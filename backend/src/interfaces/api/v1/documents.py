"""The documents resource. Uploading here is what ingests a PDF."""

from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, File, Request, Response, UploadFile, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE, Page, PaginationDep, paginate
from ....infrastructure.http.conditional import apply_read_conditions
from ....infrastructure.http.idempotency import idempotency_key, idempotency_store
from ....infrastructure.http.problem import ProblemDetail
from ....modules.common.exceptions import UnsupportedMediaTypeError
from ....modules.document.schemas import DocumentRead
from ....modules.ingestion.schemas import IngestionJobRead
from ....modules.ingestion.service import create_job, partition_uploads
from ....modules.ingestion.tasks import ingest_document_task
from ..dependencies import CollectionServiceDep, DbSession, DocumentServiceDep

router = APIRouter(tags=["Documents"])

_PROBLEM: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetail, "content": {PROBLEM_CONTENT_TYPE: {}}},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
        "model": ProblemDetail,
        "description": "A file was not a PDF.",
        "content": {PROBLEM_CONTENT_TYPE: {}},
    },
}


@router.post(
    "/collections/{collection_id}/documents",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestionJobRead,
    responses=_PROBLEM,
    summary="Ingest one or more PDFs",
)
async def ingest_documents(
    collection_id: UUID,
    request: Request,
    response: Response,
    collections: CollectionServiceDep,
    db: DbSession,
    files: List[UploadFile] = File(..., description="One or more PDF files."),
) -> IngestionJobRead:
    """Accept PDFs and return the job that will process them.

    Extraction and embedding take longer than a request should stay open, so
    each file becomes a queued task and `Location` points at the job rather
    than a result.

    A file that cannot be ingested does not sink the request: it is recorded on
    the job as a failed document with the reason, and the rest proceed. Only a
    request where nothing is usable is rejected outright.
    """
    await collections.get(collection_id, db)

    uploads, rejected = partition_uploads([(f.filename or "upload.pdf", f.content_type or "", await f.read()) for f in files])

    if not uploads:
        raise UnsupportedMediaTypeError("; ".join(f"{r.filename}: {r.reason}" for r in rejected))

    key = idempotency_key(request)
    fingerprint = ",".join(sorted(upload.checksum for upload in uploads))
    if key:
        replayed: IngestionJobRead | None = idempotency_store.get(key, fingerprint)
        if replayed is not None:
            response.headers["Location"] = f"/api/v1/ingestions/{replayed.id}"
            return replayed

    job, document_ids = await create_job(collection_id, uploads, db, rejected)
    for document_id in document_ids:
        await ingest_document_task.kiq(str(document_id), str(job.id))

    response.headers["Location"] = f"/api/v1/ingestions/{job.id}"
    read = IngestionJobRead.model_validate(job)

    if key:
        idempotency_store.put(key, fingerprint, read)

    return read


@router.get(
    "/collections/{collection_id}/documents",
    response_model=Page[DocumentRead],
    responses=_PROBLEM,
    summary="List documents in a collection",
)
async def list_documents(
    collection_id: UUID,
    request: Request,
    response: Response,
    page: PaginationDep,
    collections: CollectionServiceDep,
    documents: DocumentServiceDep,
    db: DbSession,
) -> Page[DocumentRead]:
    """Return one page of the collection's documents, newest first."""
    await collections.get(collection_id, db)
    items, total = await documents.list(collection_id, db, limit=page.limit, offset=page.offset)
    return paginate(request, response, items, total, page)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    responses=_PROBLEM,
    summary="Get a document",
)
async def get_document(
    document_id: UUID,
    request: Request,
    response: Response,
    documents: DocumentServiceDep,
    db: DbSession,
) -> DocumentRead | Response:
    """Return one document, including its ingestion status and chunk count."""
    document = await documents.get(document_id, db)

    not_modified = apply_read_conditions(request, response, document)
    return not_modified or document


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_PROBLEM,
    summary="Delete a document",
)
async def delete_document(
    document_id: UUID,
    documents: DocumentServiceDep,
    db: DbSession,
) -> None:
    """Delete a document and the chunks derived from it."""
    await documents.delete(document_id, db)
