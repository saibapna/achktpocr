# Technical Architecture

## Product boundary
aceh-ktp-ocr is an independently deployable REST API. Client applications integrate over HTTP. The service performs visual text extraction and syntactic/consistency validation only. It does not authenticate a person, prove document authenticity, or query Dukcapil.

## Architecture style
Use a modular monolith for MVP. Keep API, preprocessing, detection, OCR engines, extraction, validation, and orchestration behind explicit module boundaries. Do not split into microservices until measured throughput, isolation, or deployment requirements justify it.

## Pipeline
1. Authenticate caller and enforce request limits.
2. Read image in bounded memory; validate decoded format, dimensions, and content.
3. Correct EXIF orientation and assess image quality.
4. Detect document region and rectify perspective when justified.
5. Detect field boxes with YOLO.
6. Crop fields with controlled padding and field-specific preprocessing.
7. Run the selected OCR engine.
8. Normalize text with field-specific parsers.
9. Validate formats and cross-field consistency.
10. Return success, partial, or failed with nulls for missing fields, warnings, provenance, and timings.

A failed field must not fail the entire document by default. Fallback to full-document OCR or alternate crops only when benchmarked and bounded by latency budget.

## Detection strategy
The product strategy is hybrid YOLO + OCR. First evaluate whether one detector can localize the card and all target fields. Separate card and field detectors only if they measurably improve robustness. Track model version, class map, image size, preprocessing version, and training dataset revision.

Initial field labels: nik, nama, tempat_lahir, tanggal_lahir, jenis_kelamin, gol_darah, alamat, rt_rw, kel_desa, kecamatan, agama, status_perkawinan, pekerjaan, kewarganegaraan, berlaku_hingga, provinsi, kabupaten_kota. Confirm taxonomy against permitted sample images before training.

## OCR engine strategy
Define a common adapter interface. Benchmark PaddleOCR, Tesseract, and optionally EasyOCR on identical data splits. PaddleOCR is the first candidate, not a proven winner. Tesseract is a comparator/fallback candidate. Do not run all engines for every field by default. Initialize model objects once per process and cap concurrent inference.

Keep heavy inference dependencies optional until the model stage.

## Preprocessing
Preserve aspect ratio. Apply EXIF orientation, quality scoring, perspective correction, contrast/illumination correction, and denoising only when tests show benefit. Avoid brute-force rotation sweeps. Record preprocessing parameters with each benchmark.

## Extraction and validation
Keep raw OCR text transient and out of logs. Use field-specific normalization. NIK must be exactly 16 digits after cautious normalization; never silently invent digits. Validate real calendar dates. NIK structure and region codes support consistency warnings but cannot verify identity. Region dictionaries must be versioned with source and update date.

## Confidence and status
Keep detector confidence, OCR confidence, and rule-validation outcomes distinct. Engine scores are not calibrated probabilities by default. Calibrate thresholds against labeled data. Return success, partial, or failed. Missing values are null; never infer unknown values.

## Runtime and scaling
Start CPU-first with one API process and bounded concurrency. Measure memory before increasing workers because processes may each load model copies. Add GPU, queues, or batch jobs only when profiling and workload justify them.

## Model lifecycle
Store model artifacts outside Git unless specifically approved. Manifest records model name/version/checksum, class map, runtime version, dataset revision, evaluation report, and approval date. Model promotion must be explicit and reversible.
