"""The chunks resource: read-only, and what every citation points at."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE, Page, PaginationDep, paginate
from ....infrastructure.http.conditional import apply_read_conditions
from ....infrastructure.http.problem import ProblemDetail
from ....modules.chunk.schemas import ChunkRead
from ..dependencies import ChunkServiceDep, DbSession, DocumentServiceDep, OwnerDep

router = APIRouter(tags=["Chunks"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetail, "content": {PROBLEM_CONTENT_TYPE: {}}}
}


@router.get(
    "/documents/{document_id}/chunks",
    response_model=Page[ChunkRead],
    responses=_NOT_FOUND,
    summary="List a document's chunks",
)
async def list_document_chunks(
    document_id: UUID,
    request: Request,
    response: Response,
    page: PaginationDep,
    documents: DocumentServiceDep,
    chunks: ChunkServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> Page[ChunkRead]:
    """Return one page of chunks in document order.

    Useful for seeing how a document was split, which is otherwise invisible.
    """
    await documents.get(document_id, owner, db)
    items, total = await chunks.list_for_document(document_id, owner, db, limit=page.limit, offset=page.offset)
    return paginate(request, response, items, total, page)


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkRead,
    responses=_NOT_FOUND,
    summary="Get a chunk",
)
async def get_chunk(
    chunk_id: UUID,
    request: Request,
    response: Response,
    chunks: ChunkServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> ChunkRead | Response:
    """Return one chunk with its source page.

    Every citation in an answer carries a chunk id; this is where it resolves.
    A chunk never changes once written, so its `ETag` is stable for its life.
    """
    chunk = await chunks.get(chunk_id, owner, db)

    not_modified = apply_read_conditions(request, response, chunk)
    return not_modified or chunk
