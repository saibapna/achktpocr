# ACH KTP OCR

Standalone Indonesian KTP-el OCR API using FastAPI + RapidOCR + ONNX Runtime CPU, designed for Docker Compose.

**Status: experimental Docker OCR MVP.** Engine adapter, parser, image constraints and API are implemented. Real-world KTP accuracy, throughput and Docker runtime still require independent verification. This is not Dukcapil identity validation or document authenticity verification.

## Run using Docker

    git clone https://github.com/saibapna/achktpocr.git
    cd achktpocr
    cp .env.example .env
    # Edit .env: replace APP_API_KEY with a long random secret
    docker compose up -d --build
    docker compose ps
    curl -fsS http://127.0.0.1:8000/health/ready
    set -a; . ./.env; set +a
    curl -H "X-API-Key: $APP_API_KEY" -F "file=@synthetic-ktp.png" http://127.0.0.1:8000/v1/ocr/ktp

For local development: pip install -e '.[dev,ocr]' && pytest -q.

## API

- GET /health/live: process liveness
- GET /health/ready: OCR dependency readiness (not proof of successful inference)
- GET /v1/models: engine status
- POST /v1/ocr/ktp: JPEG/PNG/WebP multipart image upload using field file; requires X-API-Key

Default size limits are 10 MiB and 16 megapixels. The API strips image metadata, returns NIK, name, date/place of birth, sex, blood type, address, RT/RW, village, kecamatan, religion, marriage status, job, citizenship, expiry, province and regency/city. Unreadable fields are null rather than invented. Engine confidence is not a calibrated probability; 16-digit NIK format is not official registration proof.

Pipeline: validate → orient/normalize → RapidOCR CPU → group visual lines → parse labeled fields → syntax/consistency warnings → structured JSON.

YOLO field detection and comparisons with Tesseract/PaddleOCR are future extensions pending labeled benchmark data. The Docker image is CPU-first, non-root and read-only; put an HTTPS reverse proxy with rate limiting before external exposure. Never log NIK, KTP image data or raw OCR text. Human confirmation is required before persisting member/person data.

Read docs/docker-deployment.md for operations and security.

**License:** project license not yet selected; separately inspect third-party OCR model and dataset licenses before redistribution.
