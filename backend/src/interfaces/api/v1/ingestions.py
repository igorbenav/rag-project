"""The ingestion job resource: what a client polls after uploading."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE
from ....infrastructure.http.conditional import apply_read_conditions
from ....infrastructure.http.problem import ProblemDetail
from ....modules.ingestion.schemas import IngestionJobRead
from ..dependencies import DbSession, IngestionServiceDep

router = APIRouter(prefix="/ingestions", tags=["Ingestion"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetail, "content": {PROBLEM_CONTENT_TYPE: {}}}
}


@router.get(
    "/{ingestion_id}",
    response_model=IngestionJobRead,
    responses=_NOT_FOUND,
    summary="Get ingestion progress",
)
async def get_ingestion(
    ingestion_id: UUID,
    request: Request,
    response: Response,
    ingestions: IngestionServiceDep,
    db: DbSession,
) -> IngestionJobRead | Response:
    """Return the job's progress and the documents it produced.

    Clients poll this while a document processes, and most polls find nothing
    changed. `If-None-Match` turns those into a 304 with no body.
    """
    job = await ingestions.get(ingestion_id, db)

    not_modified = apply_read_conditions(request, response, job)
    return not_modified or job
