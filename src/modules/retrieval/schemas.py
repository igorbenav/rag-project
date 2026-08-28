"""What retrieval returns, including how each chunk got there."""

from dataclasses import dataclass, field
from typing import List, Optional

from ...infrastructure.indexing.base import IndexedChunk


@dataclass
class RankedChunk:
    """A chunk with its final score and the ranks that produced it.

    The per-retriever ranks are kept rather than discarded: they are what makes
    an answer explainable, and what the trace panel shows when someone asks why
    a particular passage was used.
    """

    chunk: IndexedChunk
    score: float
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    keyword_rank: Optional[int] = None
    keyword_score: Optional[float] = None
    rerank_position: Optional[int] = None

    @property
    def found_by(self) -> List[str]:
        sources = []
        if self.dense_rank is not None:
            sources.append("dense")
        if self.keyword_rank is not None:
            sources.append("keyword")
        return sources


@dataclass
class RetrievalResult:
    """The ranked chunks, plus a record of what each stage did."""

    chunks: List[RankedChunk] = field(default_factory=list)
    dense_count: int = 0
    keyword_count: int = 0
    fused_count: int = 0
    reranked: bool = False
    top_similarity: Optional[float] = None
