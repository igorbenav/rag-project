"""Application factory: build a configured FastAPI instance from settings."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Optional

import anyio
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config.settings import EnvironmentOption, Settings, get_settings
from .database.session import create_tables
from .http import register_exception_handlers
from .logging import get_logger
from .mistral.client import close_client

logger = get_logger(__name__)

DEFAULT_THREADPOOL_TOKENS = 100


async def set_threadpool_tokens(number_of_tokens: int = DEFAULT_THREADPOOL_TOKENS) -> None:
    """Widen anyio's thread limiter.

    PDF parsing is synchronous and runs via `to_thread`; the default 40 tokens
    would cap concurrent ingestion.
    """
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = number_of_tokens


def lifespan_factory(
    settings: Settings,
    create_tables_on_startup: bool = True,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build the default lifespan: widen the threadpool, then ensure tables."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await set_threadpool_tokens()

        if create_tables_on_startup:
            await create_tables()
            logger.info("Database tables ensured")

        try:
            yield
        finally:
            await close_client()

    return lifespan


def create_application(
    router: APIRouter,
    settings: Optional[Settings] = None,
    lifespan: Optional[Callable[[FastAPI], AbstractAsyncContextManager[None]]] = None,
    **kwargs: Any,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        router: Router carrying the application's routes.
        settings: Settings to build from. Defaults to the module singleton.
        lifespan: Overrides the default lifespan; mainly useful in tests.
        **kwargs: Passed through to `FastAPI`, and overriding anything derived
            from settings.

    Returns:
        A configured FastAPI application.
    """
    settings = settings or get_settings()

    hide_docs = settings.ENVIRONMENT == EnvironmentOption.PRODUCTION and not settings.ENABLE_DOCS_IN_PRODUCTION

    metadata: dict[str, Any] = {
        "title": settings.APP_NAME,
        "description": settings.APP_DESCRIPTION,
        "version": settings.VERSION,
        "docs_url": None if hide_docs else "/docs",
        "redoc_url": None if hide_docs else "/redoc",
        "openapi_url": None if hide_docs else "/openapi.json",
    }
    metadata.update(kwargs)

    if lifespan is None:
        lifespan = lifespan_factory(settings, create_tables_on_startup=settings.CREATE_TABLES_ON_STARTUP)

    application = FastAPI(lifespan=lifespan, **metadata)
    register_exception_handlers(application)
    application.include_router(router)

    if settings.CORS_ENABLED:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS_LIST,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS.split(","),
            allow_headers=settings.CORS_ALLOW_HEADERS.split(","),
        )

    if settings.GZIP_ENABLED:
        application.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MINIMUM_SIZE)

    return application
