"""The contract every vector index implements."""

from abc import ABC, abstractmethod
from typing import List, Sequence
from uuid import UUID

from ..base import IndexedChunk, IndexStats, IndexType, SearchHit


class VectorIndex(ABC):
    """A searchable set of embeddings.

    Implementations differ only in how they find neighbours: exhaustively, or
    by narrowing to part of the space first.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    @property
    @abstractmethod
    def index_type(self) -> IndexType: ...

    @abstractmethod
    def add(self, chunks: Sequence[IndexedChunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Add chunks and their embeddings."""

    @abstractmethod
    def remove_document(self, document_id: UUID) -> int:
        """Drop every chunk belonging to a document. Returns how many went."""

    @abstractmethod
    def search(self, query: Sequence[float], k: int) -> List[SearchHit]:
        """Return the k nearest chunks, most similar first."""

    @abstractmethod
    def clear(self) -> None:
        """Drop everything."""

    @abstractmethod
    def stats(self) -> IndexStats:
        """Describe the current contents."""

    def _check_dimension(self, embedding: Sequence[float]) -> None:
        if len(embedding) != self.dimension:
            raise ValueError(f"Embedding has {len(embedding)} dimensions, index expects {self.dimension}")
