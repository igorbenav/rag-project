"""Chunk reads. Chunks are created by ingestion and never edited."""

from typing import Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.http import chunk_links
from ..common.exceptions import ResourceNotFoundError
from .models import Chunk
from .schemas import ChunkRead


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

    async def get(self, chunk_id: UUID, db: AsyncSession) -> ChunkRead:
        """Fetch one chunk. This is what a citation links to.

        Raises:
            ResourceNotFoundError: if no chunk has that id.
        """
        chunk = await db.get(Chunk, chunk_id)
        if chunk is None:
            raise ResourceNotFoundError(f"No chunk with id {chunk_id}")
        return _to_read(chunk)

    async def list_for_document(
        self, document_id: UUID, db: AsyncSession, limit: int, offset: int
    ) -> Tuple[Sequence[ChunkRead], int]:
        """Return one page of a document's chunks, in document order."""
        total = await db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id))

        result = await db.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal).limit(limit).offset(offset)
        )
        return [_to_read(chunk) for chunk in result.scalars()], total or 0
