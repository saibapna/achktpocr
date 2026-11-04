from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.engines.rapidocr_engine import engine_available

router = APIRouter()


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", summary="OCR dependency readiness")
async def readiness() -> JSONResponse:
    if get_settings().ocr_enabled and engine_available():
        return JSONResponse(status_code=200, content={"status": "ready", "ocr_enabled": True})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "reason": "MODEL_NOT_CONFIGURED", "ocr_enabled": False},
    )
