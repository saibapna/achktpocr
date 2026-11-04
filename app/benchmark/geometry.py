"""Optional, conservative text-alignment deskew for *offline benchmarking*.

This module is NOT active in the production OCR request path. It uses only
geometric rotation and does not synthesize/reconstruct characters.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True)
class DeskewEstimate:
    angle_deg: float
    alignment_gain: float
    applied: bool


def estimate_text_skew(
    image: Image.Image,
    *,
    max_angle: int = 24,
    max_side: int = 700,
    minimum_gain: float = 1.8,
) -> DeskewEstimate:
    """Find the bounded rotation maximizing horizontal text-line concentration.

    A relative gain threshold prevents needless resampling of aligned images.
    This method estimates *global* skew only: it does not rectify 3D perspective,
    motion blur, mirrored text, vertical/90-degree text, or missing characters.
    """
    if max_angle < 2 or max_angle > 45 or max_side < 200 or minimum_gain <= 1.0:
        raise ValueError("Invalid deskew search limits")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Deskew benchmark requires opencv-python-headless and numpy") from exc

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    scale = min(1.0, max_side / max(height, width))
    if scale < 1:
        gray = cv2.resize(
            gray,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    height, width = ink.shape
    foreground = float(np.count_nonzero(ink)) / ink.size
    if not 0.002 <= foreground <= 0.45:
        return DeskewEstimate(0.0, 1.0, False)
    center = (width / 2, height / 2)

    def score(angle: float) -> float:
        rotation = cv2.getRotationMatrix2D(center, angle, 1.0)
        transformed = cv2.warpAffine(
            ink,
            rotation,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        sums = np.count_nonzero(transformed, axis=1).astype(np.float64)
        # Normalize for minor foreground clipping at candidate angles.
        return float(np.dot(sums, sums) / max(1.0, sums.sum()) - sums.mean())

    unrotated_score = score(0.0)
    coarse = range(-max_angle, max_angle + 1, 2)
    best_coarse = max(coarse, key=score)
    fine = [best_coarse - 1.75 + i * 0.25 for i in range(15)]
    angle = max(fine, key=score)
    peak = score(angle)
    gain = peak / max(1e-6, unrotated_score)
    applied = abs(angle) >= 1.0 and gain >= minimum_gain
    return DeskewEstimate(round(float(angle), 2), round(float(gain), 3), applied)


def deskew_png(data: bytes) -> bytes:
    """Rotate visually aligned text only if the measured alignment improves.

    Returns original PNG bytes when no transform is justified. Runs only in the
    optional offline benchmark, never as a production default.
    """
    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        estimate = estimate_text_skew(image)
        if not estimate.applied:
            return data
        corrected = image.rotate(
            estimate.angle_deg,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor="white",
        )
        buffer = io.BytesIO()
        corrected.save(buffer, format="PNG")
        corrected.close()
        return buffer.getvalue()
