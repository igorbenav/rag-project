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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.config.settings import get_settings
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
from .models import IngestionJob, IngestionStatus, UploadBlob
from .pdf import extract_pdf, looks_like_pdf

logger = get_logger(__name__)


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


async def already_ingested(collection_id: UUID, checksums: Sequence[str], db: AsyncSession) -> set[str]:
    """Checksums the collection already holds as a ready document.

    An idempotency key protects against a retried request; this protects
    against the same file being uploaded twice, which is a different event with
    the same cost — the chunks appear twice and both copies compete in the
    index.
    """
    if not checksums:
        return set()

    rows = await db.execute(
        select(Document.checksum).where(
            Document.collection_id == collection_id,
            Document.checksum.in_(list(checksums)),
            Document.status == DocumentStatus.READY,
        )
    )
    return set(rows.scalars())


async def create_job(collection_id: UUID, uploads: Sequence[Upload], db: AsyncSession) -> tuple[IngestionJob, List[UUID]]:
    """Record the job, its documents, and the bytes each one still needs.

    The bytes are stored rather than passed along: the worker is a separate
    process, and a file that only exists in a queue message is lost the moment
    the queue is drained or the worker dies mid-document.
    """
    job = IngestionJob(collection_id=collection_id, total_documents=len(uploads))
    db.add(job)

    await db.flush()

    seen = await already_ingested(collection_id, [upload.checksum for upload in uploads], db)

    document_ids: List[UUID] = []
    for upload in uploads:
        if upload.checksum in seen:
            logger.info("Skipping %s: already ingested in this collection", upload.filename)
            continue

        document = Document(
            collection_id=collection_id,
            filename=upload.filename,
            checksum=upload.checksum,
            status=DocumentStatus.PENDING,
            ingestion_job_id=job.id,
        )
        db.add(document)
        await db.flush()
        db.add(UploadBlob(document_id=document.id, data=upload.data))
        document_ids.append(document.id)

    job.total_documents = len(document_ids)
    await db.commit()
    return job, document_ids


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


async def _record_progress(document_id: UUID, *, succeeded: bool) -> None:
    async with local_session() as db:
        document = await db.get(Document, document_id)
        if document is None or document.ingestion_job_id is None:
            return
        job = await db.get(IngestionJob, document.ingestion_job_id)
        if job is None:
            return
        if succeeded:
            job.completed_documents += 1
        else:
            job.failed_documents += 1
        job.status = IngestionStatus.PROCESSING
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
                    embedding_model=get_settings().MISTRAL_EMBED_MODEL,
                )
            )
        await db.commit()


async def _load_upload(document_id: UUID) -> tuple[str, bytes] | None:
    async with local_session() as db:
        document = await db.get(Document, document_id)
        blob = await db.get(UploadBlob, document_id)
        if document is None or blob is None:
            return None
        return document.filename, blob.data


async def _discard_upload(document_id: UUID) -> None:
    """Drop the stored bytes once they are no longer needed."""
    async with local_session() as db:
        blob = await db.get(UploadBlob, document_id)
        if blob is not None:
            await db.delete(blob)
            await db.commit()


async def _replace_chunks(document_id: UUID, chunks: Sequence[TextChunk], vectors: Sequence[List[float]]) -> None:
    """Write a document's chunks, clearing any from an earlier attempt.

    A retry re-ingests the same document, so this has to be idempotent.
    """
    async with local_session() as db:
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        for chunk, vector in zip(chunks, vectors):
            db.add(
                Chunk(
                    document_id=document_id,
                    content=chunk.text,
                    page=chunk.page,
                    ordinal=chunk.ordinal,
                    embedding=vector,
                    embedding_model=get_settings().MISTRAL_EMBED_MODEL,
                )
            )
        await db.commit()


async def ingest_document(document_id: UUID) -> bool:
    """Extract, chunk, embed and store one document. Returns success.

    No session is held across extraction or embedding: the first is CPU work in
    a worker thread and the second is a network round trip per batch, and a
    connection held across either can be reaped by the database mid-job.
    """
    loaded = await _load_upload(document_id)
    if loaded is None:
        logger.warning("No stored upload for document %s; nothing to ingest", document_id)
        return False

    filename, data = loaded
    await _mark_document(document_id, DocumentStatus.PROCESSING)

    try:
        extracted = await extract_pdf(data)
        chunks = chunk_document(extracted)

        if not chunks:
            raise ValidationError("No extractable text; the file may be a scan")

        vectors = await get_embedder().embed_texts([chunk.text for chunk in chunks])

        await _replace_chunks(document_id, chunks, vectors)
        await _mark_document(document_id, DocumentStatus.READY, page_count=extracted.page_count)
        await _discard_upload(document_id)
        await _record_progress(document_id, succeeded=True)

        logger.info("Ingested %s: %d pages, %d chunks", filename, extracted.page_count, len(chunks))
        return True

    except Exception as exc:
        logger.exception("Ingestion failed for %s", filename)
        await _mark_document(document_id, DocumentStatus.FAILED, error=str(exc))
        await _record_progress(document_id, succeeded=False)
        raise


async def mark_job_finished(job_id: UUID) -> None:
    """Close the job once every document has reported a result."""
    async with local_session() as db:
        job = await db.get(IngestionJob, job_id)
        if job is None:
            return

        if job.completed_documents + job.failed_documents < job.total_documents:
            return

        job.status = IngestionStatus.COMPLETED if job.completed_documents else IngestionStatus.FAILED
        await db.commit()


async def find_unfinished_documents() -> List[tuple[UUID, UUID]]:
    """Documents whose bytes are still stored, so ingestion never finished.

    A stored blob is the marker: it is deleted the moment a document succeeds,
    so anything still holding one was interrupted.
    """
    async with local_session() as db:
        result = await db.execute(
            select(Document.id, Document.ingestion_job_id)
            .join(UploadBlob, UploadBlob.document_id == Document.id)
            .where(Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]))
        )
        return [(row[0], row[1]) for row in result.all() if row[1] is not None]
