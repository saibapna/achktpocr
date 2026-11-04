# ACH KTP OCR — Docker deployment

## Docker quick start

1. Install Docker Engine and Docker Compose v2 on a host with at least 2 GiB RAM (benchmark actual memory before production).
2. Copy .env.example to .env; set a long unique APP_API_KEY. Generate with Python secrets.token_urlsafe(48).
3. Run docker compose up -d --build.
4. Confirm docker compose ps and curl -fsS http://127.0.0.1:8000/health/ready.
5. Test with a synthetic KTP file, never publish actual KTP photos in GitHub or CI.
6. Place an HTTPS reverse proxy (Caddy, Traefik or nginx) in front of the service with ingress body and rate limits; default binding is localhost.
7. Measure latency P95, resident RAM, NIK/name/date exact match, and false positives on a lawfully obtained private KTP dataset before production use.

API smoke test (after loading your .env into the shell):

    set -a; . ./.env; set +a
    curl -H "X-API-Key: $APP_API_KEY" -F "file=@synthetic-ktp.png" http://127.0.0.1:8000/v1/ocr/ktp

## Security and limitations

- This API extracts visual text; it does not verify a person against Dukcapil or establish KTP authenticity.
- Never store image bytes, NIK, names, access tokens or OCR contents in logs or public CI artifacts.
- The current MVP uses a single API key; per-client credentials and rate limiting must precede any multi-tenant production.
- Non-root process, read-only root filesystem, dropped Linux capabilities and bounded parallel inference.
- The caller is responsible for retention policies, human review and audit records.
- Docker image build, actual RapidOCR CPU inference and real KTP accuracy must be verified on the target host. Dependency readiness alone is insufficient.
- YOLO field detection remains unimplemented pending a benchmark.
