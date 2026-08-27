"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database import async_session
from ...modules.collection.services import CollectionService

DbSession = Annotated[AsyncSession, Depends(async_session)]


def get_collection_service() -> CollectionService:
    return CollectionService()


CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
