"""Reads for ingestion jobs."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.http import ingestion_links
from ..collection.models import Collection
from ..collection.ownership import OwnerId, owned_by
from ..common.exceptions import ResourceNotFoundError
from ..document.models import Document
from .models import IngestionJob
from .schemas import IngestionJobRead


class IngestionService:
    """Read the progress of an upload."""

    async def get(self, job_id: UUID, owner: OwnerId, db: AsyncSession) -> IngestionJobRead:
        """Fetch one job with the documents it created.

        Raises:
            ResourceNotFoundError: if no job has that id, or its collection
                belongs to another key.
        """
        result = await db.execute(
            owned_by(
                select(IngestionJob)
                .join(Collection, IngestionJob.collection_id == Collection.id)
                .where(IngestionJob.id == job_id),
                owner,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise ResourceNotFoundError(f"No ingestion job with id {job_id}")

        document_ids = await self._document_ids(job_id, db)
        return IngestionJobRead(
            id=job.id,
            collection_id=job.collection_id,
            status=job.status,
            total_documents=job.total_documents,
            completed_documents=job.completed_documents,
            failed_documents=job.failed_documents,
            error=job.error,
            document_ids=document_ids,
            created_at=job.created_at,
            updated_at=job.updated_at,
            links=ingestion_links(job.id, job.collection_id),
        )

    async def _document_ids(self, job_id: UUID, db: AsyncSession) -> List[UUID]:
        result = await db.execute(select(Document.id).where(Document.ingestion_job_id == job_id).order_by(Document.created_at))
        return list(result.scalars())
