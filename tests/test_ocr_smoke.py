"""CPU inference smoke test, requires real RapidOCR installation."""

import io

import pytest
from PIL import Image, ImageDraw

from app.engines.rapidocr_engine import RapidOCREngine


def test_rapidocr_real_cpu_inference():
    pytest.importorskip("onnxruntime")
    pytest.importorskip("rapidocr")
    image = Image.new("RGB", (640, 110), "white")
    ImageDraw.Draw(image).text((20, 30), "NIK 1101010101900001", fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    lines = RapidOCREngine().read(output.getvalue())
    assert isinstance(lines, list)
