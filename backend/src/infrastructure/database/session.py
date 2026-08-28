"""Async engine, session factory, and the declarative base."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from ..config.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_SQL_QUERIES,
    future=True,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
)

local_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase, MappedAsDataclass):
    """Declarative base. `MappedAsDataclass` generates `__init__`/`__repr__`/`__eq__`."""


async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session that closes with the request."""
    async with local_session() as db:
        yield db


async def create_tables() -> None:
    """Create any table that does not yet exist. Alembic replaces this in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
