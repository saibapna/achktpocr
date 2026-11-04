from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.security import require_api_key
from app.preprocessing.image_loader import ImageValidationError, validate_image

router = APIRouter()


@router.get("/models", summary="Active model metadata")
async def models() -> dict[str, object]:
    return {
        "detector": {"name": None, "version": None, "status": "not_configured"},
        "ocr_engine": {"name": None, "version": None, "status": "not_configured"},
    }


@router.post("/ocr/ktp", summary="Extract fields from one KTP-el image")
async def ocr_ktp(
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
) -> None:
    settings = get_settings()
    data = await file.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "UPLOAD_TOO_LARGE", "message": "Image exceeds the configured size limit."},
        )
    try:
        validate_image(data, max_dimension=settings.max_image_dimension)
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMAGE", "message": str(exc)},
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "MODEL_NOT_CONFIGURED",
            "message": "OCR inference is not enabled in this foundation release.",
        },
    )
