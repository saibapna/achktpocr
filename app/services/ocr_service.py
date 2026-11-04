"""Return only structured fields extracted from actual OCR output."""

from time import perf_counter
from uuid import uuid4

from app.engines.rapidocr_engine import OCREngine, engine_available, get_engine
from app.extraction.ktp_parser import parse_ktp_lines
from app.schemas.response import KTPFields, OCRResponse


class ModelNotConfiguredError(RuntimeError):
    """Required OCR runtime or model has not been configured."""


def process_ktp(image: bytes, *, engine: OCREngine | None = None) -> OCRResponse:
    started = perf_counter()
    if engine is None:
        if not engine_available():
            raise ModelNotConfiguredError("RapidOCR and ONNX Runtime are not installed")
        engine = get_engine()
    lines = engine.read(image)
    fields, kind, warnings = parse_ktp_lines(lines)
    data = {name: getattr(fields, name).value for name in KTPFields.model_fields}
    required = ("nik", "nama", "tanggal_lahir", "alamat")
    if kind == "unknown" or not any(data.values()):
        state = "failed"
    elif all(data[name] for name in required) and fields.nik.validation == "passed":
        state = "success"
    else:
        state = "partial"
    return OCRResponse(
        request_id=str(uuid4()),
        status=state,
        document_type=kind,  # type: ignore[arg-type]
        data=data,
        fields=fields,
        warnings=warnings,
        processing={"total_ms": round((perf_counter() - started) * 1000, 2), "lines": len(lines)},
        model_version="rapidocr-onnx-default",
    )
