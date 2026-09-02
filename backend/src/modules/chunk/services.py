"""Chunk reads. Chunks are created by ingestion and never edited."""

from typing import Any, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.http import chunk_links
from ..collection.models import Collection
from ..collection.ownership import OwnerId, owned_by
from ..common.exceptions import ResourceNotFoundError
from ..document.models import Document
from .models import Chunk
from .schemas import ChunkRead


def _through_collection() -> Any:
    """Chunks reach their owner two hops up, through the document."""
    return (
        select(Chunk).join(Document, Chunk.document_id == Document.id).join(Collection, Document.collection_id == Collection.id)
    )


def _to_read(chunk: Chunk) -> ChunkRead:
    return ChunkRead(
        id=chunk.id,
        document_id=chunk.document_id,
        content=chunk.content,
        page=chunk.page,
        ordinal=chunk.ordinal,
        metadata=chunk.extra_metadata or {},
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
        links=chunk_links(chunk.id, chunk.document_id),
    )


class ChunkService:
    """Fetch chunks, individually or by document."""

    async def get(self, chunk_id: UUID, owner: OwnerId, db: AsyncSession) -> ChunkRead:
        """Fetch one chunk. This is what a citation links to.

        Raises:
            ResourceNotFoundError: if no chunk has that id, or its collection
                belongs to another key.
        """
        result = await db.execute(owned_by(_through_collection().where(Chunk.id == chunk_id), owner))
        chunk = result.scalar_one_or_none()
        if chunk is None:
            raise ResourceNotFoundError(f"No chunk with id {chunk_id}")
        return _to_read(chunk)

    async def list_for_document(
        self, document_id: UUID, owner: OwnerId, db: AsyncSession, limit: int, offset: int
    ) -> Tuple[Sequence[ChunkRead], int]:
        """Return one page of a document's chunks, in document order."""
        total = await db.scalar(
            owned_by(
                select(func.count())
                .select_from(Chunk)
                .join(Document, Chunk.document_id == Document.id)
                .join(Collection, Document.collection_id == Collection.id)
                .where(Chunk.document_id == document_id),
                owner,
            )
        )

        result = await db.execute(
            owned_by(_through_collection(), owner)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.ordinal)
            .limit(limit)
            .offset(offset)
        )
        return [_to_read(chunk) for chunk in result.scalars()], total or 0
