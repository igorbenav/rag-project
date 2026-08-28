"""Embedding generation via the Mistral API."""

from typing import List, Sequence

from ..config.settings import get_settings
from ..logging import get_logger
from .client import get_client

logger = get_logger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when the API returns something unusable."""


class MistralEmbedder:
    """Turns text into vectors, in batches.

    The dimension is fixed by settings and asserted on every response: a model
    change would otherwise write vectors of the wrong width into an index built
    for the old one, and the failure would surface much later as poor recall.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.MISTRAL_EMBED_MODEL
        self.dimension = settings.EMBEDDING_DIM
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    async def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed many texts, preserving input order.

        Raises:
            EmbeddingError: on an empty input, or a dimension mismatch.
        """
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise EmbeddingError("Cannot embed empty text")

        client = get_client()
        vectors: List[List[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            response = await client.embeddings.create_async(model=self.model, inputs=batch)

            if len(response.data) != len(batch):
                raise EmbeddingError(f"Asked for {len(batch)} embeddings, received {len(response.data)}")

            for item in response.data:
                if item.embedding is None:
                    raise EmbeddingError("Response contained an empty embedding")
                if len(item.embedding) != self.dimension:
                    raise EmbeddingError(
                        f"{self.model} returned {len(item.embedding)} dimensions, but EMBEDDING_DIM is {self.dimension}"
                    )
                vectors.append(list(item.embedding))

        logger.debug("Embedded %d texts in %d batches", len(texts), -(-len(texts) // self.batch_size))
        return vectors

    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        vectors = await self.embed_texts([text])
        return vectors[0]


_embedder: MistralEmbedder | None = None


def get_embedder() -> MistralEmbedder:
    """Return the process-wide embedder."""
    global _embedder
    if _embedder is None:
        _embedder = MistralEmbedder()
    return _embedder
