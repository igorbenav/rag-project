"""Serves the built React client.

The bundle lives outside `src/` because docker-compose mounts `./src` over the
image's copy for hot reload, which would shadow anything built into it. In the
container it is at /code/static; locally it is frontend/dist, where Vite writes
it.

The page talks to the same public API a script would, so nothing it does
depends on a private endpoint: if the UI can do it, the documented contract can.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from ...infrastructure.config.settings import get_settings

router = APIRouter(tags=["UI"], include_in_schema=False)

_CONTAINER_PATH = Path("/code/static")
_LOCAL_PATH = Path(__file__).resolve().parents[4] / "frontend" / "dist"

STATIC_DIR = (
    Path(get_settings().STATIC_DIR)
    if get_settings().STATIC_DIR
    else (_CONTAINER_PATH if _CONTAINER_PATH.exists() else _LOCAL_PATH)
)

_NOT_BUILT = """<!doctype html><html><body style="font-family:system-ui;padding:3rem">
<h1>The interface has not been built</h1>
<p>Run <code>docker compose up --build</code>, or <code>npm --prefix frontend run build</code>.</p>
<p>The API is unaffected — see <a href="/docs">/docs</a>.</p>
</body></html>"""


@router.get("/", response_model=None)
async def index() -> FileResponse | HTMLResponse:
    """The chat interface, or an explanation if it was never built."""
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return HTMLResponse(_NOT_BUILT, status_code=200)
    return FileResponse(page)
