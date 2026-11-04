# Implementation Roadmap

## Stage 1 — Foundation (current)
- [x] FastAPI package and versioned router.
- [x] Environment-based settings; no committed secrets.
- [x] API-key dependency with constant-time comparison.
- [x] Bounded upload and decoded format/dimension validation.
- [x] Health routes and explicit model-not-configured behavior.
- [x] Docker baseline and tests.
- [ ] Validate CI execution and configure branch protection.

Acceptance: app starts, tests pass, invalid uploads are rejected, and no fake OCR response is returned.

## Stage 2 — Dataset and benchmark
Define lawful collection and retention controls; create annotation guide and human-reviewed ground truth; split by source document/person/session to prevent leakage; benchmark PaddleOCR, Tesseract and optionally EasyOCR on identical splits; report exact match per field, CER/WER, field recall, latency, memory, and failure modes.

Acceptance: reproducible benchmark report with a justified engine choice.

## Stage 3 — Preprocessing
Implement EXIF orientation, quality scoring, perspective correction, and controlled enhancement. Run ablation tests; retain only transformations that improve or preserve metrics.

## Stage 4 — YOLO detector
Annotate/train detector; evaluate mAP50/mAP50-95 and per-class precision/recall; compare one-model and two-stage detection; add bounded fallback.

## Stage 5 — OCR inference
Implement adapter; initialize model once per process; cap concurrency; add timeouts and resource profiling.

## Stage 6 — Extraction and validation
Implement field parser, NIK/date/region checks, confidence calibration, warnings, and human-review thresholds.

## Stage 7 — API integration
Replace 501 with pipeline results; finalize schemas, error mapping, and integration tests.

## Stage 8 — Security and deployment
Add rate limiting, key lifecycle, TLS/gateway, PII-safe logs, upload cleanup, non-root container, secret injection, and vulnerability scanning.

## Stage 9 — Production validation
Load test, profile CPU/RAM, check P95/P99 latency, failure rate, model rollback, observability, retention, and incident response.

## Provisional engineering targets (not measured results)
- NIK exact match >= 95%.
- Name exact match >= 90%.
- Date of birth exact match >= 95%.
- Average target-field accuracy >= 90%.
- Detector mAP50 >= 95%.
- Valid-image request success >= 98%.
- CPU end-to-end P95 <= 5 seconds.

Revisit thresholds after dataset size and risk profile are known. High-impact fields require field-specific review gates rather than average accuracy alone.
