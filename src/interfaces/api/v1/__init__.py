from fastapi import APIRouter

from .collections import router as collections_router

router = APIRouter(prefix="/v1")
router.include_router(collections_router)

__all__ = ["router"]
