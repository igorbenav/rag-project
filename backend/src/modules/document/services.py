"""Document reads and deletes."""

from typing import Any, Sequence, Tuple
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.http import document_links
from ..chunk.models import Chunk
from ..collection.models import Collection
from ..collection.ownership import OwnerId, owned_by
from ..common.exceptions import ResourceNotFoundError
from .models import Document
from .schemas import DocumentRead


def _with_chunk_count() -> Select[Any]:
    chunks = select(func.count(Chunk.id)).where(Chunk.document_id == Document.id).correlate(Document).scalar_subquery()
    return select(Document, chunks.label("chunk_count")).join(Collection, Document.collection_id == Collection.id)


def _to_read(row: Any) -> DocumentRead:
    document: Document = row[0]
    return DocumentRead(
        id=document.id,
        collection_id=document.collection_id,
        filename=document.filename,
        status=document.status,
        page_count=document.page_count,
        chunk_count=row.chunk_count,
        checksum=document.checksum,
        error=document.error,
        metadata=document.extra_metadata or {},
        created_at=document.created_at,
        updated_at=document.updated_at,
        links=document_links(document.id, document.collection_id),
    )


class DocumentService:
    """Read and delete ingested documents."""

    async def get(self, document_id: UUID, owner: OwnerId, db: AsyncSession) -> DocumentRead:
        """Fetch one document.

        Raises:
            ResourceNotFoundError: if no document has that id, or its
                collection belongs to another key.
        """
        result = await db.execute(owned_by(_with_chunk_count().where(Document.id == document_id), owner))
        row = result.first()
        if row is None:
            raise ResourceNotFoundError(f"No document with id {document_id}")
        return _to_read(row)

    async def list(
        self, collection_id: UUID, owner: OwnerId, db: AsyncSession, limit: int, offset: int
    ) -> Tuple[Sequence[DocumentRead], int]:
        """Return one page of a collection's documents and the unpaginated total."""
        total = await db.scalar(
            owned_by(
                select(func.count())
                .select_from(Document)
                .join(Collection, Document.collection_id == Collection.id)
                .where(Document.collection_id == collection_id),
                owner,
            )
        )

        result = await db.execute(
            owned_by(_with_chunk_count(), owner)
            .where(Document.collection_id == collection_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_read(row) for row in result.all()], total or 0

    async def delete(self, document_id: UUID, owner: OwnerId, db: AsyncSession) -> None:
        """Delete a document and, by cascade, its chunks.

        Raises:
            ResourceNotFoundError: if no document has that id, or its
                collection belongs to another key.
        """
        result = await db.execute(
            owned_by(
                select(Document).join(Collection, Document.collection_id == Collection.id).where(Document.id == document_id),
                owner,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ResourceNotFoundError(f"No document with id {document_id}")
        await db.delete(document)
        await db.commit()
