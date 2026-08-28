from fastapi import APIRouter

from .collections import router as collections_router
from .documents import router as documents_router
from .ingestions import router as ingestions_router

router = APIRouter(prefix="/v1")
router.include_router(collections_router)
router.include_router(documents_router)
router.include_router(ingestions_router)

__all__ = ["router"]
