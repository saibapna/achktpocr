"""Convert private synthetic collector data into grouped OCR benchmark manifests.

Never logs identity values or image paths. Output stays beside the gitignored
collector input, not in the public repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmark.fixtures import distort  # noqa: E402

SOURCE = "cloverx-id/indonesian-id-card-dummy"
MONTHS = {
    "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4, "MEI": 5,
    "JUNI": 6, "JULI": 7, "AGUSTUS": 8, "SEPTEMBER": 9,
    "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
}
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[-/. ]\s*([A-Za-z]+|\d{1,2})\s*[-/. ]\s*(\d{4})(?!\d)", re.I)
AUGMENTED = ("blur_mild", "blur_medium", "rotate_12", "rotate_minus_18",
             "perspective", "low_light", "combined")


def parse_place_date(value: str) -> tuple[str, str]:
    """Return normalized place and DD-MM-YYYY; never infer an invalid date."""
    found = DATE_RE.search(value.strip())
    if not found:
        raise ValueError("Unrecognized date layout")
    day_raw, month_raw, year_raw = found.groups()
    month = MONTHS.get(month_raw.upper()) if month_raw.isalpha() else int(month_raw)
    if month is None:
        raise ValueError("Unrecognized Indonesian month")
    day, year = int(day_raw), int(year_raw)
    try:
        date(year, month, day)
    except ValueError:
        raise ValueError("Invalid date fields") from None
    return value[:found.start()].strip(" /,;:-\t"), f"{day:02d}-{month:02d}-{year:04d}"


def normalize_truth(source: dict[str, object]) -> dict[str, str]:
    if not isinstance(source, dict):
        raise ValueError("Invalid ground truth object")
    nik = str(source.get("nik") or "").strip()
    name = str(source.get("nama") or "").strip()
    address = str(source.get("alamat") or "").strip()
    if not re.fullmatch(r"[0-9]{16}", nik) or not name or not address:
        raise ValueError("Missing or invalid required synthetic fields")
    raw_birth = str(source.get("tempat_tanggal_lahir") or "").strip()
    place = str(source.get("tempat_lahir") or "").strip()
    dob = str(source.get("tanggal_lahir") or "").strip()
    if raw_birth:
        parsed_place, parsed_date = parse_place_date(raw_birth)
        place = place or parsed_place
        dob = dob or parsed_date
    if not place or not dob:
        raise ValueError("Missing date/place of birth")
    _, canonical_date = parse_place_date(dob)
    return {"nik": nik, "nama": name, "alamat": address,
            "tanggal_lahir": canonical_date, "tempat_lahir": place}


def safe_collector_image(raw: object, directory: Path) -> tuple[Path, str]:
    """Reject absolute/traversal/symlink paths outside the collector folder."""
    if not isinstance(raw, str) or not raw:
        raise ValueError("Missing image reference")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts or len(rel.parts) < 2 or rel.parts[0] != "images":
        raise ValueError("Unsafe collector image reference")
    full = (directory / rel).resolve()
    base = directory.resolve()
    if not full.is_relative_to(base) or not full.is_file():
        raise ValueError("Collector image unavailable or outside dataset")
    return full, rel.as_posix()


def read_collector(source: Path, limit: int) -> list[dict[str, object]]:
    """Minimize in-memory metadata; never copy annotations_json to the output."""
    if limit < 0:
        raise ValueError("Limit must not be negative")
    result: list[dict[str, object]] = []
    with source.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if limit and len(result) >= limit:
                break
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid JSON at collector row {line_no}") from None
            if not isinstance(row, dict):
                raise ValueError(f"Invalid collector row {line_no}")
            if row.get("source") != SOURCE or row.get("config") != "flat":
                raise ValueError("Only the reviewed synthetic flat source is supported")
            try:
                full, relative = safe_collector_image(row.get("file"), source.parent)
                truth = normalize_truth(row.get("ground_truth"))
            except ValueError:
                raise ValueError(f"Invalid collector record at row {line_no}") from None
            result.append({"full": full, "relative": relative, "truth": truth})
    if not result:
        raise ValueError("No usable collector records")
    return result


def group_split(
    rows: list[dict[str, object]], holdout_fraction: float, seed: int
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("Holdout fraction must be between 0 and 1")
    identities: dict[str, str] = {}
    for row in rows:
        truth = row["truth"]
        assert isinstance(truth, dict)
        nik = str(truth["nik"])
        if nik not in identities:
            identities[nik] = f"synthetic_group_{len(identities) + 1:06d}"
        row["group"] = identities[nik]
    ids = list(identities.values())
    if len(ids) < 2:
        raise ValueError("Need at least two independent synthetic identities")
    Random(seed).shuffle(ids)
    holdout_ids = set(ids[:max(1, min(len(ids) - 1, round(len(ids) * holdout_fraction)))])
    development = [r for r in rows if r["group"] not in holdout_ids]
    holdout = [r for r in rows if r["group"] in holdout_ids]
    return development, holdout


def _manifest_entry(row: dict[str, object], condition: str = "flat_clear") -> dict[str, object]:
    return {"image": row["relative"], "group": row["group"],
            "condition": condition, "ground_truth": row["truth"]}


def augment_holdout(
    source: Path, holdout: list[dict[str, object]], max_images: int,
    *, conditions: tuple[str, ...] = AUGMENTED
) -> list[dict[str, object]]:
    """Create controlled distortions of held-out *synthetic* images only."""
    if max_images < 0:
        raise ValueError("Invalid augmentation cap")
    count = len(holdout) * len(conditions)
    if count > max_images:
        raise ValueError("Augmentation cap exceeded; reduce --limit or raise --max-augment")
    from PIL import Image, ImageOps

    generated: list[dict[str, object]] = []
    directory = source.parent / "images" / "benchmark_generated"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for index, row in enumerate(holdout, 1):
        with Image.open(row["full"]) as original:
            source_image = ImageOps.exif_transpose(original).convert("RGB")
            for condition in conditions:
                image = distort(source_image, condition, seed=index)
                relative = f"images/benchmark_generated/case_{index:06d}_{condition}.png"
                path = source.parent / relative
                image.save(path, "PNG")
                image.close()
                item = dict(row)
                item["relative"] = relative
                generated.append(_manifest_entry(item, condition))
            source_image.close()
    return generated


def _atomic_jsonl(destination: Path, rows: list[dict[str, object]], overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        raise ValueError("Benchmark manifest exists; use --overwrite intentionally")
    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=destination.parent, prefix=".benchmark_", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.chmod(tmp_name, 0o600)
        Path(tmp_name).replace(destination)
    finally:
        if tmp_name and Path(tmp_name).exists():
            Path(tmp_name).unlink()


def convert(
    source: Path,
    *,
    limit: int = 100,
    seed: int = 20261105,
    holdout_fraction: float = 0.2,
    augment: bool = False,
    max_augment: int = 1200,
    overwrite: bool = False,
) -> dict[str, int]:
    """Produce local development and held-out manifests, preserving group separation."""
    if source.name != "ground_truth.jsonl":
        raise ValueError("Expected original collector ground_truth.jsonl")
    development_out = source.parent / "benchmark_development.jsonl"
    holdout_out = source.parent / "benchmark_holdout.jsonl"
    if not overwrite and (development_out.exists() or holdout_out.exists()):
        raise ValueError("Manifest already exists; use --overwrite to replace")
    rows = read_collector(source, limit)
    development, holdout = group_split(rows, holdout_fraction, seed)
    out_development = [_manifest_entry(row) for row in development]
    out_holdout = [_manifest_entry(row) for row in holdout]
    if augment:
        out_holdout.extend(augment_holdout(source, holdout, max_augment))
    _atomic_jsonl(development_out, out_development, overwrite)
    _atomic_jsonl(holdout_out, out_holdout, overwrite)
    return {
        "source_samples": len(rows),
        "development_cases": len(out_development),
        "holdout_cases": len(out_holdout),
        "development_groups": len({r["group"] for r in development}),
        "holdout_groups": len({r["group"] for r in holdout}),
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Private synthetic collector to benchmark converter")
    cli.add_argument("--source", type=Path,
                     default=Path("datasets/raw/huggingface/flat/ground_truth.jsonl"))
    cli.add_argument("--limit", type=int, default=100, help="Input images, 0=all")
    cli.add_argument("--holdout-fraction", type=float, default=0.2)
    cli.add_argument("--seed", type=int, default=20261105)
    cli.add_argument("--augment-holdout", action="store_true")
    cli.add_argument("--max-augment", type=int, default=1200)
    cli.add_argument("--overwrite", action="store_true")
    args = cli.parse_args()
    try:
        summary = convert(
            args.source, limit=args.limit, seed=args.seed,
            holdout_fraction=args.holdout_fraction,
            augment=args.augment_holdout,
            max_augment=args.max_augment,
            overwrite=args.overwrite,
        )
    except (ValueError, OSError) as exc:
        # Never print input paths or sensitive labels even when data is malformed.
        print(f"Conversion failed ({type(exc).__name__}); inspect private input and limits.",
              file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True))
    print("Private manifests created beside collector labels; no production model changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
