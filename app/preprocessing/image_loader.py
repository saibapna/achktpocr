from io import BytesIO

from PIL import Image, UnidentifiedImageError


class ImageValidationError(ValueError):
    """Raised when an uploaded image is invalid or unsupported."""


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(data: bytes, max_dimension: int = 8000) -> tuple[str, int, int]:
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
            if max(width, height) > max_dimension:
                raise ImageValidationError("Image dimensions exceed the configured limit.")
            image.verify()
            return image_format, width, height
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageValidationError("The uploaded file is not a valid supported image.") from exc
