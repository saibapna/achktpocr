"""Conservative document-boundary perspective candidate for *offline benchmark*.

Never active in the public OCR API. The candidate requires four visible, plausible
card corners. Missing/cropped labels cannot be reconstructed by this transform.
It is not document-authenticity or identity verification.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True, slots=True)
class PerspectiveEstimate:
    applied: bool
    area_ratio: float
    quad: tuple[tuple[float, float], ...] | None


def _ordered_corners(points):
    """Return TL/TR/BR/BL or None if corners are not unique."""
    import numpy as np

    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    total = pts.sum(axis=1)
    delta = np.diff(pts, axis=1).ravel()
    quad = np.array(
        [pts[np.argmin(total)], pts[np.argmin(delta)],
         pts[np.argmax(total)], pts[np.argmax(delta)]],
        dtype=np.float32,
    )
    if np.unique(quad, axis=0).shape[0] != 4:
        return None
    return quad


def _find_quad(array, *, max_detection_side: int = 960):
    import cv2
    import numpy as np

    height, width = array.shape[:2]
    scale = min(1.0, max_detection_side / max(width, height))
    if scale < 1:
        reduced = cv2.resize(
            array, (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        reduced = array
    gray = cv2.cvtColor(reduced, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 130)
    edges = cv2.morphologyEx(
        edges, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    reduced_area = float(reduced.shape[0] * reduced.shape[1])
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        area_ratio = area / reduced_area
        if not 0.18 <= area_ratio <= 0.90:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        for epsilon in (0.012, 0.020, 0.030, 0.040):
            approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            quad = _ordered_corners(approx[:, 0, :])
            if quad is None:
                continue
            top = float(np.linalg.norm(quad[1] - quad[0]))
            bottom = float(np.linalg.norm(quad[2] - quad[3]))
            left = float(np.linalg.norm(quad[3] - quad[0]))
            right = float(np.linalg.norm(quad[2] - quad[1]))
            if min(top, bottom, left, right) < 0.18 * min(reduced.shape[:2]):
                continue
            aspect = max(top, bottom) / max(left, right)
            if not 1.15 <= aspect <= 2.25:
                continue
            # Reject thin/concave approximate contours or spurious structures.
            if not 0.87 <= area / max(1.0, cv2.contourArea(quad)) <= 1.13:
                continue
            candidates.append((area, quad, area_ratio))
            break
    if not candidates:
        return None
    _, quad, area_ratio = max(candidates, key=lambda x: x[0])
    quad /= scale
    return quad, area_ratio


def estimate_perspective(image: Image.Image) -> PerspectiveEstimate:
    """Require a bounded, clearly angled quadrilateral before correcting it."""
    import cv2
    import numpy as np

    width, height = image.size
    if min(width, height) < 240 or max(width, height) > 8000:
        return PerspectiveEstimate(False, 0.0, None)
    if width * height > 16_000_000:
        return PerspectiveEstimate(False, 0.0, None)
    array = np.asarray(image.convert("RGB"))
    match = _find_quad(array)
    if match is None:
        return PerspectiveEstimate(False, 0.0, None)
    quad, area_ratio = match
    top = float(np.linalg.norm(quad[1] - quad[0]))
    bottom = float(np.linalg.norm(quad[2] - quad[3]))
    left = float(np.linalg.norm(quad[3] - quad[0]))
    right = float(np.linalg.norm(quad[2] - quad[1]))
    # Leave close-to-front-facing cards untouched: avoid unnecessary resampling.
    distortion = max(
        abs(float(quad[1, 1] - quad[0, 1])) / max(top, 1),
        abs(float(quad[2, 1] - quad[3, 1])) / max(bottom, 1),
        abs(float(quad[3, 0] - quad[0, 0])) / max(left, 1),
        abs(float(quad[2, 0] - quad[1, 0])) / max(right, 1),
        abs(top - bottom) / max(top, bottom, 1),
        abs(left - right) / max(left, right, 1),
    )
    if distortion < 0.035:
        return PerspectiveEstimate(False, round(area_ratio, 3), None)
    # A quadrilateral is not sufficient: reject an empty or extremely dark panel.
    output_width = int(max(top, bottom))
    output_height = int(max(left, right))
    if min(output_width, output_height) < 200 or output_width * output_height > 10_000_000:
        return PerspectiveEstimate(False, round(area_ratio, 3), None)
    destination = np.float32([
        (0, 0), (output_width - 1, 0),
        (output_width - 1, output_height - 1), (0, output_height - 1),
    ])
    transform = cv2.getPerspectiveTransform(quad, destination)
    preview = cv2.warpPerspective(
        cv2.cvtColor(array, cv2.COLOR_RGB2GRAY), transform,
        (output_width, output_height), flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=255,
    )
    h, w = preview.shape
    roi = preview[int(.1 * h):int(.9 * h), int(.1 * w):int(.9 * w)]
    dark_ratio = float(np.count_nonzero(roi < 145)) / max(1, roi.size)
    if not 0.002 <= dark_ratio <= 0.35:
        return PerspectiveEstimate(False, round(area_ratio, 3), None)
    return PerspectiveEstimate(
        True, round(area_ratio, 3),
        tuple((float(x), float(y)) for x, y in quad),
    )


def perspective_png(data: bytes) -> bytes:
    """Crop/rectify when document corners are reliable; otherwise return input."""
    import cv2
    import numpy as np

    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        estimate = estimate_perspective(image)
        if not estimate.applied or estimate.quad is None:
            return data
        quad = np.array(estimate.quad, dtype=np.float32)
        top = float(np.linalg.norm(quad[1] - quad[0]))
        bottom = float(np.linalg.norm(quad[2] - quad[3]))
        left = float(np.linalg.norm(quad[3] - quad[0]))
        right = float(np.linalg.norm(quad[2] - quad[1]))
        width = int(max(top, bottom))
        height = int(max(left, right))
        destination = np.float32([
            (0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1),
        ])
        warp = cv2.getPerspectiveTransform(quad, destination)
        corrected = cv2.warpPerspective(
            np.asarray(image), warp, (width, height),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )
        output = io.BytesIO()
        Image.fromarray(corrected).save(output, format="PNG")
        return output.getvalue()
