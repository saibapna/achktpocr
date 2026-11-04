"""OCR orchestration placeholder.

Do not return fabricated OCR values. Implement inference only after a benchmark
dataset and validated detector/OCR model artifacts are available.
"""


class ModelNotConfiguredError(RuntimeError):
    """Raised when inference is requested without validated model artifacts."""
