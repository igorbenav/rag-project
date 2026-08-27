"""ASGI entrypoint. Routers are mounted here as each resource is built."""

from fastapi import APIRouter

from ..infrastructure.app_factory import create_application
from ..infrastructure.config.settings import get_settings

settings = get_settings()

router = APIRouter()


@router.get("/health", tags=["Health"], summary="Liveness probe")
async def health() -> dict[str, str]:
    """Report that the process is up.

    Does not touch the database: this backs the container healthcheck, and a
    Postgres blip should not restart a healthy web process.
    """
    return {"status": "ok"}


app = create_application(router=router, settings=settings)
