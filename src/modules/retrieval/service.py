"""Retrieval: run the enabled retrievers, fuse their rankings, take the top k."""

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.indexing import index_manager
from ...infrastructure.indexing.base import SearchHit
from ...infrastructure.logging import get_logger
from .config import RetrievalConfig
from .fusion import reciprocal_rank_fusion
from .rerank import rerank
from .schemas import RankedChunk, RetrievalResult

logger = get_logger(__name__)


class RetrievalService:
    """Finds the chunks most likely to answer a query."""

    async def retrieve(
        self,
        collection_id: UUID,
        query: str,
        embedding: Sequence[float],
        config: RetrievalConfig,
        db: AsyncSession,
    ) -> RetrievalResult:
        """Retrieve and rank candidates for one query.

        The two retrievers run one after the other rather than concurrently:
        they share a database session, which is not safe to use from two tasks
        at once, and the searches themselves are in-memory work where
        concurrency would buy nothing.
        """
        dense: List[SearchHit] = []
        keyword: List[SearchHit] = []

        if config.use_dense:
            dense = await index_manager.search_vector(collection_id, embedding, config.candidates_per_retriever, db)

        if config.use_keyword:
            keyword = await index_manager.search_keyword(collection_id, query, config.candidates_per_retriever, db)

        fused = reciprocal_rank_fusion(dense, keyword, config.rrf_k)

        ranked = fused
        reranked = False
        if config.use_rerank and len(fused) > 1:
            ranked = await rerank(query, fused[: config.rerank_candidates])
            reranked = True

        selected = ranked[: config.top_k]

        return RetrievalResult(
            chunks=selected,
            dense_count=len(dense),
            keyword_count=len(keyword),
            fused_count=len(fused),
            reranked=reranked,
            top_similarity=_best_similarity(selected),
        )


def _best_similarity(chunks: Sequence[RankedChunk]) -> Optional[float]:
    """Highest cosine similarity among the selected chunks.

    Reported separately from the fused score because only this one is
    comparable across queries, which is what a refusal threshold needs.
    """
    similarities = [chunk.dense_score for chunk in chunks if chunk.dense_score is not None]
    return max(similarities) if similarities else None
