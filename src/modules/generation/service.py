"""Turning ranked passages into a cited answer."""

from typing import List, Optional, Sequence

from ...infrastructure.config.settings import get_settings
from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from ..query.schemas import Intent, PolicyAction, PolicyDecision
from ..retrieval.schemas import RankedChunk, RetrievalResult
from .constants import CITATION_SNIPPET_CHARS
from .prompts import (
    ANSWER_SYSTEM_PROMPT,
    CANNED_REPLIES,
    INSUFFICIENT_EVIDENCE,
    about_the_system_reply,
    format_passages,
)
from .schemas import Answer, Citation, GeneratedAnswer

logger = get_logger(__name__)


def _citations(chunks: Sequence[RankedChunk], cited: Sequence[int]) -> List[Citation]:
    """Resolve cited positions to chunks, ignoring indices that do not exist."""
    valid = [index for index in dict.fromkeys(cited) if 0 <= index < len(chunks)]

    return [
        Citation(
            chunk_id=chunks[index].chunk.chunk_id,
            document_id=chunks[index].chunk.document_id,
            page=chunks[index].chunk.page,
            snippet=chunks[index].chunk.content[:CITATION_SNIPPET_CHARS].strip(),
        )
        for index in valid
    ]


class GenerationService:
    """Produces the reply for a query, with or without the documents."""

    def reply_without_retrieval(self, intent: Intent, document_count: int, filenames: Sequence[str]) -> Answer:
        """Answer an intent that needs no documents, without calling the model.

        A greeting has one good answer. Generating it costs a round trip and
        introduces a chance of saying something wrong for no gain.
        """
        if intent is Intent.ABOUT_THE_SYSTEM:
            return Answer(text=about_the_system_reply(document_count, filenames), generated=False)

        return Answer(text=CANNED_REPLIES.get(intent, CANNED_REPLIES[Intent.CHITCHAT]), generated=False)

    def refuse(self, reason: str, message: Optional[str] = None) -> Answer:
        """Decline to answer, saying why."""
        return Answer(
            text=message or INSUFFICIENT_EVIDENCE,
            answered=False,
            refusal_reason=reason,
            generated=False,
        )

    async def answer(
        self,
        question: str,
        retrieval: RetrievalResult,
        minimum_similarity: float,
        policy: Optional[PolicyDecision] = None,
    ) -> Answer:
        """Answer a question from retrieved passages.

        Refuses in three places, deliberately. Nothing retrieved means there is
        nothing to answer from. A best similarity below the threshold means the
        corpus has nothing close enough to be worth reading. And the model
        itself reports whether the passages contained an answer, which catches
        the case the threshold cannot: passages that are on-topic but silent on
        the actual question.
        """
        if not retrieval.chunks:
            return self.refuse("no_results")

        if minimum_similarity > 0 and (retrieval.top_similarity or 0.0) < minimum_similarity:
            logger.info(
                "Refusing: best similarity %.3f below threshold %.3f",
                retrieval.top_similarity or 0.0,
                minimum_similarity,
            )
            return self.refuse("below_similarity_threshold")

        passages = [ranked.chunk.content for ranked in retrieval.chunks]

        try:
            generated = await get_chat().parse(
                format_passages(question, passages),
                GeneratedAnswer,
                system=ANSWER_SYSTEM_PROMPT,
                model=get_settings().MISTRAL_GENERATION_MODEL,
            )
        except Exception as exc:  # noqa: BLE001 - surface a refusal, not a stack trace
            logger.exception("Generation failed")
            return self.refuse("generation_failed", f"I couldn't generate an answer: {exc}")

        if not generated.answered or not generated.answer.strip():
            return self.refuse("model_found_no_answer")

        citations = _citations(retrieval.chunks, generated.cited)
        if not citations:
            logger.warning("Refusing an uncited answer: %r", generated.answer[:120])
            return self.refuse("answer_without_citation")

        disclaimer = policy.message if policy and policy.action is PolicyAction.DISCLAIM else None

        return Answer(
            text=generated.answer.strip(),
            citations=citations,
            answered=True,
            disclaimer=disclaimer,
        )
