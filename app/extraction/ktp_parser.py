"""Read explicit labeled Indonesian KTP fields without fabricating missing data."""

import re
from datetime import datetime

from app.engines.rapidocr_engine import OCRLine
from app.schemas.response import FieldResult, KTPFields

_LABELS = [
    ("nik", r"N\s*[I1]\s*K"),
    ("nama", r"NAMA"),
    ("tanggal_tempat", r"TEMPAT\s*[/,\-]?\s*(?:TGL\.?|TANGGAL)\s*LAHIR"),
    ("tanggal_lahir", r"(?:TGL\.?|TANGGAL)\s*LAHIR"),
    ("jenis_kelamin", r"JENIS\s*KELAMIN"),
    ("gol_darah", r"GOL\.?\s*(?:DARAH|DRH)"),
    ("alamat", r"ALAMAT"),
    ("rt_rw", r"RT\s*[/\-]\s*RW"),
    ("kel_desa", r"(?:KEL(?:URAHAN)?\s*[/\-]\s*DESA|KEL(?:URAHAN)?|DESA)"),
    ("kecamatan", r"KECAMATAN"),
    ("agama", r"AGAMA"),
    ("status_perkawinan", r"STATUS\s*PERKAWINAN"),
    ("pekerjaan", r"PEKERJAAN"),
    ("kewarganegaraan", r"KEWARGANEGARAAN"),
    ("berlaku_hingga", r"BERLAKU\s*HINGGA"),
    ("provinsi", r"PROVINSI"),
    ("kabupaten_kota", r"(?:KABUPATEN|KAB\.?|KOTA)"),
]
_PATTERNS = [
    (name, re.compile(r"^\s*" + label + r"\b\s*[:;=\-]?\s*(.*?)\s*$", re.I))
    for name, label in _LABELS
]
_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*[-/\.]\s*(\d{1,2})\s*[-/\.]\s*(\d{4})(?!\d)")


def _assign(fields: KTPFields, field: str, value: str, confidence: float) -> None:
    value = value.strip(" \t:;=-")
    if value and not getattr(fields, field).value:
        setattr(
            fields,
            field,
            FieldResult(
                value=value,
                confidence=max(0.0, min(1.0, confidence)),
                source="rapidocr",
            ),
        )


def _extract_date(raw: str) -> tuple[str, str] | None:
    match = _DATE.search(raw)
    if not match:
        return None
    day, month, year = (int(item) for item in match.groups())
    try:
        datetime(year, month, day)
    except ValueError:
        return None
    place = raw[: match.start()].strip(" ,:;-")
    return place, f"{day:02d}-{month:02d}-{year:04d}"


def _validate(fields: KTPFields, warnings: list[str]) -> None:
    if not fields.nik.value:
        warnings.append("NIK tidak terbaca persis 16 digit; perlu pemeriksaan manual.")
    elif not re.fullmatch(r"[0-9]{16}", fields.nik.value):
        fields.nik.validation = "failed"
        fields.nik.warnings.append("NIK harus tepat 16 digit.")
        warnings.append("Format NIK tidak valid.")
    else:
        fields.nik.validation = "passed"
        day_encoded = int(fields.nik.value[6:8])
        day = day_encoded - 40 if day_encoded > 40 else day_encoded
        month = int(fields.nik.value[8:10])
        if not (1 <= day <= 31 and 1 <= month <= 12):
            fields.nik.validation = "warning"
            fields.nik.warnings.append("Segmen tanggal pada NIK perlu diperiksa.")
            warnings.append("Segmen tanggal pada NIK tidak wajar.")
        if fields.tanggal_lahir.value:
            try:
                date = datetime.strptime(fields.tanggal_lahir.value, "%d-%m-%Y")
            except ValueError:
                fields.tanggal_lahir.validation = "warning"
                warnings.append("Format tanggal lahir belum tervalidasi.")
            else:
                fields.tanggal_lahir.validation = "passed"
                if (
                    day != date.day
                    or month != date.month
                    or int(fields.nik.value[10:12]) != date.year % 100
                ):
                    fields.nik.validation = "warning"
                    fields.nik.warnings.append("Tanggal dalam NIK berbeda dari tanggal lahir OCR.")
                    warnings.append("Tanggal lahir dan segmen NIK tidak konsisten.")
    if not fields.nama.value:
        warnings.append("Nama tidak terbaca; perlu pemeriksaan manual.")
    if not fields.alamat.value:
        warnings.append("Alamat tidak terbaca; perlu pemeriksaan manual.")


def _merge_bounding_box_rows(lines: list[OCRLine]) -> list[OCRLine]:
    """Combine label/value boxes sharing one visual row, respecting horizontal order."""
    with_boxes = [line for line in lines if line.box and len(line.box) >= 4]
    if len(with_boxes) < 2:
        return lines
    measured = []
    for line in with_boxes:
        assert line.box is not None
        left = min(p[0] for p in line.box)
        top = min(p[1] for p in line.box)
        bottom = max(p[1] for p in line.box)
        measured.append((line, left, (top + bottom) / 2, max(1.0, bottom - top)))
    measured.sort(key=lambda item: (item[2], item[1]))
    rows: list[list[tuple[OCRLine, float, float, float]]] = []
    for item in measured:
        if rows:
            last = rows[-1]
            anchor = sum(segment[2] for segment in last) / len(last)
            threshold = max(7.0, min(item[3], last[0][3]) * 0.5)
            if abs(anchor - item[2]) <= threshold:
                last.append(item)
                continue
        rows.append([item])
    merged = [
        OCRLine(
            " ".join(segment[0].text for segment in sorted(row, key=lambda v: v[1])),
            min(segment[0].confidence for segment in row),
        )
        for row in rows
    ]
    merged.extend(line for line in lines if not line.box or len(line.box) < 4)
    return merged


def parse_ktp_lines(lines: list[OCRLine]) -> tuple[KTPFields, str, list[str]]:
    """Return fields, likely document type and PII-free warnings.

    Does not verify document authenticity or NIK registration.
    """
    lines = _merge_bounding_box_rows(lines)
    fields = KTPFields()
    warnings: list[str] = []
    matched_labels: set[str] = set()
    for i, line in enumerate(lines):
        value = line.text.strip()
        if not value:
            continue
        for name, pattern in _PATTERNS:
            match = pattern.match(value)
            if not match:
                continue
            matched_labels.add(name)
            raw_value = match.group(1).strip()
            if name == "nik":
                candidate = re.sub(r"\s", "", raw_value)
                if not candidate and i + 1 < len(lines):
                    candidate = re.sub(r"\s", "", lines[i + 1].text)
                if re.fullmatch(r"[0-9]{16}", candidate):
                    _assign(fields, "nik", candidate, line.confidence)
                else:
                    warnings.append("Label NIK ditemukan, tetapi 16 digit tidak dapat dipastikan.")
            elif name == "tanggal_tempat":
                parts = _extract_date(raw_value)
                if parts:
                    place, birth = parts
                    _assign(fields, "tempat_lahir", place, line.confidence)
                    _assign(fields, "tanggal_lahir", birth, line.confidence)
                else:
                    warnings.append("Tempat/tanggal lahir tidak berhasil dipisahkan.")
            elif name == "tanggal_lahir":
                parts = _extract_date(raw_value)
                if parts:
                    _assign(fields, "tanggal_lahir", parts[1], line.confidence)
            elif name == "jenis_kelamin":
                blood = re.search(
                    r"\bGOL\.?\s*(?:DARAH|DRH)\b\s*[:;=\-]?\s*(.*)$", raw_value, re.I
                )
                if blood:
                    _assign(fields, "gol_darah", blood.group(1), line.confidence)
                    raw_value = raw_value[: blood.start()]
                _assign(fields, name, raw_value, line.confidence)
            else:
                _assign(fields, name, raw_value, line.confidence)
            break

    _validate(fields, warnings)
    is_ktp = "nik" in matched_labels and bool(
        matched_labels.intersection({"nama", "tanggal_tempat", "jenis_kelamin", "alamat"})
    )
    kind = "ktp_el" if is_ktp else "unknown"
    if not is_ktp:
        warnings.append("Tidak cukup label untuk mengidentifikasi gambar sebagai KTP-el.")
    return fields, kind, list(dict.fromkeys(warnings))
