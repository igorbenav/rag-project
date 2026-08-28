"""The collections resource."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE, Page, PaginationDep, paginate
from ....infrastructure.http.problem import ProblemDetail
from ....modules.collection.schemas import CollectionCreate, CollectionRead
from ..dependencies import CollectionServiceDep, DbSession

router = APIRouter(prefix="/collections", tags=["Collections"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ProblemDetail,
        "description": "No collection with that id.",
        "content": {PROBLEM_CONTENT_TYPE: {}},
    }
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CollectionRead,
    summary="Create a collection",
)
async def create_collection(
    body: CollectionCreate,
    response: Response,
    service: CollectionServiceDep,
    db: DbSession,
) -> CollectionRead:
    """Create a collection and return it, with its URL in `Location`."""
    collection = await service.create(body, db)
    response.headers["Location"] = f"/api/v1/collections/{collection.id}"
    return collection


@router.get(
    "",
    response_model=Page[CollectionRead],
    summary="List collections",
)
async def list_collections(
    request: Request,
    response: Response,
    page: PaginationDep,
    service: CollectionServiceDep,
    db: DbSession,
) -> Page[CollectionRead]:
    """Return one page of collections, newest first."""
    items, total = await service.list(db, limit=page.limit, offset=page.offset)
    return paginate(request, response, items, total, page)


@router.get(
    "/{collection_id}",
    response_model=CollectionRead,
    responses=_NOT_FOUND,
    summary="Get a collection",
)
async def get_collection(
    collection_id: UUID,
    service: CollectionServiceDep,
    db: DbSession,
) -> CollectionRead:
    """Return one collection, with its document and chunk totals."""
    return await service.get(collection_id, db)


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_NOT_FOUND,
    summary="Delete a collection",
)
async def delete_collection(
    collection_id: UUID,
    service: CollectionServiceDep,
    db: DbSession,
) -> None:
    """Delete a collection along with its documents and chunks."""
    await service.delete(collection_id, db)
