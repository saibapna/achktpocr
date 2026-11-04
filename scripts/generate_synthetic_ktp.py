"""Generate a completely fictional OCR test card (not a real or authentic KTP)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def generate(path: Path) -> None:
    canvas = Image.new("RGB", (1450, 930), "white")
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        body = ImageFont.truetype(font_path, 35)
        title = ImageFont.truetype(font_path, 50)
    except OSError:
        body = ImageFont.load_default()
        title = body
    draw.text((90, 60), "PROVINSI ACEH", fill="black", font=title)
    draw.text((90, 150), "KABUPATEN ACEH BESAR", fill="black", font=body)
    rows = [
        "NIK : 1101010101900001",
        "Nama : CONTOH FIKTIF",
        "Tempat/Tgl Lahir : BANDA ACEH, 01-01-1990",
        "Jenis Kelamin : LAKI-LAKI",
        "Alamat : JALAN CONTOH NO 1",
        "RT/RW : 001/002",
        "Kel/Desa : CONTOH",
        "Kecamatan : CONTOH",
        "Kewarganegaraan : WNI",
        "Berlaku Hingga : SEUMUR HIDUP",
    ]
    for index, row in enumerate(rows):
        draw.text((90, 260 + 59 * index), row, fill="black", font=body)
    canvas.save(path)


if __name__ == "__main__":
    generate(Path("synthetic-ktp.png"))
    print("Saved synthetic-ktp.png (fictional data only)")
