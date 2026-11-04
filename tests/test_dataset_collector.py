"""Offline safety and catalog tests for the optional KTP collector."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


COLLECTOR = Path(__file__).resolve().parents[1] / "datasets" / "collector" / "collector.py"
spec = importlib.util.spec_from_file_location("ktp_dataset_collector", COLLECTOR)
assert spec is not None and spec.loader is not None
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_all_twelve_sources() -> None:
    sources = collector.load_catalog()
    assert len(sources) == 12
    assert len({item["id"] for item in sources}) == 12
    assert any(item["type"].startswith("real-") for item in sources)


def test_filename_sanitization() -> None:
    assert collector.safe_name("../../secret path/ktp:image.jpg", 4) == "000004_ktp_image"


def test_augmented_requires_authorization(tmp_path: Path) -> None:
    args = argparse.Namespace(config="augmented", limit=1, out=str(tmp_path), ack_authorization=False)
    with pytest.raises(SystemExit, match="Denied: augmented"):
        collector.hf(args)


def test_review_github_requires_permission(tmp_path: Path) -> None:
    args = argparse.Namespace(group="review", out=str(tmp_path), ack_authorization=False)
    with pytest.raises(SystemExit, match="Denied:"):
        collector.github(args)


def test_roboflow_requires_permission(tmp_path: Path) -> None:
    args = argparse.Namespace(out=str(tmp_path), ack_authorization=False)
    with pytest.raises(SystemExit, match="Denied:"):
        collector.roboflow(args)


def test_default_all_does_not_touch_restricted_sources() -> None:
    args = collector.make_parser().parse_args(["all"])
    assert args.config == "flat"
    assert args.limit == 100
    assert not args.ack_authorization
