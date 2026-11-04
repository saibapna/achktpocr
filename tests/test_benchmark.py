"""Privacy and fairness regression tests for the offline benchmark."""

import json
from pathlib import Path

import pytest
from PIL import Image

from app.benchmark.adapters import TesseractAdapter, parse_tesseract_tsv
from app.benchmark.fixtures import Fixture, distort
from app.benchmark.runner import (_distance, _pct, read_manifest, report_to_file,
                                  run_comparison)
from app.engines.rapidocr_engine import OCRLine


class PerfectEngine:
    name = "test-perfect"

    def read(self, _image: bytes) -> list[OCRLine]:
        return [
            OCRLine("NIK : 0000000101900001", 0.99),
            OCRLine("Nama : CONTOH FIKTIF", 0.99),
            OCRLine("Tempat/Tgl Lahir : BANDA ACEH, 01-01-1990", 0.99),
            OCRLine("Alamat : JALAN SINTETIS NOMOR 7", 0.99),
        ]


class BrokenEngine:
    name = "test-error"

    def read(self, _image: bytes) -> list[OCRLine]:
        raise RuntimeError("secret raw OCR 0000000101900001")


def _case(tmp_path: Path) -> Fixture:
    image = tmp_path / "private-name.png"
    Image.new("RGB", (100, 100), "white").save(image)
    return Fixture(
        image, "clear", "group_1",
        {"nik": "0000000101900001", "nama": "CONTOH FIKTIF",
         "tanggal_lahir": "01-01-1990", "tempat_lahir": "BANDA ACEH",
         "alamat": "JALAN SINTETIS NOMOR 7"},
    )


def test_edit_distance():
    assert _distance("ABC", "ABC") == 0
    assert _distance("NAMA", "NANA") == 1
    assert _distance("", "16") == 2
    assert _pct([10, 20, 30], 95) == 29.0
    assert _pct([], 50) is None


def test_tesseract_tsv_group_words_and_confidence():
    data = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t20\t30\t50\t30\t93.5\tNIK\n"
        "5\t1\t1\t1\t1\t2\t75\t30\t250\t30\t86.4\t0000000101900001\n"
        "5\t1\t1\t1\t2\t1\t20\t70\t60\t30\t90\tNama\n"
        "5\t1\t1\t1\t2\t2\t85\t70\t190\t30\t91\tCONTOH\n"
    )
    lines = parse_tesseract_tsv(data)
    assert len(lines) == 2
    assert lines[0].text == "NIK 0000000101900001"
    assert lines[0].confidence == pytest.approx(0.864)
    assert lines[0].box[0] == (20, 30)
    assert lines[0].box[2] == (325, 60)


def test_perfect_engine_exact_match_and_no_pii_in_report(tmp_path):
    case = _case(tmp_path)
    report = run_comparison([case], {"fake": PerfectEngine()}, ["raw"], dataset_kind="synthetic")
    row = report["summary"][0]
    assert row["fields"]["nik"]["exact_rate"] == 1
    assert row["fields"]["tanggal_lahir"]["exact_rate"] == 1
    assert report["promotion_eligible"] is False
    output = tmp_path / "report.json"
    report_to_file(report, output)
    contents = output.read_text()
    assert "0000000101900001" not in contents
    assert "CONTOH FIKTIF" not in contents
    assert str(case.image) not in contents
    assert "private-name" not in contents
    assert "fake" in contents


def test_errors_are_counted_as_incorrect_not_dropped(tmp_path):
    report = run_comparison(
        [_case(tmp_path)], {"broken": BrokenEngine()}, ["raw"],
        dataset_kind="synthetic", allow_errors=True
    )
    row = report["summary"][0]
    assert row["errors"] == 1
    assert row["cases"] == 1
    assert row["fields"]["nik"]["exact_rate"] == 0.0
    assert row["fields"]["nik"]["cer"] == 1.0
    assert "secret raw OCR" not in json.dumps(report)


def test_failure_fails_closed_without_raw_error(tmp_path):
    with pytest.raises(RuntimeError, match="aborted to avoid misleading metrics") as err:
        run_comparison([_case(tmp_path)], {"broken": BrokenEngine()}, ["raw"],
                       dataset_kind="synthetic")
    assert "secret raw OCR" not in str(err.value)


def test_manifest_rejects_escape_and_never_reports_path(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    manifest = private / "manifest.jsonl"
    manifest.write_text(json.dumps({"image": "../outside.png", "ground_truth": {"nik": "0"}}))
    with pytest.raises(ValueError, match="inside manifest"):
        read_manifest(manifest)


def test_manifest_reads_valid_fixture(tmp_path):
    case = _case(tmp_path)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image": "private-name.png", "group": "card-A",
                                    "condition": "blur_mild", "ground_truth": case.truth}) + "\n")
    parsed = read_manifest(manifest)
    assert parsed[0].group == "card-A"
    assert parsed[0].truth["nama"] == "CONTOH FIKTIF"


def test_synthetic_distortions_deterministic():
    img = Image.new("RGB", (320, 120), "white")
    for cond in ("clear", "blur_mild", "blur_medium", "rotate_12", "rotate_minus_18",
                 "perspective", "low_light", "combined"):
        first = distort(img, cond, seed=20261105)
        second = distort(img, cond, seed=20261105)
        assert first.tobytes() == second.tobytes()
    with pytest.raises(ValueError):
        distort(img, "unknown", seed=42)


def test_reject_unsupported_preprocessing(tmp_path):
    with pytest.raises(ValueError, match="Unknown preprocessing"):
        run_comparison([_case(tmp_path)], {"fake": PerfectEngine()}, ["hallucination"],
                       dataset_kind="synthetic")


def test_tesseract_model_must_be_present(tmp_path):
    with pytest.raises(FileNotFoundError):
        TesseractAdapter(tessdata_dir=tmp_path, lang="ktp")
