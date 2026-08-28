"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database import async_session
from ...modules.chunk.services import ChunkService
from ...modules.collection.services import CollectionService
from ...modules.document.services import DocumentService
from ...modules.ingestion.services import IngestionService
from ...modules.query.service import QueryService

DbSession = Annotated[AsyncSession, Depends(async_session)]


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


ChunkServiceDep = Annotated[ChunkService, Depends(get_chunk_service)]
CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
