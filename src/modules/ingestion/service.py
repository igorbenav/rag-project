"""Ingestion: validate an upload, then process it off the request path.

Sessions are deliberately short and never span slow IO. Extraction is CPU
work in a worker thread and embedding is a network round trip per batch;
holding a connection across either lets the database reap it mid-job, and on a
pooled Postgres it also pins a slot that other requests need.
"""

import hashlib
from dataclasses import dataclass
from typing import List, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.session import local_session
from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_embedder
from ..chunk.models import Chunk
from ..common.exceptions import UnsupportedMediaTypeError, ValidationError
from ..common.mime import normalize_content_type
from ..document.models import Document, DocumentStatus
from .chunking import TextChunk, chunk_document
from .constants import (
    ALLOWED_UPLOAD_TYPES,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_FILES,
)
from .models import IngestionJob, IngestionStatus
from .pdf import extract_pdf, looks_like_pdf

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueuedDocument:
    """A document row paired with the bytes waiting to fill it."""

    document_id: UUID
    upload: "Upload"


@dataclass(frozen=True)
class Upload:
    """One validated file, held in memory until its job finishes."""

    filename: str
    data: bytes

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def validate_upload(filename: str, content_type: str, data: bytes) -> Upload:
    """Check one file before it is queued.

    The declared content type is only a first filter. Both it and
    Content-Length are set by the client, so the size limit is applied to the
    bytes actually read and the format is decided by the file signature.

    Raises:
        UnsupportedMediaTypeError: if the type or signature is not a PDF.
        ValidationError: if the file is empty or over the size limit.
    """
    if normalize_content_type(content_type) not in ALLOWED_UPLOAD_TYPES:
        raise UnsupportedMediaTypeError(f"{filename}: expected a PDF, got {content_type}")

    if not data:
        raise ValidationError(f"{filename} is empty")

    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"{filename} is {len(data)} bytes, over the {MAX_UPLOAD_BYTES} byte limit")

    if not looks_like_pdf(data):
        raise UnsupportedMediaTypeError(f"{filename} is not a PDF")

    return Upload(filename=filename, data=data)


def validate_uploads(files: Sequence[tuple[str, str, bytes]]) -> List[Upload]:
    """Validate every file in a request, rejecting the whole batch on any failure."""
    if not files:
        raise ValidationError("No files were uploaded")

    if len(files) > MAX_UPLOAD_FILES:
        raise ValidationError(f"{len(files)} files exceeds the limit of {MAX_UPLOAD_FILES}")

    return [validate_upload(name, content_type, data) for name, content_type, data in files]


async def create_job(
    collection_id: UUID, uploads: Sequence[Upload], db: AsyncSession
) -> tuple[IngestionJob, List[QueuedDocument]]:
    """Record the job and its documents so the client has something to poll.

    Returns the queued pairs directly: identifiers are generated client-side,
    so they are known before the rows are flushed and the background task needs
    no lookup to find its work.
    """
    job = IngestionJob(collection_id=collection_id, total_documents=len(uploads))
    db.add(job)

    await db.flush()

    queued: List[QueuedDocument] = []
    for upload in uploads:
        document = Document(
            collection_id=collection_id,
            filename=upload.filename,
            checksum=upload.checksum,
            status=DocumentStatus.PENDING,
            ingestion_job_id=job.id,
        )
        db.add(document)
        queued.append(QueuedDocument(document_id=document.id, upload=upload))

    await db.commit()
    return job, queued


async def _mark_job(job_id: UUID, status: IngestionStatus, error: str | None = None) -> None:
    async with local_session() as db:
        job = await db.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = status
        if error:
            job.error = error[:1000]
        await db.commit()


async def _mark_document(document_id: UUID, status: DocumentStatus, page_count: int = 0, error: str | None = None) -> None:
    async with local_session() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        document.status = status
        document.page_count = page_count
        if error:
            document.error = error[:1000]
        await db.commit()


async def _record_progress(job_id: UUID, *, succeeded: bool) -> None:
    async with local_session() as db:
        job = await db.get(IngestionJob, job_id)
        if job is None:
            return
        if succeeded:
            job.completed_documents += 1
        else:
            job.failed_documents += 1
        await db.commit()


async def _persist_chunks(document_id: UUID, chunks: Sequence[TextChunk], vectors: Sequence[List[float]]) -> None:
    async with local_session() as db:
        for chunk, vector in zip(chunks, vectors):
            db.add(
                Chunk(
                    document_id=document_id,
                    content=chunk.text,
                    page=chunk.page,
                    ordinal=chunk.ordinal,
                    embedding=vector,
                )
            )
        await db.commit()


async def _ingest_one(document_id: UUID, upload: Upload) -> bool:
    """Extract, chunk, embed and store one document. Returns success."""
    await _mark_document(document_id, DocumentStatus.PROCESSING)

    try:
        extracted = await extract_pdf(upload.data)
        chunks = chunk_document(extracted)

        if not chunks:
            raise ValidationError("No extractable text; the file may be a scan")

        vectors = await get_embedder().embed_texts([chunk.text for chunk in chunks])

        await _persist_chunks(document_id, chunks, vectors)
        await _mark_document(document_id, DocumentStatus.READY, page_count=extracted.page_count)

        logger.info("Ingested %s: %d pages, %d chunks", upload.filename, extracted.page_count, len(chunks))
        return True

    except Exception as exc:
        logger.exception("Ingestion failed for %s", upload.filename)
        await _mark_document(document_id, DocumentStatus.FAILED, error=str(exc))
        return False


async def run_job(job_id: UUID, queued: Sequence[QueuedDocument]) -> None:
    """Process an upload batch. Runs as a background task, owns its sessions."""
    await _mark_job(job_id, IngestionStatus.PROCESSING)

    succeeded = 0
    for item in queued:
        ok = await _ingest_one(item.document_id, item.upload)
        succeeded += ok
        await _record_progress(job_id, succeeded=ok)

    final = IngestionStatus.COMPLETED if succeeded else IngestionStatus.FAILED
    await _mark_job(job_id, final)
