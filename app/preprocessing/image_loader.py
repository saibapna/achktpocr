"""Validate supported images, cap decoded pixels and remove EXIF metadata."""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageValidationError(ValueError):
    """Raised if an image cannot be safely processed."""


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(
    data: bytes, max_dimension: int = 8000, max_pixels: int = 16_000_000
) -> tuple[str, int, int]:
    if not data:
        raise ImageValidationError("The uploaded file is empty.")
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            if image_format not in ALLOWED_FORMATS:
                raise ImageValidationError("Only JPEG, PNG, and WEBP images are supported.")
            if width < 1 or height < 1:
                raise ImageValidationError("Image dimensions are invalid.")
            if max(width, height) > max_dimension or width * height > max_pixels:
                raise ImageValidationError("Image dimensions exceed the configured limit.")
            image.verify()
            return image_format, width, height
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageValidationError("The uploaded file is not a valid supported image.") from exc


def prepare_image(
    data: bytes,
    *,
    max_dimension: int = 8000,
    max_pixels: int = 16_000_000,
    max_side: int = 2500,
) -> bytes:
    """Correct EXIF orientation, strip metadata and cap inference resolution."""
    if max_side <= 0:
        raise ValueError("max_side must be positive")
    validate_image(data, max_dimension=max_dimension, max_pixels=max_pixels)
    try:
        with Image.open(BytesIO(data)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="PNG")
            image.close()
            return output.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageValidationError("The uploaded image cannot be decoded.") from exc
