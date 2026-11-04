from app.engines.rapidocr_engine import OCRLine
from app.extraction.ktp_parser import parse_ktp_lines
from app.services.ocr_service import process_ktp


class FakeEngine:
    def __init__(self, lines):
        self.lines = lines

    def read(self, image):
        assert image == b"synthetic-image"
        return self.lines


def specimen_lines():
    return [
        OCRLine("PROVINSI ACEH", 0.95),
        OCRLine("KABUPATEN ACEH BESAR", 0.94),
        OCRLine("NIK : 1101010101900001", 0.99),
        OCRLine("Nama : CONTOH FIKTIF", 0.98),
        OCRLine("Tempat/Tgl Lahir : BANDA ACEH, 01-01-1990", 0.98),
        OCRLine("Jenis Kelamin : LAKI-LAKI Gol Darah : O", 0.93),
        OCRLine("Alamat : JALAN CONTOH NO 1", 0.97),
        OCRLine("RT/RW : 001/002", 0.99),
        OCRLine("Kel/Desa : CONTOH", 0.98),
        OCRLine("Kecamatan : CONTOH", 0.98),
        OCRLine("Agama : ISLAM", 0.98),
        OCRLine("Status Perkawinan : BELUM KAWIN", 0.98),
        OCRLine("Pekerjaan : PELAJAR", 0.98),
        OCRLine("Kewarganegaraan : WNI", 0.98),
        OCRLine("Berlaku Hingga : SEUMUR HIDUP", 0.99),
    ]


def test_parse_full_synthetic_ktp():
    fields, kind, warnings = parse_ktp_lines(specimen_lines())
    assert kind == "ktp_el"
    assert fields.nik.value == "1101010101900001"
    assert fields.nik.validation == "passed"
    assert fields.nama.value == "CONTOH FIKTIF"
    assert fields.tanggal_lahir.value == "01-01-1990"
    assert fields.tempat_lahir.value == "BANDA ACEH"
    assert fields.gol_darah.value == "O"
    assert fields.provinsi.value == "ACEH"
    assert not warnings


def test_process_ktp_with_fake_engine():
    result = process_ktp(b"synthetic-image", engine=FakeEngine(specimen_lines()))
    assert result.status == "success"
    assert result.document_type == "ktp_el"
    assert result.data["nik"] == "1101010101900001"


def test_does_not_invent_nik_digits():
    lines = [OCRLine("NIK : 110101O101900001", 0.90), OCRLine("Nama: CONTOH", 0.95)]
    fields, kind, warnings = parse_ktp_lines(lines)
    assert kind == "ktp_el"
    assert fields.nik.value is None
    assert any("NIK" in warning for warning in warnings)
    result = process_ktp(b"synthetic-image", engine=FakeEngine(lines))
    assert result.status == "partial"


def test_detects_nik_dob_inconsistency():
    lines = specimen_lines()
    lines[4] = OCRLine("Tempat/Tgl Lahir: BANDA ACEH, 02-01-1990", 0.98)
    fields, _, warnings = parse_ktp_lines(lines)
    assert fields.nik.validation == "warning"
    assert any("tidak konsisten" in warning for warning in warnings)


def test_rejects_random_text_as_ktp():
    result = process_ktp(
        b"synthetic-image",
        engine=FakeEngine([OCRLine("Nomor Rekening 1101010101900001", 0.99)]),
    )
    assert result.document_type == "unknown"
    assert result.status == "failed"
    assert result.data["nik"] is None


def test_nik_can_be_on_next_line_if_exact():
    lines = [
        OCRLine("NIK:", 0.95),
        OCRLine("1101010101900001", 0.95),
        OCRLine("Nama: CONTOH FIKTIF", 0.95),
    ]
    fields, kind, _ = parse_ktp_lines(lines)
    assert kind == "ktp_el"
    assert fields.nik.value == "1101010101900001"


def test_merges_ocr_split_columns_using_geometry():
    def box(x0, y0, x1, y1):
        return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))

    lines = [
        OCRLine("Nama", 0.99, box(40, 100, 125, 125)),
        OCRLine(": CONTOH FIKTIF", 0.98, box(145, 101, 350, 125)),
        OCRLine("NIK", 0.99, box(40, 60, 125, 85)),
        OCRLine(": 1101010101900001", 0.99, box(145, 61, 400, 85)),
        OCRLine("Tempat/Tgl Lahir", 0.99, box(40, 145, 200, 170)),
        OCRLine(": BANDA ACEH, 01-01-1990", 0.95, box(211, 145, 500, 170)),
        OCRLine("Alamat : JALAN CONTOH NO 1", 0.96, box(40, 190, 500, 215)),
    ]
    fields, kind, warnings = parse_ktp_lines(lines)
    assert kind == "ktp_el"
    assert fields.nik.value == "1101010101900001"
    assert fields.nama.value == "CONTOH FIKTIF"
    assert fields.tanggal_lahir.value == "01-01-1990"
    assert not warnings
