# Reproducible CPU comparison: RapidOCR vs Tesseract `ktp.traineddata`

## Current evidence boundary

- **No claim of accuracy improvement** until both models complete the **same** held-out image set.
- `ktp.traineddata` is a custom Tesseract language model from `taqiin/OCR-KTP-ID`, pinned to commit `56026700d951845897eed5f48339d19c00604147` and Git blob SHA1 `8df4926187c806b35607519eee0c5a6e970a630a`.
- Upstream `LICENSE` is Artistic License 2.0, while `package.json` says MIT. The training source/model rights are not documented. **Do not redistribute or bundle the binary without a legal/provenance review.**
- The model is a **candidate comparator**, not an automatic production fallback. It is excluded from the production Dockerfile and Compose.

## Running locally (requires network to install models)

Run from the repository root on a CPU machine with 2+ GiB memory and Python 3.11:

    python -m pip install -e '.[ocr,dev]'
    sudo apt-get install tesseract-ocr fonts-dejavu-core

After checking the source/model rights and security of the artifact:

    python scripts/fetch_taqiin_ktp.py --acknowledge-license-review
    python scripts/benchmark_ocr.py --synthetic \
      --tessdata-dir models/benchmark --engines rapidocr,tesseract-ktp \
      --variants raw,gray,contrast,unsharp \
      --output reports/synthetic_ocr.json

This generates 24 **fictional, typographic** fixtures (3 synthetic identities × 8 conditions) in a temporary directory. Conditions include blur, ± rotation, perspective, low light and combined distortions. Reports contain aggregate outcomes only and **cannot** establish accuracy on real KTP photos.

## Running with Docker

    mkdir -p reports models/benchmark
    export LOCAL_UID=$(id -u) LOCAL_GID=$(id -g)
    docker compose -f compose.benchmark.yaml build benchmark
    docker compose -f compose.benchmark.yaml run --rm benchmark

The reference model must be placed in `models/benchmark/ktp.traineddata` manually/by the reviewed fetch script before building/running; it is bind-mounted read-only. The benchmark image runs both OCR engines as an offline CPU workload. This **does not modify** production `docker compose up`.

For an authorized private held-out collection, mount the private dataset to `/private` read-only and override the Compose command:

    docker compose -f compose.benchmark.yaml run --rm \
      -v /secure/private-ktp:/private:ro \
      benchmark --manifest /private/manifest.jsonl \
      --tessdata-dir /models/benchmark --engines rapidocr,tesseract-ktp \
      --variants raw,gray,contrast,unsharp --output /reports/private_summary.json

Manifest format (JSONL, one object per case; **never commit private files**):

    {"image":"images/case_001.png","group":"person_A","condition":"blur_mild","ground_truth":{"nik":"0000000101900001","nama":"CONTOH FIKTIF","tanggal_lahir":"01-01-1990","tempat_lahir":"BANDA ACEH","alamat":"JALAN SINTETIS NOMOR 7"}}

`image` must be a relative path inside the manifest directory. `group` identifies the same person/card across multiple captures and is used to report the number of independent groups. The manifest should be sampled and split **by distinct persons/cards**, with ground truth independently verified. The example above is wholly fictional.

## Methodology and decision gate

- Use exactly the same image bytes, engine configuration, parser and held-out samples across comparisons. The `raw`, `gray`, `contrast` and `unsharp` ablations are each measured independently.
- Measurements: NIK 16-digit exact match, exact match/read rate and character error rate (CER) for name/date/place/address, parse coverage, engine errors, P50/P95 inference time. No raw OCR text, paths, NIK, GT labels or images in output.
- **Never** accept an improvement on only the synthetic set. Require at least 100 independent, properly licensed/authorized held-out real documents across photographed conditions, enough per-severity samples, and estimates of uncertainty before promotion.
- Candidate preprocessing/fallback must improve NIK exact-match on the hard subset **without material losses on clear samples**, excess false positive `success`, or unacceptable CPU/RAM/P95 cost. Include per-field metrics, not only mean confidence. Compare paired outcomes per document to avoid bias.
- User-visible inference never replaces a missing NIK with inferred digits; review/re-photograph when uncertain.
- Any promotion requires explicit maintainer approval and a separate PR, model provenance audit and CI + Docker smoke tests; the benchmark **never alters the default engine**.

## Failure modes

The runner fails closed if either engine/model is absent or crashes (unless explicitly using `--allow-errors`, which counts failures). `health/ready` dependency availability is **not** a successful OCR inference test. A Docker image build is likewise **not** benchmark evidence.
