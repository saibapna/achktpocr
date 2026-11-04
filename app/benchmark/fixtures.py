"""Generate *fictional* KTP-like text cards and deterministic distortions.

These are typographic tests, not replicas of official KTP cards. They cannot
estimate accuracy on real photographs. Never generate or include real NIKs.
"""

from dataclasses import dataclass
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


@dataclass(frozen=True)
class Fixture:
    image: Path
    condition: str
    group: str
    truth: dict[str, str]


SYNTHETIC_PEOPLE = (
    ("0000000101900001", "CONTOH FIKTIF", "BANDA ACEH", "01-01-1990"),
    ("0000000212940002", "DATA SIMULASI", "MEDAN", "02-12-1994"),
    ("0000001506030003", "UJI PERANGKAT", "JAKARTA", "15-06-2003"),
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    raise RuntimeError("Install DejaVu Sans fonts to generate reproducible synthetic fixtures")


def _base_card(person: tuple[str, str, str, str]) -> Image.Image:
    nik, nama, place, dob = person
    image = Image.new("RGB", (1450, 970), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 50), "PROVINSI SIMULASI", font=_font(44), fill="black")
    draw.text((80, 126), "KABUPATEN CONTOH", font=_font(32), fill="black")
    lines = (
        f"NIK : {nik}",
        f"Nama : {nama}",
        f"Tempat/Tgl Lahir : {place}, {dob}",
        "Jenis Kelamin : LAKI-LAKI",
        "Alamat : JALAN SINTETIS NOMOR 7",
        "RT/RW : 001/002",
        "Kel/Desa : CONTOH",
        "Kecamatan : SIMULASI",
        "Kewarganegaraan : WNI",
        "Berlaku Hingga : SEUMUR HIDUP",
    )
    for i, line in enumerate(lines):
        draw.text((80, 225 + 62 * i), line, fill="black", font=_font(32))
    draw.text((80, 890), "SINTETIS - BUKAN DOKUMEN RESMI", fill=(170, 170, 170), font=_font(23))
    return image


def _perspective(image: Image.Image) -> Image.Image:
    """Apply a trapezoid transform via the Pillow 4-corner QUAD transformation."""
    w, h = image.size
    # Maps output rectangle corners to input corners; creates non-uniform skew.
    corners = (int(w * 0.10), int(h * 0.02), int(w * 0.05), int(h * 0.95),
               int(w * 0.96), int(h * 0.99), int(w * 0.90), int(h * 0.08))
    return image.transform((w, h), Image.Transform.QUAD, corners, Image.Resampling.BICUBIC,
                           fillcolor="white")



def make_perspective_photo(image: Image.Image, *, blur_radius: float = 0.0) -> Image.Image:
    """Render a fictional complete card on a contrasting background.

    Unlike the legacy `perspective` case, all four document corners and text
    remain inside the photograph, so rectification has information to recover.
    """
    import cv2
    import numpy as np

    card = np.asarray(image.convert("RGB"))
    h, w = card.shape[:2]
    corners = np.float32(((150, 130), (1600, 320), (1400, 1190), (210, 995)))
    matrix = cv2.getPerspectiveTransform(
        np.float32(((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1))), corners
    )
    shape = (1350, 1800)
    canvas = np.full((shape[0], shape[1], 3), 90, dtype=np.uint8)
    warped = cv2.warpPerspective(card, matrix, (shape[1], shape[0]), flags=cv2.INTER_CUBIC)
    mask = cv2.warpPerspective(
        np.full((h, w), 255, dtype=np.uint8), matrix,
        (shape[1], shape[0]), flags=cv2.INTER_NEAREST,
    )
    canvas[mask > 0] = warped[mask > 0]
    cv2.polylines(canvas, [corners.astype(np.int32)], True, (25, 25, 25), 7)
    photo = Image.fromarray(canvas)
    if blur_radius:
        return photo.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return photo


def distort(image: Image.Image, condition: str, seed: int) -> Image.Image:
    if condition == "clear":
        return image.copy()
    if condition == "blur_mild":
        return image.filter(ImageFilter.GaussianBlur(radius=1.3))
    if condition == "blur_medium":
        return image.filter(ImageFilter.GaussianBlur(radius=2.6))
    if condition == "rotate_12":
        return image.rotate(12, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white")
    if condition == "rotate_minus_18":
        return image.rotate(-18, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white")
    if condition == "perspective":
        return _perspective(image)
    if condition == "photo_perspective":
        return make_perspective_photo(image)
    if condition == "photo_perspective_blur":
        return make_perspective_photo(image, blur_radius=1.4)
    if condition == "low_light":
        return ImageEnhance.Contrast(ImageEnhance.Brightness(image).enhance(0.48)).enhance(0.55)
    if condition == "combined":
        rotated = image.rotate(12, expand=True, resample=Image.Resampling.BICUBIC,
                               fillcolor="white")
        return rotated.filter(ImageFilter.GaussianBlur(radius=2.0))
    raise ValueError(f"Unknown synthetic condition: {condition}")


CONDITIONS = ("clear", "blur_mild", "blur_medium", "rotate_12", "rotate_minus_18",
              "perspective", "photo_perspective", "photo_perspective_blur", "low_light", "combined")


def generate_synthetic(directory: Path, seed: int = 20261105) -> list[Fixture]:
    directory.mkdir(parents=True, exist_ok=True)
    cases: list[Fixture] = []
    rnd = Random(seed)
    for index, person in enumerate(SYNTHETIC_PEOPLE):
        base = _base_card(person)
        for condition in CONDITIONS:
            # Seed reserved for deterministic variations to the generators.
            rnd.random()
            image = distort(base, condition, seed + index)
            image_path = directory / f"synthetic_{index:02}_{condition}.png"
            image.save(image_path)
            image.close()
            cases.append(Fixture(
                image_path, condition, f"synthetic_person_{index}",
                {
                    "nik": person[0],
                    "nama": person[1],
                    "tempat_lahir": person[2],
                    "tanggal_lahir": person[3],
                    "alamat": "JALAN SINTETIS NOMOR 7",
                },
            ))
        base.close()
    return cases
