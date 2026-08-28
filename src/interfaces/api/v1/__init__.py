from fastapi import APIRouter, Depends

from ....infrastructure.security import require_api_key
from .chunks import router as chunks_router
from .collections import router as collections_router
from .documents import router as documents_router
from .ingestions import router as ingestions_router
from .queries import router as queries_router

# Applied once at include time rather than on each route: a new endpoint
# is authenticated by default instead of by remembering to say so.
router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])
router.include_router(collections_router)
router.include_router(documents_router)
router.include_router(chunks_router)
router.include_router(ingestions_router)
router.include_router(queries_router)

__all__ = ["router"]
