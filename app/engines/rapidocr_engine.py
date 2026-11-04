"""Lazy-loaded RapidOCR ONNX CPU adapter."""

from dataclasses import dataclass
from functools import lru_cache
from importlib.util import find_spec
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OCRLine:
    text: str
    confidence: float
    box: tuple[tuple[float, float], ...] | None = None


class OCREngine(Protocol):
    def read(self, image: bytes) -> list[OCRLine]: ...


def engine_available() -> bool:
    """Dependency availability only; not evidence that inference succeeds."""
    return find_spec("rapidocr") is not None and find_spec("onnxruntime") is not None


class RapidOCREngine:
    def __init__(self) -> None:
        from rapidocr import RapidOCR

        self._engine = RapidOCR()

    def read(self, image: bytes) -> list[OCRLine]:
        result = self._engine(image)
        texts = result.txts if result.txts is not None else []
        scores = result.scores if result.scores is not None else []
        boxes = result.boxes if result.boxes is not None else []
        lines: list[OCRLine] = []
        for index, text in enumerate(texts):
            value = str(text).strip()
            if not value:
                continue
            try:
                score = float(scores[index]) if index < len(scores) else 0.0
                score = max(0.0, min(1.0, score))
            except (TypeError, ValueError):
                score = 0.0
            box = None
            if index < len(boxes):
                try:
                    box = tuple((float(point[0]), float(point[1])) for point in boxes[index])
                except (IndexError, TypeError, ValueError):
                    box = None
            lines.append(OCRLine(value, score, box))
        return lines


@lru_cache(maxsize=1)
def get_engine() -> RapidOCREngine:
    return RapidOCREngine()
