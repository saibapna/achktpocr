from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.ocr import router as ocr_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(ocr_router, prefix="/v1", tags=["ocr"])
