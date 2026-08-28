"""BM25 ranking over an inverted index.

BM25 scores a chunk by how many query terms it contains, weighted so that rare
terms count for more, repeated terms saturate, and long chunks are not rewarded
merely for being long:

    score(c, q) = sum over terms t in q of
                  idf(t) * tf(t,c) * (k1 + 1)
                  ------------------------------------------
                  tf(t,c) + k1 * (1 - b + b * len(c) / avgdl)

This matters alongside embeddings because the two fail differently. A vector
search understands that "operating margin" and "profitability" are related, but
drifts on exact strings — a model number, an acronym, a surname — where the
literal token is the whole signal. BM25 has no idea what a word means and
matches it exactly. Fusing them covers both.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple
from uuid import UUID

from ..base import IndexedChunk, IndexStats, IndexType, SearchHit, top_k
from ..constants import BM25_B, BM25_K1, MIN_TOKEN_LENGTH
from .base import KeywordIndex

# Letters and digits only. Digits are kept deliberately: "110M", "15%" and
# "BERT-large" are exactly the queries a vector search handles worst.
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanumerics, drop single characters.

    No stopword list. BM25 already discounts common words through inverse
    document frequency, so a hand-picked list would only add a second, less
    principled mechanism doing the same job.
    """
    return [token for token in _TOKEN.findall(text.lower()) if len(token) >= MIN_TOKEN_LENGTH]


class BM25Index(KeywordIndex):
    """An in-memory inverted index scored with Okapi BM25."""

    def __init__(self, k1: float = BM25_K1, b: float = BM25_B) -> None:
        self.k1 = k1
        self.b = b
        self._chunks: List[IndexedChunk] = []
        self._term_frequencies: List[Counter[str]] = []
        self._lengths: List[int] = []
        self._postings: Dict[str, List[Tuple[int, int]]] = {}
        self._total_length = 0

    @property
    def index_type(self) -> IndexType:
        return IndexType.BM25

    @property
    def _average_length(self) -> float:
        return self._total_length / len(self._chunks) if self._chunks else 0.0

    def add(self, chunks: Sequence[IndexedChunk]) -> None:
        for chunk in chunks:
            frequencies = Counter(tokenize(chunk.content))
            position = len(self._chunks)

            self._chunks.append(chunk)
            self._term_frequencies.append(frequencies)
            length = sum(frequencies.values())
            self._lengths.append(length)
            self._total_length += length

            for term, count in frequencies.items():
                self._postings.setdefault(term, []).append((position, count))

    def remove_document(self, document_id: UUID) -> int:
        keep = [i for i, chunk in enumerate(self._chunks) if chunk.document_id != document_id]
        removed = len(self._chunks) - len(keep)
        if not removed:
            return 0

        # Positions shift, so the postings are rebuilt rather than patched.
        # Re-tokenising is avoided by keeping the per-chunk counts.
        chunks = [self._chunks[i] for i in keep]
        frequencies = [self._term_frequencies[i] for i in keep]
        self._reset()

        self._chunks = chunks
        self._term_frequencies = frequencies
        self._lengths = [sum(counter.values()) for counter in frequencies]
        self._total_length = sum(self._lengths)
        for position, counter in enumerate(frequencies):
            for term, count in counter.items():
                self._postings.setdefault(term, []).append((position, count))

        return removed

    def _inverse_document_frequency(self, term: str) -> float:
        """Rarity of a term, in the always-positive Lucene form.

        The textbook formula goes negative for terms in more than half the
        corpus, which would let a common word subtract from a score. The `+ 1`
        inside the logarithm floors it instead.
        """
        document_frequency = len(self._postings.get(term, ()))
        if not document_frequency:
            return 0.0

        total = len(self._chunks)
        return math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))

    def search(self, query: str, k: int) -> List[SearchHit]:
        if not self._chunks or k <= 0:
            return []

        average_length = self._average_length
        scores: Dict[int, float] = {}

        for term in set(tokenize(query)):
            postings = self._postings.get(term)
            if not postings:
                continue

            idf = self._inverse_document_frequency(term)
            for position, frequency in postings:
                normalised_length = 1 - self.b + self.b * self._lengths[position] / average_length
                saturation = frequency * (self.k1 + 1) / (frequency + self.k1 * normalised_length)
                scores[position] = scores.get(position, 0.0) + idf * saturation

        hits = [SearchHit(chunk=self._chunks[position], score=score) for position, score in scores.items()]
        return top_k(hits, k)

    def _reset(self) -> None:
        self._chunks = []
        self._term_frequencies = []
        self._lengths = []
        self._postings = {}
        self._total_length = 0

    def clear(self) -> None:
        self._reset()

    def stats(self) -> IndexStats:
        return IndexStats(index_type=self.index_type, total_vectors=len(self._chunks))
