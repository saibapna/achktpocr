# Benchmark-only correction of visible KTP-card perspective

**Status: experimental, not production enabled.** This is a deterministic OpenCV
candidate for photographs containing an intact, visibly bounded card. It does
not authenticate KTPs, does not infer missing characters, and is not an OCR
model. The main FastAPI `/v1/ocr/ktp` and Docker production image do not call it.

## Why this matters

The previous `perspective` synthetic fixture clips the left part of several
labels before OCR. No interpolation or rectification can recover absent pixels;
its expected outcome is failure/re-photograph. Two additional scenarios are now
available:

- `photo_perspective`: an intact, fictional text card on a dark backdrop, with
  a strong but bounded four-corner perspective transform.
- `photo_perspective_blur`: the same synthetic photo plus Gaussian blur radius
  1.4. Every printed character remains inside the four visible corners.

The generator has **three distinct fictional identities** and ten conditions,
for 30 total samples. These are typography-based simulations, not KTP photographs
or an unbiased estimate of accuracy for real-world e-KTPs.

## Candidate processing and rejection behavior

`app/benchmark/perspective.py`:

1. Resize only the detection copy (maximum 960 pixels on the longest side).
2. Find a large, convex quadrilateral from image edges. Require a realistic
   card shape (aspect ratio, visible area, sufficient edge length).
3. Require measurable corner distortion; leave near-front-facing cards alone.
4. Warp a preview to a rectangle and check for plausible text ink density.
5. Apply the same geometric warp to the input image when checks pass.
6. **Fail closed** by returning unmodified image bytes if corners, size or ink
   confidence are insufficient. No image synthesis/super-resolution is used.

Variants for the isolated benchmark:

- `raw`: original prepared image (baseline).
- `perspective`: card-boundary rectification only.
- `deskew`: previous optional global text orientation correction.
- `perspective_deskew`: perspective correction followed by deskew. This is a
  candidate for subsequent paired tests, not a production setting.

The CLI, parser and paired NIK metrics are otherwise unchanged.

## Reproducible local diagnostic (2026-11-05)

Environment: Linux, Tesseract CLI with installed **`ind`** model (not upstream
`ktp.traineddata`), Python 3.13; CPU inference. The report contains only
aggregates; images and raw OCR/identity text were not committed.

```sh
python scripts/benchmark_ocr.py --synthetic \
  --engines tesseract-ind \
  --tessdata-dir /usr/share/tesseract-ocr/5/tessdata \
  --variants raw,perspective \
  --output reports/tesseract-ind-perspective.json
```

| Synthetic condition | Raw NIK exact | Perspective NIK exact |
| --- | ---: | ---: |
| Clear (3 images) | 3/3 | 3/3 |
| Mild blur (3) | 3/3 | 3/3 |
| Medium blur (3) | 3/3 | 3/3 |
| Low light (3) | 3/3 | 3/3 |
| Rotated +12 deg (3) | 0/3 | 0/3 |
| Rotated -18 deg (3) | 0/3 | 0/3 |
| Rotation + blur (3) | 0/3 | 0/3 |
| Legacy clipped perspective (3) | 0/3 | 0/3 |
| **Whole-card perspective photo (3)** | **0/3** | **3/3** |
| **Whole-card perspective + blur (3)** | **0/3** | **3/3** |
| **Total** | **12/30 (40%)** | **18/30 (60%)** |

Paired NIK outcomes: **six improvements, zero regressions, twelve still wrong,
twelve correct for both** on this synthetic set. Combined OCR + candidate
preprocessing latency P95: **341.04 ms raw vs 455.49 ms perspective** on the
local test runtime. The shared image decode/normalization and HTTP overhead
are excluded. Peak memory was not measured, and these numbers are **not**
valid production SLOs.

Reproducible machine-readable aggregate:
[`docs/benchmarks/tesseract-ind-perspective-synthetic-20261105.json`](benchmarks/tesseract-ind-perspective-synthetic-20261105.json).

## Important limitations and release gates

- Three independent synthetic cards are too few for a robust accuracy claim;
  they share fonts, layouts, lighting model and background. No p-values or
  confidence bounds are inferred. The quad detector can fail on real textured
  backgrounds, occluded card corners, glare or unusual proportions.
- The legacy cropped fixture remains deliberately uncorrected; this should
  prompt safe OCR refusal / photograph again, not generated NIK digits.
- **RapidOCR/ONNX** and **Tesseract `ktp.traineddata`** have **not** completed
  a paired real-model comparison on the same dataset. Do not attribute the
  `tesseract-ind` diagnostic to either model.
- No unreviewed third-party traineddata is shipped; check its provenance and
  conflicting upstream license declarations before any use/distribution.
- Before enabling the candidate in production, require a private, lawfully
  obtained held-out dataset with at least 100 independent cards/identities and
  sufficient blur/perspective severity, plus hard-negative non-KTP examples.
- Review paired NIK/name/DOB exact match, CER, fallback rate, false success,
  per-condition regressions, latency P95/peak RAM in Docker; do not accept a
  regression in clear images or a substantial security/privacy risk.
- Finish end-to-end Docker inference smoke tests and CI on the exact PR commit;
  then require a **separate approval/PR** for production deployment.

This work is intentionally a benchmark option only.
