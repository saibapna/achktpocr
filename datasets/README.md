# Datasets and privacy

Do not commit KTP images, NIK, names, addresses, identity labels, or other personal data here. Keep authorized real-world data in private, access-controlled storage. Document lawful basis, consent/notice where required, provenance, retention, access policy, and deletion procedure before collection. Use synthetic fixtures for CI.

## Optional dataset collector

The `dataset-collector` service is in the `datasets` profile; it does not start with the OCR API.

```sh
cp .env.example .env
mkdir -p datasets/raw
docker compose --profile datasets run --build --rm dataset-collector sources
docker compose --profile datasets run --rm dataset-collector hf --config flat --limit 100
```

Results stay in gitignored `datasets/raw/`. See [collector instructions](collector/README.md) for the complete source catalog, permissions and ground-truth locations.
