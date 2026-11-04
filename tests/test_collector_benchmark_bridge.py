"""Never use real personal data in tests of the collector adapter."""

import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.prepare_collector_benchmark import (
    convert,
    group_split,
    normalize_truth,
    parse_place_date,
    read_collector,
    safe_collector_image,
)
from app.benchmark.runner import read_manifest


def _synthetic_root(tmp_path: Path, n: int = 8, duplicate: bool = False) -> Path:
    root = tmp_path / "flat"
    (root / "images").mkdir(parents=True)
    source = root / "ground_truth.jsonl"
    with source.open("w", encoding="utf-8") as handle:
        for index in range(n):
            path = root / "images" / f"fake_{index:03}.png"
            Image.new("RGB", (120, 65), "white").save(path)
            nik_suffix = index if not (duplicate and index == 1) else 0
            row = {
                "file": f"images/fake_{index:03}.png",
                "source": "cloverx-id/indonesian-id-card-dummy", "config": "flat",
                "ground_truth": {
                    "nik": f"000000010190{nik_suffix:04d}",
                    "nama": "PENGUJIAN FIKTIF",
                    "alamat": "JALAN CONTOH 5",
                    "tempat_tanggal_lahir": "BANDA ACEH, 01-01-1990",
                    "annotations_json": "SENSITIVE, DO NOT SERIALIZE",
                },
            }
            handle.write(json.dumps(row) + "\n")
    return source


def test_indonesian_months_and_numeric_date():
    assert parse_place_date("BANDA ACEH, 2 Agustus 2003") == ("BANDA ACEH", "02-08-2003")
    assert parse_place_date("MEDAN, 01/01/1990") == ("MEDAN", "01-01-1990")


def test_invalid_dates_are_not_invented():
    with pytest.raises(ValueError):
        parse_place_date("BANDA ACEH, 31-02-2001")
    with pytest.raises(ValueError):
        parse_place_date("BANDA ACEH, 01 imaginary 2001")


def test_normalizes_only_required_fields():
    truth = normalize_truth({
        "nik": "0000000101900001", "nama": "FAKE USER", "alamat": "ROAD ONE",
        "tempat_tanggal_lahir": "BANDA ACEH, 1 JANUARI 1990", "annotations_json": "NOPE",
    })
    assert truth == {"nik": "0000000101900001", "nama": "FAKE USER",
                     "alamat": "ROAD ONE", "tempat_lahir": "BANDA ACEH",
                     "tanggal_lahir": "01-01-1990"}


def test_rejects_traversal_and_symlink(tmp_path):
    folder = tmp_path / "flat"
    (folder / "images").mkdir(parents=True)
    with pytest.raises(ValueError):
        safe_collector_image("images/../../secret.png", folder)
    with pytest.raises(ValueError):
        safe_collector_image("/tmp/data.jpg", folder)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"x")
    (folder / "images" / "link.jpg").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_collector_image("images/link.jpg", folder)


def test_flat_only_and_limit(tmp_path):
    source = _synthetic_root(tmp_path, 4)
    assert len(read_collector(source, limit=2)) == 2
    rows = [json.loads(x) for x in source.read_text().splitlines()]
    rows[0]["config"] = "augmented"
    source.write_text("\n".join(map(json.dumps, rows)) + "\n")
    with pytest.raises(ValueError, match="synthetic flat"):
        read_collector(source, limit=2)


def test_group_split_is_identity_separated_and_reproducible(tmp_path):
    source = _synthetic_root(tmp_path, 8, duplicate=True)
    a = read_collector(source, 0)
    dev, hold = group_split(a, 0.4, 42)
    assert len(set(r["group"] for r in dev) & set(r["group"] for r in hold)) == 0
    assert len(set(r["group"] for r in a)) == 7
    b = read_collector(source, 0)
    dev2, hold2 = group_split(b, 0.4, 42)
    assert [x["relative"] for x in dev] == [x["relative"] for x in dev2]
    assert [x["relative"] for x in hold] == [x["relative"] for x in hold2]


def test_convert_produces_readable_private_manifest(tmp_path):
    source = _synthetic_root(tmp_path, 10)
    summary = convert(source, limit=10, seed=42, holdout_fraction=0.2)
    assert summary == {"source_samples": 10, "development_cases": 8,
                       "holdout_cases": 2, "development_groups": 8,
                       "holdout_groups": 2}
    holdout_file = source.parent / "benchmark_holdout.jsonl"
    development_file = source.parent / "benchmark_development.jsonl"
    assert holdout_file.stat().st_mode & 0o077 == 0
    assert development_file.stat().st_mode & 0o077 == 0
    fixture = read_manifest(holdout_file)
    assert len(fixture) == 2
    assert fixture[0].condition == "flat_clear"
    assert "tanggal_lahir" in fixture[0].truth
    assert "annotations_json" not in holdout_file.read_text()
    with pytest.raises(ValueError, match="already exists"):
        convert(source)


def test_augmentation_only_on_holdout(tmp_path):
    source = _synthetic_root(tmp_path, 8)
    result = convert(source, limit=8, holdout_fraction=0.25,
                     augment=True, max_augment=20)
    assert result["holdout_cases"] == 2 * 8
    entries = read_manifest(source.parent / "benchmark_holdout.jsonl")
    assert len(entries) == 16
    assert len({x.group for x in entries}) == 2
    assert {x.condition for x in entries} == {"flat_clear", "blur_mild",
        "blur_medium", "rotate_12", "rotate_minus_18", "perspective",
        "low_light", "combined"}
    assert len(read_manifest(source.parent / "benchmark_development.jsonl")) == 6


def test_augmentation_cap_is_fail_closed(tmp_path):
    source = _synthetic_root(tmp_path, 8)
    with pytest.raises(ValueError, match="cap"):
        convert(source, limit=8, augment=True, max_augment=1)
    assert not (source.parent / "benchmark_holdout.jsonl").exists()


def test_errors_never_log_labels(tmp_path, capsys):
    source = _synthetic_root(tmp_path, 3)
    rows = [json.loads(x) for x in source.read_text().splitlines()]
    rows[0]["ground_truth"]["nik"] = "1111111111111111"
    rows[0]["ground_truth"]["tempat_tanggal_lahir"] = "PRIVATECITY, not-a-date"
    source.write_text("\n".join(map(json.dumps, rows)) + "\n")
    # The library raises a generic line number, not the raw input value.
    with pytest.raises(ValueError) as exc:
        convert(source, limit=3)
    assert "1111111111111111" not in str(exc.value)
    assert "PRIVATECITY" not in str(exc.value)
    assert "1111111111111111" not in capsys.readouterr().out
