# Security and Privacy

KTP images, NIK, names, addresses, birth dates, and OCR output are sensitive personal data.

## Defaults
- Do not persist uploaded images by default.
- Keep processing in memory where feasible; delete temporary files in finally blocks if introduced.
- Never log image bytes, raw OCR text, NIK, names, addresses, API keys, or authorization headers.
- Return generic errors without stack traces, exception details, or filesystem paths.
- Enforce decoded format, size, dimensions, timeout, and concurrency limits.
- Use TLS and API keys from secret management/environment.
- Rotate credentials and document incident response.
- Restrict access to datasets and model artifacts.

## Repository hygiene
Never commit .env files (except .env.example), API tokens, private keys, service-account credentials, real KTP images, identity labels, or unapproved model weights. .gitignore is not a substitute for secret scanning and review.

## Dataset governance
Use only samples with a documented lawful basis, appropriate notice/consent where required, access controls, retention schedule, and deletion procedure. Prefer synthetic fixtures for CI. Never put personal KTP samples in a public repository or issue tracker.

## Limitations
OCR and format checks are not identity verification. NIK structure checks do not establish that a number is registered, validly assigned, or owned by the person shown. Model confidence must not be the sole basis for consequential decisions.
