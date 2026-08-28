"""Shared test fixtures.

Tests run against a real PostgreSQL container: the schema uses UUID primary
keys, a native enum, and a float array, none of which SQLite can stand in for.
"""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("CREATE_TABLES_ON_STARTUP", "false")
os.environ.setdefault("API_KEY_REQUIRED", "false")
# The suite fires far more requests than a real client would, through a single
# in-process bucket. Both are exercised by their own tests instead.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Ryuk needs to bind-mount the docker socket, which Docker Desktop's
# ~/.docker/run/docker.sock does not support. The context manager cleans up.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# mypy: disable-error-code="import-untyped"
from src.infrastructure.database.session import Base, async_session  # noqa: E402
from src.interfaces.main import app  # noqa: E402
from src.modules import registry  # noqa: E402,F401  (registers models on Base.metadata)
from testcontainers.community.postgres import PostgresContainer  # noqa: E402
from testcontainers.core.docker_client import DockerClient  # noqa: E402


def _docker_available() -> bool:
    try:
        DockerClient()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_container():
    if not _docker_available():
        pytest.skip("Docker is required to run integration tests")
    with PostgresContainer("postgres:16") as container:
        yield container


@pytest_asyncio.fixture
async def engine(postgres_container):
    """A fresh schema per test, so ordering never matters."""
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client bound to the test database.

    ASGITransport does not run the lifespan, so the application never touches
    the engine configured from real settings.
    """
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[async_session] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
