"""The queries resource. Asking a question creates one."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE, Page, PaginationDep, paginate
from ....infrastructure.http.conditional import apply_read_conditions
from ....infrastructure.http.problem import ProblemDetail
from ....modules.query.schemas import QueryCreate, QueryRead
from ....modules.retrieval.config import RetrievalConfig
from ..dependencies import CollectionServiceDep, DbSession, OwnerDep, QueryServiceDep

router = APIRouter(tags=["Queries"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetail, "content": {PROBLEM_CONTENT_TYPE: {}}}
}


@router.post(
    "/collections/{collection_id}/queries",
    status_code=status.HTTP_201_CREATED,
    response_model=QueryRead,
    responses=_NOT_FOUND,
    summary="Ask a question",
)
async def create_query(
    collection_id: UUID,
    body: QueryCreate,
    response: Response,
    collections: CollectionServiceDep,
    queries: QueryServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> QueryRead:
    """Answer a question from the collection's documents.

    Returns `201` with the answer, its citations, and the retrieval trace. The
    query stays readable afterwards at the URL in `Location`, so an answer can
    be revisited or shared without asking the model again.

    Synchronous, unlike ingestion: a question is a handful of model calls and
    seconds of work, so a job resource would add a poll loop for no benefit.
    """
    await collections.get(collection_id, owner, db)

    query = await queries.ask(collection_id, body, RetrievalConfig.from_settings(), db)
    response.headers["Location"] = f"/api/v1/queries/{query.id}"
    return QueryRead.from_model(query)


@router.get(
    "/collections/{collection_id}/queries",
    response_model=Page[QueryRead],
    responses=_NOT_FOUND,
    summary="List past questions",
)
async def list_queries(
    collection_id: UUID,
    request: Request,
    response: Response,
    page: PaginationDep,
    collections: CollectionServiceDep,
    queries: QueryServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> Page[QueryRead]:
    """Return one page of the collection's query history, newest first."""
    await collections.get(collection_id, owner, db)
    items, total = await queries.list_for_collection(collection_id, owner, db, limit=page.limit, offset=page.offset)
    return paginate(request, response, items, total, page)


@router.get(
    "/queries/{query_id}",
    response_model=QueryRead,
    responses=_NOT_FOUND,
    summary="Get a stored answer",
)
async def get_query(
    query_id: UUID,
    request: Request,
    response: Response,
    queries: QueryServiceDep,
    owner: OwnerDep,
    db: DbSession,
) -> QueryRead | Response:
    """Return a previous answer, without calling the model again.

    A stored answer is immutable, so its `ETag` never changes.
    """
    query = await queries.get(query_id, owner, db)

    not_modified = apply_read_conditions(request, response, query)
    return not_modified or query
