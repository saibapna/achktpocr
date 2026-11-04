# aceh-ktp-ocr

Standalone REST API for Indonesian KTP-el OCR using a hybrid computer-vision pipeline: YOLO field detection + pluggable OCR engines.

> **Status:** Foundation / early MVP. Model accuracy has not been benchmarked yet. This repository does not verify identity against Dukcapil and must not be presented as an official identity-verification service.

## Product decisions

- Product: standalone API consumed by multiple applications.
- Architecture: Python modular monolith with FastAPI.
- Detection: YOLO for document/field localization.
- OCR: adapter-based engine selection; PaddleOCR is the initial candidate, Tesseract is a comparator/fallback candidate.
- Image processing: OpenCV + Pillow.
- Validation: field-specific rules and Pydantic schemas.
- Runtime: Docker; CPU-first baseline.
- Storage: no permanent image storage by default.
- API version: /v1.

## Pipeline

upload validation → preprocessing → document/field detection → field crops → OCR → extraction → validation/confidence → JSON response

If one or more fields cannot be detected or read, return a partial result with null values and warnings. Do not fabricate missing identity data.

## Repository layout

~~~text
app/
  api/                 HTTP routes, dependencies
  core/                settings, lifecycle, security, logging
  detection/            YOLO document/field detector adapters
  preprocessing/        image loading, orientation, enhancement
  engines/              pluggable OCR engines
  extraction/           field-specific normalization/parsing
  validation/           KTP field and consistency checks
  schemas/              request and response contracts
  services/             pipeline orchestration and confidence
tests/
  unit/ integration/ security/ benchmark/
docs/                   architecture, API, security, model card
models/                 model manifest only; weights are not committed
datasets/               empty local data folders; never commit real KTPs
scripts/                benchmark and dataset utilities
~~~

## Quick start

Python 3.11+ is recommended.

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
~~~

OpenAPI docs: http://127.0.0.1:8000/docs

Docker:

~~~bash
docker compose up --build
~~~

The initial foundation exposes health endpoints and an OCR contract. OCR inference returns a controlled 501 until detector and OCR models are configured; the scaffold does not pretend to recognize documents before a validated model is added.

## API

- GET /health/live
- GET /health/ready
- GET /v1/models
- POST /v1/ocr/ktp (multipart field: file; requires API key)

See docs/api-spec.md.

## Development

~~~bash
pytest
ruff check .
mypy app
~~~

Benchmark before selecting production models. Track NIK exact match, name/date exact match, per-field accuracy, CER/WER, detector mAP, field recall, invalid-document false positives, P95 latency, memory, and failure rate. Confidence values from the OCR engine are not calibrated probabilities by default.

## Security and privacy

- Treat KTP images, NIK, and OCR output as sensitive personal data.
- Never commit real KTP images, ground-truth identity labels, API keys, service-account files, or .env.
- Logs must not contain image bytes, NIK, names, or raw OCR text.
- Temporary uploads must be removed after processing.
- Keep datasets local/private with lawful basis, access control, retention limits, and human-reviewed annotation.
- API key values are provided through environment variables; only hashes should be stored by any future key-management component.
- This API performs OCR and syntactic/consistency checks only. It does not establish document authenticity or identity ownership.

## Implementation stages

1. Project foundation and secure defaults.
2. Lawfully sourced dataset, annotation guide, ground truth, and reproducible benchmarks.
3. Preprocessing and quality assessment.
4. YOLO document/field detector.
5. OCR engine adapters and benchmark-based engine selection.
6. Extraction, validation, confidence, and human-review states.
7. API integration and contract tests.
8. Security, container hardening, and deployment.
9. End-to-end, load, and production-readiness testing.

See docs/architecture.md, docs/implementation-roadmap.md, and docs/security.md.

## License

Not yet selected. Do not assume this repository grants rights to use third-party model weights, OCR language data, or datasets; review their licenses separately.
