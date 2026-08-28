"""Per-collection indexes, built on demand from the database.

The indexes live in memory, but the API and the worker are separate processes:
an index the worker filled would be invisible to the process serving searches.
So Postgres stays the source of truth and each index is a cache over it, rebuilt
whenever the collection's chunks have changed underneath it.

The check is one cheap aggregate per search — the number of chunks and the most
recent write. That is enough to notice ingestion, deletion, and re-ingestion,
and it costs a single indexed query rather than a coordination protocol.

At this corpus size rebuilding is milliseconds. A larger deployment would put
the index behind its own service, or push vectors into the database and search
them there; both are noted in the README rather than built.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...modules.chunk.models import Chunk
from ...modules.document.models import Document
from ..config.settings import get_settings
from ..logging import get_logger
from .base import IndexedChunk, IndexStats, SearchHit
from .keyword.bm25 import BM25Index
from .vector.linear import LinearVectorIndex

logger = get_logger(__name__)


@dataclass
class _Fingerprint:
    """What the indexes were built from, so staleness is detectable.

    `models` is part of the identity: re-embedding under a different model
    changes no count and no timestamp, but every vector in the index moves.
    """

    count: int
    latest: Optional[datetime]
    models: Tuple[str, ...]


@dataclass
class _CollectionIndexes:
    """The pair of indexes for one collection, and their provenance."""

    vectors: LinearVectorIndex
    keywords: BM25Index
    fingerprint: _Fingerprint


class IndexManager:
    """Holds both indexes for each collection and keeps them in step.

    Both are rebuilt together under one lock. A chunk present in one but not the
    other is silent recall loss: fusion would keep scoring it from one side and
    no test would notice.
    """

    def __init__(self) -> None:
        self._indexes: Dict[UUID, _CollectionIndexes] = {}
        self._locks: Dict[UUID, asyncio.Lock] = {}

    def _lock_for(self, collection_id: UUID) -> asyncio.Lock:
        return self._locks.setdefault(collection_id, asyncio.Lock())

    async def _fingerprint(self, collection_id: UUID, db: AsyncSession) -> _Fingerprint:
        row = (
            await db.execute(
                select(func.count(Chunk.id), func.max(Chunk.created_at))
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.collection_id == collection_id)
            )
        ).one()
        models = (
            await db.execute(
                select(Chunk.embedding_model)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.collection_id == collection_id)
                .distinct()
            )
        ).scalars()
        return _Fingerprint(count=row[0] or 0, latest=row[1], models=tuple(sorted(models)))

    async def _load(self, collection_id: UUID, db: AsyncSession) -> _CollectionIndexes:
        """Read a collection's chunks and build both indexes from them."""
        dimension = get_settings().EMBEDDING_DIM

        result = await db.execute(
            select(Chunk.id, Chunk.document_id, Chunk.page, Chunk.content, Chunk.embedding)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.collection_id == collection_id)
            .order_by(Chunk.ordinal)
        )
        rows = result.all()

        chunks = [IndexedChunk(chunk_id=row[0], document_id=row[1], page=row[2], content=row[3]) for row in rows]
        embeddings = [row[4] for row in rows]

        vectors = LinearVectorIndex(dimension=dimension)
        keywords = BM25Index()
        if chunks:
            vectors.add(chunks, embeddings)
            keywords.add(chunks)

        fingerprint = await self._fingerprint(collection_id, db)
        if len(fingerprint.models) > 1:
            logger.warning(
                "Collection %s mixes embedding models %s; re-ingest to make ranking comparable",
                collection_id,
                fingerprint.models,
            )

        logger.info("Built indexes for collection %s from %d chunks", collection_id, len(chunks))
        return _CollectionIndexes(vectors=vectors, keywords=keywords, fingerprint=fingerprint)

    async def _ensure_current(self, collection_id: UUID, db: AsyncSession) -> _CollectionIndexes:
        """Return indexes matching what is in the database right now."""
        async with self._lock_for(collection_id):
            cached = self._indexes.get(collection_id)
            current = await self._fingerprint(collection_id, db)

            if cached is not None and cached.fingerprint == current:
                return cached

            rebuilt = await self._load(collection_id, db)
            self._indexes[collection_id] = rebuilt
            return rebuilt

    async def search_vector(self, collection_id: UUID, embedding: Sequence[float], k: int, db: AsyncSession) -> List[SearchHit]:
        indexes = await self._ensure_current(collection_id, db)
        return indexes.vectors.search(embedding, k)

    async def search_keyword(self, collection_id: UUID, query: str, k: int, db: AsyncSession) -> List[SearchHit]:
        indexes = await self._ensure_current(collection_id, db)
        return indexes.keywords.search(query, k)

    async def stats(self, collection_id: UUID, db: AsyncSession) -> Tuple[IndexStats, IndexStats]:
        indexes = await self._ensure_current(collection_id, db)
        return indexes.vectors.stats(), indexes.keywords.stats()

    def forget(self, collection_id: UUID) -> None:
        """Drop cached indexes, e.g. when the collection itself is deleted."""
        self._indexes.pop(collection_id, None)
        self._locks.pop(collection_id, None)


index_manager = IndexManager()
