"""Adapters for a fair baseline OCR comparison on identical image bytes.

Tesseract's traineddata is deliberately not bundled: the upstream repository's
LICENSE and package.json disagree. Audit its provenance/license separately.
"""

import csv
import hashlib
import io
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from app.engines.rapidocr_engine import OCRLine, RapidOCREngine


class BenchmarkEngine(Protocol):
    name: str

    def read(self, image: bytes) -> list[OCRLine]: ...


class RapidOCRAdapter:
    name = "rapidocr"

    def __init__(self) -> None:
        self._engine = RapidOCREngine()

    def read(self, image: bytes) -> list[OCRLine]:
        return self._engine.read(image)


class TesseractAdapter:
    """Tesseract CLI TSV-based adapter for the exact provided language model."""

    def __init__(
        self, *, tessdata_dir: Path, lang: str = "ktp", psm: int = 6, timeout: float = 30.0
    ) -> None:
        self.name = f"tesseract-{lang}"
        self.tessdata_dir = tessdata_dir.resolve()
        self.lang = lang
        self.psm = psm
        self.timeout = timeout
        model = self.tessdata_dir / f"{lang}.traineddata"
        if not model.is_file() or model.stat().st_size < 10000:
            raise FileNotFoundError(f"Tesseract model missing or invalid: {model}")
        if not (3 <= psm <= 13):
            raise ValueError("Page segmentation mode must be 3..13")
        with model.open("rb") as model_file:
            self.model_sha256 = hashlib.file_digest(model_file, "sha256").hexdigest()

    def read(self, image: bytes) -> list[OCRLine]:
        command = [
            "tesseract",
            "stdin",
            "stdout",
            "--tessdata-dir",
            str(self.tessdata_dir),
            "-l",
            self.lang,
            "--oem",
            "3",
            "--psm",
            str(self.psm),
            "tsv",
        ]
        try:
            process = subprocess.run(
                command,
                input=image,
                capture_output=True,
                check=False,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Tesseract executable is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Tesseract inference timed out") from exc
        if process.returncode != 0:
            # Never surface stderr: it could include an image filename or other PII.
            raise RuntimeError(
                f"Tesseract failed (exit {process.returncode}); inspect model/runtime"
            )
        try:
            text = process.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Invalid TSV output from Tesseract") from exc
        return parse_tesseract_tsv(text)


def parse_tesseract_tsv(text: str) -> list[OCRLine]:
    """Group word boxes by line to preserve KTP label-value relationships."""
    groups: dict[tuple[int, int, int, int], list[tuple[int, str, float, int, int, int, int]]] = (
        defaultdict(list)
    )
    for line in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if line.get("level") != "5":
            continue
        value = (line.get("text") or "").strip()
        if not value:
            continue
        try:
            conf = float(line["conf"])
            if not (0 <= conf <= 100):
                continue
            left, top, width, height = (int(line[k]) for k in ("left", "top", "width", "height"))
            if width < 1 or height < 1:
                continue
            key = tuple(int(line[k]) for k in ("page_num", "block_num", "par_num", "line_num"))
            position = int(line["word_num"])
        except (ValueError, TypeError, KeyError):
            continue
        groups[key].append((position, value, conf, left, top, left + width, top + height))
    output: list[tuple[int, int, OCRLine]] = []
    for words in groups.values():
        words.sort(key=lambda w: w[0])
        left = min(word[3] for word in words)
        top = min(word[4] for word in words)
        right = max(word[5] for word in words)
        bottom = max(word[6] for word in words)
        recognized = " ".join(word[1] for word in words)
        # Tesseract's 0..100 score is likewise not a calibrated probability.
        confidence = min(word[2] for word in words) / 100.0
        box = ((left, top), (right, top), (right, bottom), (left, bottom))
        output.append((top, left, OCRLine(recognized, confidence, box)))
    output.sort(key=lambda item: (item[0], item[1]))
    return [entry[2] for entry in output]
