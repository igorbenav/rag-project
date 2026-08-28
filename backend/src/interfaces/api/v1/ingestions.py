"""The ingestion job resource: what a client polls after uploading."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from ....infrastructure.http import PROBLEM_CONTENT_TYPE
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
    ingestions: IngestionServiceDep,
    db: DbSession,
) -> IngestionJobRead:
    """Return the job's progress and the documents it produced."""
    return await ingestions.get(ingestion_id, db)
