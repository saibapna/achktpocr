"""Geometric preprocessing regression checks (synthetic text only)."""

import io

import pytest
from PIL import Image

from app.benchmark.fixtures import SYNTHETIC_PEOPLE, _base_card, distort
from app.benchmark.geometry import deskew_png, estimate_text_skew
from app.benchmark.runner import normalize_image


@pytest.mark.parametrize(
    ("condition", "expected_angle"),
    [("rotate_12", -12), ("rotate_minus_18", 18), ("combined", -12)],
)
def test_detects_large_rotation_of_synthetic_card(condition, expected_angle):
    source = _base_card(SYNTHETIC_PEOPLE[0])
    transformed = distort(source, condition, seed=0)
    estimate = estimate_text_skew(transformed)
    assert estimate.applied
    assert estimate.alignment_gain > 1.8
    assert estimate.angle_deg == pytest.approx(expected_angle, abs=0.75)


def test_clear_image_is_left_untouched():
    source = _base_card(SYNTHETIC_PEOPLE[0])
    image = io.BytesIO()
    source.save(image, format="PNG")
    original = image.getvalue()
    estimate = estimate_text_skew(source)
    assert not estimate.applied
    assert estimate.angle_deg == 0
    assert deskew_png(original) == original
    assert normalize_image(original, "deskew") == original


def test_lightly_blurred_card_not_needlessly_resampled():
    source = _base_card(SYNTHETIC_PEOPLE[1])
    blurred = distort(source, "blur_mild", seed=0)
    assert not estimate_text_skew(blurred).applied


def test_perspective_remains_explicitly_unfixed():
    source = _base_card(SYNTHETIC_PEOPLE[0])
    persp = distort(source, "perspective", seed=0)
    estimate = estimate_text_skew(persp)
    assert not estimate.applied, "deskew is not perspective rectification"


def test_blank_and_noisy_images_are_rejected_by_alignment_gate():
    assert not estimate_text_skew(Image.new("RGB", (800, 500), "white")).applied
    assert not estimate_text_skew(Image.new("RGB", (800, 500), "black")).applied


def test_invalid_parameter_bounds():
    source = Image.new("RGB", (500, 400), "white")
    with pytest.raises(ValueError, match="search limits"):
        estimate_text_skew(source, max_angle=90)
    with pytest.raises(ValueError, match="search limits"):
        estimate_text_skew(source, minimum_gain=0.5)
