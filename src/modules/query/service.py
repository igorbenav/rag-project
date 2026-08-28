"""Answering a question: route it, retrieve for it, generate from what came back."""

import asyncio
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_embedder
from ..common.exceptions import ResourceNotFoundError
from ..document.models import Document
from ..generation.schemas import Answer
from ..generation.service import GenerationService
from ..retrieval.config import RetrievalConfig
from ..retrieval.schemas import RetrievalResult
from ..retrieval.service import RetrievalService
from .intent import detect_intent, quick_intent
from .models import Query
from .policy import apply_policies
from .schemas import (
    Intent,
    IntentDecision,
    PolicyAction,
    QueryCreate,
    QueryRead,
    TransformedQuery,
)
from .transform import transform_query

logger = get_logger(__name__)


def _citation_rows(answer: Answer) -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": str(citation.chunk_id),
            "document_id": str(citation.document_id),
            "page": citation.page,
            "snippet": citation.snippet,
        }
        for citation in answer.citations
    ]


def _trace_row(
    intent: IntentDecision,
    transformed: Optional[TransformedQuery],
    retrieval: Optional[RetrievalResult],
) -> Dict[str, Any]:
    """Record what each stage did, so an answer can be explained afterwards."""
    trace: Dict[str, Any] = {
        "intent": intent.intent.value,
        "intent_decided_by": intent.decided_by,
        "retrieved": retrieval is not None,
    }

    if transformed is not None:
        trace |= {
            "dense_query": transformed.dense_query,
            "keyword_query": transformed.keyword_query,
            "key_terms": transformed.key_terms,
        }

    if retrieval is not None:
        trace |= {
            "dense_count": retrieval.dense_count,
            "keyword_count": retrieval.keyword_count,
            "fused_count": retrieval.fused_count,
            "reranked": retrieval.reranked,
            "top_similarity": retrieval.top_similarity,
            "candidates": [
                {
                    "chunk_id": str(ranked.chunk.chunk_id),
                    "document_id": str(ranked.chunk.document_id),
                    "page": ranked.chunk.page,
                    "fused_score": ranked.score,
                    "dense_rank": ranked.dense_rank,
                    "keyword_rank": ranked.keyword_rank,
                    "rerank_position": ranked.rerank_position,
                    "found_by": ranked.found_by,
                }
                for ranked in retrieval.chunks
            ],
        }

    return trace


class QueryService:
    """Runs a question through the pipeline and records the outcome."""

    def __init__(self) -> None:
        self.retrieval = RetrievalService()
        self.generation = GenerationService()

    async def ask(
        self,
        collection_id: UUID,
        body: QueryCreate,
        config: RetrievalConfig,
        db: AsyncSession,
    ) -> Query:
        """Answer a question and persist the result."""
        started = time.perf_counter()
        question = body.question.strip()

        policy = apply_policies(question)
        if policy.action is PolicyAction.REFUSE:
            answer = self.generation.refuse(f"policy_{policy.category}", policy.message)
            intent = IntentDecision(
                intent=Intent.QUESTION,
                needs_retrieval=False,
                decided_by="policy",
                reason=f"Blocked by the {policy.category} policy.",
            )
            return await self._persist(collection_id, question, intent, None, None, answer, started, db)

        intent, transformed = await self._route(question)

        if not intent.needs_retrieval:
            count, filenames = await self._collection_documents(collection_id, db)
            answer = self.generation.reply_without_retrieval(intent.intent, count, filenames)
            return await self._persist(collection_id, question, intent, None, None, answer, started, db)

        assert transformed is not None
        embedding = await get_embedder().embed_query(transformed.dense_query)
        retrieval = await self.retrieval.retrieve(collection_id, transformed.keyword_query, embedding, config, db)

        answer = await self.generation.answer(question, retrieval, config.minimum_similarity, policy)
        return await self._persist(collection_id, question, intent, transformed, retrieval, answer, started, db)

    async def _route(self, question: str) -> Tuple[IntentDecision, Optional[TransformedQuery]]:
        """Classify and rewrite in one step.

        A phrase match settles greetings and thanks with no model call at all.
        Otherwise both calls go out together: neither depends on the other, so
        running them in sequence would pay for the slower one twice.
        """
        quick = quick_intent(question)
        if quick is not None and not quick.needs_retrieval:
            return quick, None

        intent, transformed = await asyncio.gather(detect_intent(question), transform_query(question))
        return intent, transformed if intent.needs_retrieval else None

    async def _collection_documents(self, collection_id: UUID, db: AsyncSession) -> Tuple[int, List[str]]:
        rows = (await db.execute(select(Document.filename).where(Document.collection_id == collection_id).limit(10))).scalars()
        filenames = list(rows)
        total = await db.scalar(select(func.count()).select_from(Document).where(Document.collection_id == collection_id))
        return total or 0, filenames

    async def _persist(
        self,
        collection_id: UUID,
        question: str,
        intent: IntentDecision,
        transformed: Optional[TransformedQuery],
        retrieval: Optional[RetrievalResult],
        answer: Answer,
        started: float,
        db: AsyncSession,
    ) -> Query:
        query = Query(
            collection_id=collection_id,
            question=question,
            answer=answer.text,
            answered=answer.answered,
            intent=intent.intent.value,
            refusal_reason=answer.refusal_reason,
            disclaimer=answer.disclaimer,
            citations=_citation_rows(answer),
            unsupported_claims=[{"sentence": claim.sentence, "reason": claim.reason} for claim in answer.unsupported_claims],
            evidence_checked=answer.evidence_checked,
            trace=_trace_row(intent, transformed, retrieval),
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )
        db.add(query)
        await db.commit()
        return query

    async def get(self, query_id: UUID, db: AsyncSession) -> QueryRead:
        """Fetch a stored answer without recomputing it.

        Raises:
            ResourceNotFoundError: if no query has that id.
        """
        query = await db.get(Query, query_id)
        if query is None:
            raise ResourceNotFoundError(f"No query with id {query_id}")
        return QueryRead.from_model(query)

    async def list_for_collection(
        self, collection_id: UUID, db: AsyncSession, limit: int, offset: int
    ) -> Tuple[Sequence[QueryRead], int]:
        """Return one page of a collection's query history, newest first."""
        total = await db.scalar(select(func.count()).select_from(Query).where(Query.collection_id == collection_id))
        rows = (
            await db.execute(
                select(Query)
                .where(Query.collection_id == collection_id)
                .order_by(Query.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [QueryRead.from_model(row) for row in rows], total or 0
