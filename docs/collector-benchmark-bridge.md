# Collector -> OCR benchmark bridge (synthetic flat split)

This utility converts the **locally collected, synthetic-only** Hugging Face
`flat` dataset into the private JSONL format expected by the paired OCR
benchmark. **No dataset images, labels, NIKs or manifests are committed.**

## Why the converter is needed

The collector creates `datasets/raw/huggingface/flat/ground_truth.jsonl` records
with `file` and a nested `ground_truth` matching the HF row schema. The benchmark
expects `image`, `condition`, `group` and a normalized `ground_truth` object.
The source uses `tempat_tanggal_lahir` whereas the parser measures distinct
`tempat_lahir` and `tanggal_lahir` fields.

This converter validates the source, path, mandatory labels and date; splits
**whole synthetic identities** by the exact NIK value (never printed), and
writes two manifests next to the original collector output:

- `benchmark_development.jsonl`: development-only synthetic cases.
- `benchmark_holdout.jsonl`: untouched synthetic holdout cases, optionally
  extended with blur, rotation, perspective, low-light and combined variants.

Both are private/local, are written with `0600` permissions, and retain labels.
The derived images remain in `images/benchmark_generated/` and are excluded
from Git by the existing `datasets/raw/` rules.

## Docker-only workflow

After switching to the branch that includes this bridge:

```sh
cp .env.example .env
# Set APP_API_KEY before starting the production API.
mkdir -p datasets/raw models/benchmark reports

# Start small rather than downloading all ~24,000 synthetic flat records.
docker compose --profile datasets run --build --rm \
  dataset-collector hf --config flat --limit 100

# Build the separate benchmark image with Python and Pillow.
export LOCAL_UID=$(id -u)
export LOCAL_GID=$(id -g)
docker compose -f compose.benchmark.yaml build benchmark

# Convert and generate 7 distorted variants for each holdout image.
docker compose -f compose.benchmark.yaml run --rm \
  --entrypoint python \
  -v "$PWD/datasets/raw/huggingface/flat:/private" \
  benchmark scripts/prepare_collector_benchmark.py \
  --source /private/ground_truth.jsonl --limit 100 \
  --holdout-fraction 0.2 --seed 20261105 \
  --augment-holdout --max-augment 200

# First measure RapidOCR alone: does not require the custom Tesseract model.
docker compose -f compose.benchmark.yaml run --rm \
  -v "$PWD/datasets/raw/huggingface/flat:/private:ro" \
  benchmark --manifest /private/benchmark_holdout.jsonl \
  --engines rapidocr --variants raw,deskew \
  --output /reports/collector_rapidocr.json
```

The above example starts from 100 collected synthetic cards, chooses ~20%
independent groups for holdout (exact row counts can vary if identities repeat),
and creates 7 controlled distortions per held-out card. The remaining cards
are reserved for development, **not** for reporting final accuracy.

To run the paired comparison against the third-party trained model, first
review its origin, redistribution rights and license; place the verified
`ktp.traineddata` in `models/benchmark/`, then rerun with
`--engines rapidocr,tesseract-ktp`. **Do not enable production fallback from
results on this synthetic dataset alone.**

## Python-only alternative

Install the base dependencies / Pillow and execute from repository root:

```sh
python3 scripts/prepare_collector_benchmark.py \
  --source datasets/raw/huggingface/flat/ground_truth.jsonl \
  --limit 100 --augment-holdout
```

By default the converter refuses to overwrite existing manifests. Use
`--overwrite` for an intentional regeneration with a different split seed.
`--limit 0` reads all available samples, but producing distortions at scale
requires raising `--max-augment` and sufficient disk space. Start small.

## Validity and security limitations

- Only `cloverx-id/indonesian-id-card-dummy` **flat** records are supported.
  The augmented subset has a publisher warning about possible residual
  third-party personal data and is deliberately rejected here.
- Neither a split of one public synthetic dataset nor artificially degraded
  images estimates performance on genuine photographed e-KTPs. Models can
  already have seen similar generated templates. Reassess on held-out,
  lawfully sourced independent card identities and camera conditions.
- Repeated synthetic NIKs stay in the same split; no labels, filenames,
  image paths or per-card predictions appear in aggregated benchmark reports.
  The private manifests **do contain** raw synthetic ground truth and must
  remain access-controlled.
- Distortions are analytical only, not a license to manufacture real IDs or
  use genuine personal data without permission.
- A benchmark result does **not** promote a different OCR engine or image
  preprocessing automatically. Promotion requires review and a separate PR.
