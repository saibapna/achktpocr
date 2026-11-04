"""Bounded authenticated KTP OCR endpoint."""

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.security import require_api_key
from app.engines.rapidocr_engine import engine_available
from app.preprocessing.image_loader import ImageValidationError, prepare_image
from app.schemas.response import OCRResponse
from app.services.ocr_service import ModelNotConfiguredError, process_ktp

router = APIRouter()
_INFER_LIMIT = asyncio.Semaphore(1)


@router.get("/models", summary="Active model metadata")
async def models() -> dict[str, object]:
    active = get_settings().ocr_enabled and engine_available()
    return {
        "detector": {"name": None, "version": None, "status": "not_required_for_baseline"},
        "ocr_engine": {
            "name": "rapidocr" if active else None,
            "version": "onnx-default" if active else None,
            "status": "available" if active else "not_configured",
        },
    }


@router.post("/ocr/ktp", response_model=OCRResponse, summary="Extract KTP-el fields")
async def ocr_ktp(
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
) -> OCRResponse:
    settings = get_settings()
    try:
        data = await file.read(settings.upload_max_bytes + 1)
    finally:
        await file.close()
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "UPLOAD_TOO_LARGE", "message": "Image exceeds the configured size limit."},
        )
    try:
        prepared = prepare_image(
            data,
            max_dimension=settings.max_image_dimension,
            max_pixels=settings.max_image_pixels,
            max_side=settings.ocr_max_side,
        )
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMAGE", "message": str(exc)},
        ) from None
    if not settings.ocr_enabled or not engine_available():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "OCR runtime is unavailable."},
        )
    try:
        async with _INFER_LIMIT:
            return await run_in_threadpool(process_ktp, prepared)
    except ModelNotConfiguredError:
        raise HTTPException(
            status_code=501,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "OCR runtime is unavailable."},
        ) from None
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "OCR_UNAVAILABLE", "message": "OCR processing is temporarily unavailable."},
        ) from None
