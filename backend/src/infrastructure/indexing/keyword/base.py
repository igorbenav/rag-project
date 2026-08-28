"""The contract every keyword index implements.

Deliberately not a `VectorIndex`: a keyword index has no embedding, no
dimension, and no notion of distance. Forcing both behind one interface would
mean an `embedding` argument that one of them ignores.
"""

from abc import ABC, abstractmethod
from typing import List, Sequence
from uuid import UUID

from ..base import IndexedChunk, IndexStats, IndexType, SearchHit


class KeywordIndex(ABC):
    """A searchable set of chunks, ranked by term overlap."""

    @property
    @abstractmethod
    def index_type(self) -> IndexType: ...

    @abstractmethod
    def add(self, chunks: Sequence[IndexedChunk]) -> None:
        """Add chunks, tokenising their content."""

    @abstractmethod
    def remove_document(self, document_id: UUID) -> int:
        """Drop every chunk belonging to a document. Returns how many went."""

    @abstractmethod
    def search(self, query: str, k: int) -> List[SearchHit]:
        """Return the k best-matching chunks, highest score first."""

    @abstractmethod
    def clear(self) -> None:
        """Drop everything."""

    @abstractmethod
    def stats(self) -> IndexStats:
        """Describe the current contents."""
