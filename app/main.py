from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    docs_enabled = get_settings().env != "production"
    application = FastAPI(
        title="aceh-ktp-ocr",
        description="Standalone KTP-el OCR API; not proof of identity or document authenticity.",
        version="0.2.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.include_router(api_router)
    return application


app = create_app()
