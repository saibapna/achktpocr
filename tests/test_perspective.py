"""Only fictional image fixtures; benchmark-only geometry candidate."""

import io

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("cv2")
pytest.importorskip("numpy")

from app.benchmark.fixtures import (  # noqa: E402
    SYNTHETIC_PEOPLE,
    _base_card,
    distort,
)
from app.benchmark.perspective import (  # noqa: E402
    estimate_perspective,
    perspective_png,
)
from app.benchmark.runner import PREPROCESS, normalize_image  # noqa: E402


def _png(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


@pytest.mark.parametrize("condition", ["photo_perspective", "photo_perspective_blur"])
def test_recovers_plausible_full_card_from_synthetic_photo(condition):
    source = _base_card(SYNTHETIC_PEOPLE[0])
    distorted = distort(source, condition, 0)
    estimate = estimate_perspective(distorted)
    assert estimate.applied
    assert estimate.quad is not None and len(estimate.quad) == 4
    assert .3 < estimate.area_ratio < .85
    fixed = perspective_png(_png(distorted))
    with Image.open(io.BytesIO(fixed)) as image:
        assert 1050 < image.width < 1800
        assert 720 < image.height < 1150
    assert fixed != _png(distorted)


def test_preserve_clear_fictional_card_without_border():
    source = _base_card(SYNTHETIC_PEOPLE[1])
    original = _png(source)
    assert not estimate_perspective(source).applied
    assert perspective_png(original) == original
    assert normalize_image(original, "perspective") == original
    assert normalize_image(original, "perspective_deskew") == original


def test_cropped_perspective_does_not_hallucinate_missing_document():
    source = _base_card(SYNTHETIC_PEOPLE[0])
    clipped = distort(source, "perspective", seed=0)
    original = _png(clipped)
    assert not estimate_perspective(clipped).applied
    assert perspective_png(original) == original


def test_blank_and_black_panels_are_rejected():
    import cv2
    import numpy as np

    for color in (0, 255):
        image = Image.new("RGB", (1000, 800), (color, color, color))
        assert not estimate_perspective(image).applied
        assert perspective_png(_png(image)) == _png(image)
    # An apparently rectangular blank card is not sufficient: we require ink.
    canvas = np.full((900, 1250, 3), 80, dtype=np.uint8)
    points = np.float32([[120, 100], [1110, 170], [1080, 820], [100, 780]])
    cv2.fillConvexPoly(canvas, points.astype(np.int32), (255, 255, 255))
    cv2.polylines(canvas, [points.astype(np.int32)], True, (0, 0, 0), 5)
    image = Image.fromarray(canvas)
    assert not estimate_perspective(image).applied


def test_non_kpt_logo_like_small_quadrilateral_not_warped():
    image = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(300, 250), (550, 240), (580, 370), (310, 390)], outline="black", width=6)
    assert not estimate_perspective(image).applied


def test_no_unnecessary_resize_for_near_aligned_full_card():
    import cv2
    import numpy as np

    source = _base_card(SYNTHETIC_PEOPLE[0]).convert("RGB")
    card = np.asarray(source)
    h, w = card.shape[:2]
    canvas = np.full((h + 200, w + 200, 3), 85, dtype=np.uint8)
    canvas[100:100 + h, 100:100 + w] = card
    cv2.rectangle(canvas, (100, 100), (100 + w - 1, 100 + h - 1), (20, 20, 20), 6)
    flat = Image.fromarray(canvas)
    image_bytes = _png(flat)
    assert not estimate_perspective(flat).applied
    assert perspective_png(image_bytes) == image_bytes


def test_optional_preprocess_variants_are_exposed():
    assert "perspective" in PREPROCESS
    assert "perspective_deskew" in PREPROCESS
    data = _png(distort(_base_card(SYNTHETIC_PEOPLE[1]), "photo_perspective", 0))
    fixed = normalize_image(data, "perspective_deskew")
    assert fixed.startswith(b"\x89PNG")
    assert fixed != data


def test_large_images_are_rejected_with_noop():
    image = Image.new("RGB", (4000, 4500), "white")
    assert not estimate_perspective(image).applied
