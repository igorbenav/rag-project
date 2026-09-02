"""The collections resource."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE, Page, PaginationDep, paginate
from ....infrastructure.http.conditional import apply_read_conditions, etag_for, require_if_match
from ....infrastructure.http.problem import ProblemDetail
from ....modules.collection.schemas import CollectionCreate, CollectionRead, CollectionUpdate
from ..dependencies import CollectionServiceDep, DbSession, OwnerDep

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
    owner: OwnerDep,
    db: DbSession,
) -> CollectionRead:
    """Create a collection and return it, with its URL in `Location`."""
    collection = await service.create(body, owner, db)
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
    owner: OwnerDep,
    db: DbSession,
) -> Page[CollectionRead]:
    """Return one page of collections, newest first."""
    items, total = await service.list(owner, db, limit=page.limit, offset=page.offset)
    return paginate(request, response, items, total, page)


@router.get(
    "/{collection_id}",
    response_model=CollectionRead,
    responses=_NOT_FOUND,
    summary="Get a collection",
)
async def get_collection(
    collection_id: UUID,
    request: Request,
    response: Response,
    service: CollectionServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> CollectionRead | Response:
    """Return one collection, with its document and chunk totals.

    Carries an `ETag`. A client that sends it back as `If-None-Match` gets
    `304` and no body.
    """
    collection = await service.get(collection_id, owner, db)

    not_modified = apply_read_conditions(request, response, collection)
    return not_modified or collection


@router.patch(
    "/{collection_id}",
    response_model=CollectionRead,
    responses=_NOT_FOUND,
    summary="Update a collection",
)
async def update_collection(
    collection_id: UUID,
    body: CollectionUpdate,
    request: Request,
    response: Response,
    service: CollectionServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> CollectionRead:
    """Apply a partial update.

    Honours `If-Match`: send the `ETag` you read and the update is rejected
    with `412` if the collection changed in between, rather than overwriting
    whatever it changed to.
    """
    current = await service.get(collection_id, owner, db)
    require_if_match(request, current)

    updated = await service.update(collection_id, body, owner, db)
    response.headers["ETag"] = etag_for(updated)
    return updated


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_NOT_FOUND,
    summary="Delete a collection",
)
async def delete_collection(
    collection_id: UUID,
    request: Request,
    service: CollectionServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> None:
    """Delete a collection along with its documents and chunks.

    Honours `If-Match`, so a client can refuse to delete something that
    changed since it last looked.
    """
    current = await service.get(collection_id, owner, db)
    require_if_match(request, current)

    await service.delete(collection_id, owner, db)
