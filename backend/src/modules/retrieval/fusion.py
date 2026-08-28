"""Reciprocal rank fusion.

Two retrievers produce scores on incomparable scales: cosine similarity sits
between 0 and 1 and clusters high, while BM25 is unbounded and depends on
corpus statistics. Normalising them into a common range means choosing a
mapping and defending it, and the choice moves results.

RRF sidesteps that by discarding the scores and keeping only the ranks:

    score(chunk) = sum over retrievers of 1 / (k + rank)

A chunk ranked second by both retrievers beats one ranked first by a single
retriever, which is the behaviour worth having — agreement between two methods
that fail differently is stronger evidence than one method's confidence.
"""

from typing import Dict, List, Sequence
from uuid import UUID

from ...infrastructure.indexing.base import SearchHit
from .schemas import RankedChunk


def reciprocal_rank_fusion(
    dense: Sequence[SearchHit],
    keyword: Sequence[SearchHit],
    rrf_k: int,
) -> List[RankedChunk]:
    """Merge two ranked lists into one, ordered by fused score.

    Args:
        dense: Hits from the vector index, best first.
        keyword: Hits from the keyword index, best first.
        rrf_k: Damping constant; larger values flatten the influence of rank.

    Returns:
        Every chunk either retriever found, best first.
    """
    merged: Dict[UUID, RankedChunk] = {}

    def contribute(hits: Sequence[SearchHit], source: str) -> None:
        for rank, hit in enumerate(hits, start=1):
            entry = merged.get(hit.chunk_id)
            if entry is None:
                entry = RankedChunk(chunk=hit.chunk, score=0.0)
                merged[hit.chunk_id] = entry

            entry.score += 1.0 / (rrf_k + rank)
            if source == "dense":
                entry.dense_rank, entry.dense_score = rank, hit.score
            else:
                entry.keyword_rank, entry.keyword_score = rank, hit.score

    contribute(dense, "dense")
    contribute(keyword, "keyword")

    return sorted(merged.values(), key=lambda ranked: ranked.score, reverse=True)
