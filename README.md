# ACH KTP OCR

Standalone Indonesian KTP-el OCR API using FastAPI + RapidOCR + ONNX Runtime CPU, designed for Docker Compose.

**Status: experimental Docker OCR MVP.** Engine adapter, parser, image constraints and API are implemented. Real-world KTP accuracy, throughput and Docker runtime still require independent verification. This is not Dukcapil identity validation or document authenticity verification.

## Run using Docker

    git clone https://github.com/saibapna/achktpocr.git
    cd achktpocr
    git switch feat/rapidocr-docker-mvp
    cp .env.example .env
    # Edit .env: replace APP_API_KEY with a long random secret
    docker compose up -d --build
    docker compose ps
    curl -fsS http://127.0.0.1:8000/health/ready
    set -a; . ./.env; set +a
    curl -H "X-API-Key: $APP_API_KEY" -F "file=@synthetic-ktp.png" http://127.0.0.1:8000/v1/ocr/ktp

For local development: pip install -e '.[dev,ocr]' && pytest -q.

## Optional dataset collector

The dataset collector runs separately from the OCR API using an opt-in Docker Compose profile. It downloads synthetic KTP images and labels for offline testing; no dataset files are bundled with the public repository or the production API image.

```sh
mkdir -p datasets/raw
docker compose --profile datasets run --build --rm dataset-collector sources
docker compose --profile datasets run --rm dataset-collector hf --config flat --limit 100
# Whole synthetic flat split (large download):
docker compose --profile datasets run --rm dataset-collector hf --config flat --limit 0
```

Files are stored locally at `datasets/raw/`, excluded from Git. Real or uncertain-privacy collections require separate permission and are never downloaded by default. See [collector instructions](datasets/collector/README.md) and [dataset policy](datasets/README.md).

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

## Benchmark RapidOCR vs Tesseract model KTP

The separate CPU-only benchmark compares RapidOCR and Tesseract with `ktp.traineddata` on identical synthetic or private, authorized held-out images. The custom Tesseract model is **not** included in production images and must pass model licensing/provenance review. See [benchmark instructions](docs/ocr-benchmark.md). Do not enable fallback or preprocessing without validated improvements on held-out KTPs.
