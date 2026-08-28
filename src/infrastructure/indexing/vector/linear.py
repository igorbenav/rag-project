"""Exact nearest-neighbour search over every vector in the index.

One matrix multiply, then a partial sort. Exhaustive, so recall is 1.0 by
construction: whatever it returns is genuinely the closest, which is what makes
it the yardstick every approximate index is measured against.
"""

from typing import List, Sequence
from uuid import UUID

import numpy as np

from ..base import IndexedChunk, IndexStats, IndexType, SearchHit
from .base import VectorIndex


def _normalise(matrix: np.ndarray) -> np.ndarray:
    """Scale rows to unit length so a dot product is a cosine similarity.

    Mistral already returns unit vectors, so this is usually a no-op; doing it
    anyway keeps the index correct for any embedding provider.
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return np.asarray(matrix / norms, dtype=np.float32)


class LinearVectorIndex(VectorIndex):
    """Brute-force cosine similarity against a preallocated matrix."""

    def __init__(self, dimension: int) -> None:
        super().__init__(dimension)
        self._chunks: List[IndexedChunk] = []
        self._matrix = np.empty((0, dimension), dtype=np.float32)

    @property
    def index_type(self) -> IndexType:
        return IndexType.LINEAR

    def add(self, chunks: Sequence[IndexedChunk], embeddings: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(f"Got {len(chunks)} chunks and {len(embeddings)} embeddings")
        if not chunks:
            return

        for embedding in embeddings:
            self._check_dimension(embedding)

        block = _normalise(np.asarray(embeddings, dtype=np.float32))
        self._matrix = np.vstack([self._matrix, block]) if len(self._chunks) else block
        self._chunks.extend(chunks)

    def remove_document(self, document_id: UUID) -> int:
        keep = [i for i, chunk in enumerate(self._chunks) if chunk.document_id != document_id]
        removed = len(self._chunks) - len(keep)
        if not removed:
            return 0

        self._chunks = [self._chunks[i] for i in keep]
        self._matrix = self._matrix[keep] if keep else np.empty((0, self.dimension), dtype=np.float32)
        return removed

    def search(self, query: Sequence[float], k: int) -> List[SearchHit]:
        self._check_dimension(query)
        if not self._chunks or k <= 0:
            return []

        vector = _normalise(np.asarray([query], dtype=np.float32))[0]
        scores = self._matrix @ vector

        # argpartition finds the k best in linear time; only those k are then
        # sorted, which matters once the index is large and k stays small.
        wanted = min(k, len(scores))
        candidates = np.argpartition(-scores, wanted - 1)[:wanted]
        ordered = candidates[np.argsort(-scores[candidates])]

        return [SearchHit(chunk=self._chunks[i], score=float(scores[i])) for i in ordered]

    def clear(self) -> None:
        self._chunks = []
        self._matrix = np.empty((0, self.dimension), dtype=np.float32)

    def stats(self) -> IndexStats:
        return IndexStats(
            index_type=self.index_type,
            total_vectors=len(self._chunks),
            dimension=self.dimension,
        )
