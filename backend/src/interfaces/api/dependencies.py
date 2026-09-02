"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.config.settings import get_settings
from ...infrastructure.database import async_session
from ...infrastructure.http.problem import ProblemException
from ...modules.chunk.services import ChunkService
from ...modules.collection.ownership import OwnerId
from ...modules.collection.services import CollectionService
from ...modules.document.services import DocumentService
from ...modules.ingestion.services import IngestionService
from ...modules.query.service import QueryService

DbSession = Annotated[AsyncSession, Depends(async_session)]


def get_owner_id(request: Request) -> OwnerId:
    """The key that authenticated this request, or None when auth is off.

    `require_api_key` runs first as a router-level dependency and puts the id
    here. None therefore means authentication is disabled — and because None
    scopes to everything, it has to be refused when it is not. A router
    registered without that dependency would otherwise serve every key's data
    to an anonymous caller, and nothing about the response would look wrong.
    """
    owner: OwnerId = getattr(request.state, "api_key_id", None)
    if owner is None and get_settings().API_KEY_REQUIRED:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "This request was never authenticated.")
    return owner


def get_chunk_service() -> ChunkService:
    return ChunkService()


def get_collection_service() -> CollectionService:
    return CollectionService()


def get_document_service() -> DocumentService:
    return DocumentService()


def get_ingestion_service() -> IngestionService:
    return IngestionService()


def get_query_service() -> QueryService:
    return QueryService()


OwnerDep = Annotated[OwnerId, Depends(get_owner_id)]

ChunkServiceDep = Annotated[ChunkService, Depends(get_chunk_service)]
CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
