# Candidate geometry preprocessing: auto-deskew (benchmark only)

**Status: evaluation; NOT deployed.** This candidate adds conservative global text-line rotation to the isolated OCR benchmark. It does not edit `/v1/ocr/ktp`, the production Dockerfile, RapidOCR model selection, or API output. Do not interpret the experiments below as a claim about real KTP photos.

## What it does

`app/benchmark/geometry.py` downsamples an image to at most 700 px, selects a bounded rotation (−24° to +24°) by maximizing horizontal ink-row concentration, and accepts the transformation only if there is at least a 1.8× gain in the alignment score. Otherwise it returns the original image bytes. The image is rotated using bicubic interpolation and white borders; no learned upscaling, hallucination or character filling is used.

- **Useful for testing:** global tilted text and minor moderate blur with text still present.
- **Not solved:** arbitrary camera perspective / trapezoid, 90°/180° orientation, severe motion blur, cropped-off characters, forged documents, Dukcapil verification.
- **Risk:** alignment gain is not an OCR confidence or a calibrated probability. On real documents, dense patterns, patterned backgrounds or asymmetric layouts may lead to wrong rotations. Measure on held-out KTPs before considering deployment.

## Reproduce on a Docker CPU benchmark host

Make sure the project is on `feat/ocr-geometry-deskew-benchmark` (or a descendant of the benchmark PR). Install `rapidocr`, ONNX Runtime, and the Tesseract candidate model only in the **benchmark environment**, after verifying the model's licensing/provenance. No KTP images or custom traineddata are included in source control.

Synthetic smoke comparison, same input set and parser for both engines:

    python scripts/benchmark_ocr.py --synthetic \
      --engines rapidocr,tesseract-ktp \
      --tessdata-dir models/benchmark \
      --variants raw,deskew \
      --output reports/paired_geometry_synthetic.json

For private, consented held-out KTP cases, use `--manifest /private/manifest.jsonl` instead of `--synthetic`. The input must contain multiple groups of distinct cards/people; split/train/test by group and separately report hard subsets (rotation, motion blur, defocus, perspective, low-light). Keep the dataset offline and private.

### Diagnostic with Tesseract `ind` (not the custom KTP model)

On a CPU host with Tesseract language `ind` installed:

    python scripts/benchmark_ocr.py --synthetic \
      --engines tesseract-ind \
      --tessdata-dir /usr/share/tesseract-ocr/5/tessdata \
      --variants raw,deskew \
      --output reports/deskew_ind_synthetic.json

Results observed on **2026-11-05**, Tesseract 5.5.0, `ind` model SHA-256 `69786901da87ab8766c1ea7fbb10b28f2110c14da3f6c8f2735df131fba95d88`, Python 3.13.5, 24 typographic synthetic fixture images (3 distinct fictional cards × 8 conditions):

| Synthetic condition | Raw NIK exact | Deskew NIK exact |
| --- | ---: | ---: |
| Clear | 3/3 | 3/3 |
| Mild Gaussian blur | 3/3 | 3/3 |
| Medium Gaussian blur | 3/3 | 3/3 |
| Low light | 3/3 | 3/3 |
| Rotated +12° | 0/3 | 3/3 |
| Rotated −18° | 0/3 | 3/3 |
| Rotated and blurred | 0/3 | 3/3 |
| Perspective warped | 0/3 | 0/3 |
| **Total** | **12/24** | **21/24** |

**Paired difference: 9 improved, 0 regressed, 15 unchanged**; only 3 independent synthetic cards. These results are not KTP field accuracy estimates or statistical evidence for production deployment. For reproducibility, a minimized aggregate JSON report containing no NIK, names, paths, raw OCR strings, or source images is checked into `docs/benchmarks/`.

The measured P95 for inference plus variant transformation was **347.29 ms raw** versus **705.96 ms deskew** on the local machine (a cost increase); these figures exclude base image decode and network handling, and 24 synthetic samples are insufficient for reliable performance estimates.

This experiment was **not a RapidOCR vs custom `ktp.traineddata` comparison**: both engines must still be executed against the same held-out real documents under identical CPU and image configurations.

## Operational cost and reporting

- The runner now reports the variant transform time separately as `variant_preprocessing_ms` and its sum with OCR inference as `inference_plus_variant_ms`. The base image decoding/normalization remains a shared, uncounted cost, so neither metric is complete HTTP latency.
- `overall` returns aggregate sample-level P50/P95, not the mean of per-condition percentiles.
- `paired_nik_variants` compares `raw` with each non-raw variant on identical input images; `paired_nik_engines` similarly compares each candidate engine with the first engine passed to `--engines`. The `both_correct`, `baseline_only`, `candidate_only`, and `both_wrong` values are counts, without exposing any individual image.
- An engine error counts as incorrect rather than silently disappearing from denominators when `--allow-errors` is explicitly set. The default is fail-closed.

## Conditions before any production adoption

1. Both **RapidOCR** and Tesseract with verified `ktp.traineddata` complete the same ≥100 independent, lawfully sourced, labeled and held-out KTP cards, with blur/rotation/perspective strata adequately populated. The diagnostic set is **not** qualifying data.
2. Show per-condition NIK **16-digit exact match**, other field exact match/CER, invalid-document false positives, failure/re-photograph rate, and paired differences with uncertainty intervals. Never claim a 16-digit regex means NIK authenticity.
3. Ensure no material regression on clear or non-KTP samples and acceptable CPU/RAM/p95 cost *including preprocessing*. Avoid generative digit reconstruction.
4. Maintain privacy: no raw image bytes, NIK, names, ground truth or OCR text in logs or public CI reports.
5. Obtain maintainer review, model license clearance, passing Docker inference and CI, and then open a **separate production PR** if evidence supports it.
