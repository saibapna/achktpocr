"""Regression checks for privacy-safe paired benchmark acceptance metrics."""

from app.benchmark.runner import PairedCounts, run_comparison
from app.engines.rapidocr_engine import OCRLine
from tests.test_benchmark import BrokenEngine, PerfectEngine, _case


class VariantAwareEngine:
    name = "synthetic-variant"

    def read(self, image: bytes) -> list[OCRLine]:
        nik = "0000000101900001" if image == b"deskew" else "0000000101900002"
        return [
            OCRLine(f"NIK : {nik}", 0.99),
            OCRLine("Nama : CONTOH FIKTIF", 0.99),
        ]


def test_paired_counts_detect_improvement_and_regression():
    counts = PairedCounts()
    counts.add(True, True)
    counts.add(True, False)
    counts.add(False, True)
    counts.add(False, False)
    assert counts.summary() == {
        "both_correct": 1,
        "baseline_only": 1,
        "candidate_only": 1,
        "both_wrong": 1,
    }


def test_runner_compares_identical_cases_across_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.benchmark.runner.normalize_image",
        lambda _image, variant: variant.encode("ascii"),
    )
    report = run_comparison(
        [_case(tmp_path)],
        {"fixture-engine": VariantAwareEngine()},
        ["raw", "deskew"],
        dataset_kind="synthetic",
    )
    assert [row for row in report["paired_nik_variants"] if row["condition"] == "clear"] == [
        {
            "engine": "fixture-engine",
            "baseline": "raw",
            "candidate": "deskew",
            "condition": "clear",
            "both_correct": 0,
            "baseline_only": 0,
            "candidate_only": 1,
            "both_wrong": 0,
        }
    ]
    for row in report["summary"]:
        assert "variant_preprocessing_ms" in row
        assert "inference_plus_variant_ms" in row
    assert len(report["overall"]) == 2
    assert report["overall"][0]["cases"] == 1


def test_engine_pair_counts_errors_as_incorrect(tmp_path):
    report = run_comparison(
        [_case(tmp_path)],
        {"primary": PerfectEngine(), "secondary": BrokenEngine()},
        ["raw"],
        dataset_kind="synthetic",
        allow_errors=True,
    )
    paired = report["paired_nik_engines"][0]
    assert paired["baseline_engine"] == "primary"
    assert paired["candidate_engine"] == "secondary"
    assert paired["baseline_only"] == 1
    assert paired["candidate_only"] == 0
    assert paired["both_wrong"] == 0
