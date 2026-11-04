# API Specification (v1)

## Authentication
Protected endpoints use the X-API-Key header. Configure APP_API_KEY using deployment environment/secret management. Never commit real values. Use TLS in deployment.

## Endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | /health/live | Liveness | No |
| GET | /health/ready | Readiness/model state | No |
| GET | /v1/models | Active model metadata | No in foundation |
| POST | /v1/ocr/ktp | OCR one KTP image | Yes |

## POST /v1/ocr/ktp
Content type: multipart/form-data. Required field: file. Supported decoded formats: JPEG, PNG, WEBP. Default max upload: 10 MiB; max dimension: 8000 px.

Success contract (illustrative):

~~~json
{
  "request_id": "opaque-request-id",
  "status": "partial",
  "document_type": "ktp_el",
  "data": {"nik": null, "nama": "string-or-null"},
  "fields": {
    "nik": {
      "value": null,
      "confidence": null,
      "source": null,
      "validation": "warning",
      "warnings": ["Field not confidently detected"]
    }
  },
  "warnings": [],
  "processing": {"total_ms": 0},
  "model_version": "detector-version"
}
~~~

Final response includes the full field set. Confidence must not be described as calibrated probability unless calibration was evaluated.

## Error contract

| HTTP | Code | Meaning |
|---|---|---|
| 400 | INVALID_IMAGE | Invalid or unsupported image |
| 401 | UNAUTHORIZED | Missing/invalid API key |
| 413 | UPLOAD_TOO_LARGE | Upload exceeds limit |
| 429 | RATE_LIMITED | Caller exceeded quota; limiter stage |
| 501 | MODEL_NOT_CONFIGURED | No active inference model |
| 503 | AUTH_NOT_CONFIGURED / NOT_READY | Required runtime configuration/model unavailable |

Do not return stack traces, raw OCR content, NIK, or internal file paths in errors.

## Operational semantics
One image per request, synchronous in MVP. Missing fields are null. Partial results are first-class. Request IDs must not encode personal data. Include model and preprocessing versions for reproducibility.
