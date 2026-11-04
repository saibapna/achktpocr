# Dataset collector for ACH KTP OCR

Optional Docker dataset acquisition utility. It is separate from the production OCR API image. Data is stored in gitignored `datasets/raw/`.

## Quick start (repository root)

```sh
cp .env.example .env
mkdir -p datasets/raw
# Set a strong APP_API_KEY in .env before deploying the API.
docker compose --profile datasets run --build --rm dataset-collector sources
docker compose --profile datasets run --rm dataset-collector hf --config flat --limit 100
# Download all synthetic flat samples (large):
docker compose --profile datasets run --rm dataset-collector hf --config flat --limit 0
```

Images: `datasets/raw/huggingface/flat/images/`. Labels: `datasets/raw/huggingface/flat/ground_truth.jsonl`. The `--limit 0` option can consume substantial disk space.

## More sources

```sh
docker compose --profile datasets run --rm dataset-collector github --group synthetic
docker compose --profile datasets run --rm dataset-collector all --config flat --limit 100
```

`all` uses only synthetic flat samples and synthetic generator repositories by default. It does not automatically fetch real KTP photographs.

The augmented split may contain residual third-party personal information in hard negatives. Review its data card and permissions before using:

```sh
docker compose --profile datasets run --rm dataset-collector hf --config augmented --limit 100 --ack-authorization
```

The GitHub review collections and Roboflow projects may contain personal ID photos. **Only download if you verified legal authorization from the owners/data subjects**, and only in a private environment.

```sh
docker compose --profile datasets run --rm dataset-collector github --group review --ack-authorization
# Set ROBOFLOW_API_KEY in local .env first:
docker compose --profile datasets run --rm dataset-collector roboflow --ack-authorization
```

The 78-image anonymized real KTP dataset from the JEECS study is **not publicly downloadable**. Use `RESEARCH_ACCESS_REQUEST.md` to request access from authors.

## Safety and limitations

- Never commit KTP images, NIK, identity labels, API keys, or `.env` files.
- A repository's public license does not establish consent from the people pictured.
- Operator flag `--ack-authorization` only confirms your review; it does not verify compliance automatically.
- Keep any genuine samples in encrypted, access-controlled storage with retention/deletion policies.
- Collector needs internet. The API image does not install collector dependencies or mount the dataset.
- If the mounted folder is not writable, set `DATASET_UID` / `DATASET_GID` in `.env` to your numeric local UID/GID; ensure `datasets/raw` is owned by that account.
- Third-party dataset schemas, licenses and availability can change; verify independently.

See `sources.json` for URLs, reported counts, access restrictions and provenance notes.
