# Model Card

## Current status
No detector or OCR model is shipped. The foundation returns MODEL_NOT_CONFIGURED and does not fabricate extraction results.

## Intended use
Assistive text extraction from Indonesian KTP-el images for downstream human-reviewed workflows.

## Out of scope
Identity verification, document authenticity decisions, automated eligibility decisions, and replacing Dukcapil or authoritative registries.

## Planned strategy
YOLO document/field detection followed by one benchmark-selected OCR engine. PaddleOCR is the first candidate; Tesseract is a comparator/fallback candidate. Selection is evidence-based.

## Required evaluation
Per-field exact match, CER/WER, detection precision/recall and mAP, field recall, false-positive document detection, robustness by image conditions, latency, memory, and failure analysis. Record dataset provenance, annotation process, limitations, model checksum, and version before promotion.

Accuracy is unknown until a representative, lawfully sourced, human-labeled evaluation set exists.
