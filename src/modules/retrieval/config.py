"""Which retrieval stages run, and how wide each one casts.

Every stage is switchable so the evaluation harness can measure them
separately: dense alone, keyword alone, fused, fused then reranked. Without
that, a claim about what fusion contributes is an assertion.
"""

from dataclasses import dataclass, replace

from ...infrastructure.config.settings import get_settings


@dataclass(frozen=True)
class RetrievalConfig:
    """One retrieval strategy."""

    use_dense: bool = True
    use_keyword: bool = True
    use_rerank: bool = True

    # Candidates each retriever returns before fusion. Wider than the final k
    # because fusion can only rank what it is given: a chunk missed by both
    # retrievers cannot be recovered later.
    candidates_per_retriever: int = 20

    # Chunks handed to the generator after ranking.
    top_k: int = 5

    # Fused candidates passed to the reranker.
    rerank_candidates: int = 20

    # Reciprocal rank fusion constant. Damps the influence of the top ranks so
    # a chunk placed second by both retrievers can beat one placed first by
    # only one of them. 60 is the value from the original RRF paper.
    rrf_k: int = 60

    # Below this cosine similarity the best hit is treated as no answer.
    # Calibrated against the evaluation set, not guessed: unrelated text still
    # scores around 0.63 with mistral-embed, so the useful range is narrow.
    minimum_similarity: float = 0.0

    @classmethod
    def from_settings(cls) -> "RetrievalConfig":
        settings = get_settings()
        return cls(
            candidates_per_retriever=settings.RETRIEVAL_CANDIDATES,
            top_k=settings.RETRIEVAL_TOP_K,
            rrf_k=settings.RETRIEVAL_RRF_K,
            rerank_candidates=settings.RERANK_CANDIDATES,
            minimum_similarity=settings.RETRIEVAL_MIN_SIMILARITY,
        )

    def only_dense(self) -> "RetrievalConfig":
        return replace(self, use_dense=True, use_keyword=False, use_rerank=False)

    def only_keyword(self) -> "RetrievalConfig":
        return replace(self, use_dense=False, use_keyword=True, use_rerank=False)

    def fused(self) -> "RetrievalConfig":
        return replace(self, use_dense=True, use_keyword=True, use_rerank=False)
