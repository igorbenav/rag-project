"""Reranking fused candidates with a language model.

Retrieval ranks by similarity, which is a proxy for relevance and not the same
thing: a chunk can be about the right topic without containing the answer. A
model reading the question alongside each candidate judges that directly, so
this stage fixes ordering rather than recall — it can only reorder what the
retrievers already found.

Candidates are presented in a numbered list and the model returns positions
rather than text. Asking for text back would mean matching strings to chunks,
and a model that paraphrases a passage would break the mapping silently.
"""

from typing import List, Sequence

from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from .constants import RERANK_PASSAGE_CHARS
from .prompts import RERANK_PROMPT
from .schemas import RankedChunk, RerankOrder

logger = get_logger(__name__)

def _format_candidates(question: str, candidates: Sequence[RankedChunk]) -> str:
    passages = "\n".join(
        f"[{position}] {candidate.chunk.content[:RERANK_PASSAGE_CHARS]}" for position, candidate in enumerate(candidates)
    )
    return f"Question: {question}\n\n{passages}"


def _apply_order(candidates: Sequence[RankedChunk], indices: Sequence[int]) -> List[RankedChunk]:
    """Reorder candidates, tolerating a partial or malformed answer.

    Out-of-range and repeated indices are dropped, and anything the model did
    not mention keeps its fused position at the end. A bad response degrades
    the ordering; it never loses a candidate.
    """
    seen: set[int] = set()
    ordered: List[RankedChunk] = []

    for index in indices:
        if 0 <= index < len(candidates) and index not in seen:
            seen.add(index)
            ordered.append(candidates[index])

    ordered.extend(candidate for position, candidate in enumerate(candidates) if position not in seen)

    for position, candidate in enumerate(ordered):
        candidate.rerank_position = position

    return ordered


async def rerank(question: str, candidates: Sequence[RankedChunk]) -> List[RankedChunk]:
    """Reorder candidates by judged relevance.

    Returns the candidates untouched if the model call fails: a worse ordering
    is better than no answer.
    """
    if len(candidates) < 2:
        return list(candidates)

    try:
        result = await get_chat().parse(_format_candidates(question, candidates), RerankOrder, system=RERANK_PROMPT)
    except Exception as exc:  # noqa: BLE001 - keep the fused order
        logger.warning("Reranking failed, keeping the fused order: %s", exc)
        return list(candidates)

    returned = len(set(result.ordered_indices) & set(range(len(candidates))))
    if returned < len(candidates):
        logger.debug("Reranker returned %d of %d indices", returned, len(candidates))

    return _apply_order(candidates, result.ordered_indices)
