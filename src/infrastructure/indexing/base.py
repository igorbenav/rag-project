"""Types shared by every index, vector or keyword."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from uuid import UUID


class IndexType(str, Enum):
    """Selectable index implementations."""

    LINEAR = "linear"
    IVF = "ivf"
    BM25 = "bm25"


@dataclass(frozen=True)
class IndexedChunk:
    """A chunk as an index holds it: enough to rank it and to cite it.

    Content and page ride along so a search result can be rendered without a
    second trip to the database for every hit.
    """

    chunk_id: UUID
    document_id: UUID
    page: int
    content: str


@dataclass(frozen=True)
class SearchHit:
    """One ranked result."""

    chunk: IndexedChunk
    score: float

    @property
    def chunk_id(self) -> UUID:
        return self.chunk.chunk_id


@dataclass(frozen=True)
class IndexStats:
    """What an index can report about itself."""

    index_type: IndexType
    total_vectors: int
    dimension: Optional[int] = None
    clusters: Optional[int] = None
    is_built: bool = True


def top_k(hits: List[SearchHit], k: int) -> List[SearchHit]:
    """Highest scores first, truncated to k."""
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:k]
