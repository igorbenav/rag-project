"""ASGI entrypoint. Routers are mounted here as each resource is built."""

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from ..infrastructure.app_factory import create_application
from ..infrastructure.config.settings import get_settings
from ..modules import registry  # noqa: F401  (registers models on Base.metadata)
from .api import router as api_router
from .ui import router as ui_router
from .ui.router import STATIC_DIR

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
app.include_router(api_router)
app.include_router(ui_router)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
