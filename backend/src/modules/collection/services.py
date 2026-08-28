"""Collection operations, independent of how they are exposed over HTTP."""

from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...modules.common.exceptions import ResourceNotFoundError
from ..chunk.models import Chunk
from ..document.models import Document
from .crud import collection_crud
from .models import Collection
from .schemas import CollectionCreate, CollectionRead


def _with_counts() -> Select[Any]:
    """Select collections alongside their document and chunk totals.

    Correlated scalar subqueries rather than joins: joining through documents
    to chunks multiplies the rows, so a plain count would report each document
    once per chunk it owns.
    """
    documents = (
        select(func.count(Document.id)).where(Document.collection_id == Collection.id).correlate(Collection).scalar_subquery()
    )
    chunks = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.collection_id == Collection.id)
        .correlate(Collection)
        .scalar_subquery()
    )
    return select(
        Collection,
        documents.label("document_count"),
        chunks.label("chunk_count"),
    )


def _to_read(row: Any) -> CollectionRead:
    collection: Collection = row[0]
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        metadata=collection.extra_metadata or {},
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=row.document_count,
        chunk_count=row.chunk_count,
    )


class CollectionService:
    """Create, read, and delete collections."""

    async def create(self, data: CollectionCreate, db: AsyncSession) -> CollectionRead:
        collection = Collection(
            name=data.name,
            description=data.description,
            extra_metadata=data.metadata or {},
        )
        db.add(collection)
        await db.commit()
        await db.refresh(collection)

        return CollectionRead(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            metadata=collection.extra_metadata or {},
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    async def get(self, collection_id: UUID, db: AsyncSession) -> CollectionRead:
        """Fetch one collection.

        Raises:
            ResourceNotFoundError: if no collection has that id.
        """
        result = await db.execute(_with_counts().where(Collection.id == collection_id))
        row = result.first()
        if row is None:
            raise ResourceNotFoundError(f"No collection with id {collection_id}")
        return _to_read(row)

    async def list(self, db: AsyncSession, limit: int, offset: int) -> tuple[Sequence[CollectionRead], int]:
        """Return one page of collections and the unpaginated total."""
        total = await db.scalar(select(func.count()).select_from(Collection)) or 0

        result = await db.execute(_with_counts().order_by(Collection.created_at.desc()).limit(limit).offset(offset))
        return [_to_read(row) for row in result.all()], total

    async def delete(self, collection_id: UUID, db: AsyncSession) -> None:
        """Delete a collection and, by cascade, its documents and chunks.

        Raises:
            ResourceNotFoundError: if no collection has that id.
        """
        if not await collection_crud.exists(db=db, id=collection_id):
            raise ResourceNotFoundError(f"No collection with id {collection_id}")
        await collection_crud.db_delete(db=db, id=collection_id)
        await db.commit()
