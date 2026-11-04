"""CPU benchmark entrypoint: both engines, identical KTP fixture images.

Examples:
  python scripts/benchmark_ocr.py --synthetic --tessdata-dir models/benchmark
  python scripts/benchmark_ocr.py --manifest /private/heldout/manifest.jsonl \
      --tessdata-dir models/benchmark
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Supports calling this file directly from repository root and Docker WORKDIR.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmark.fixtures import generate_synthetic  # noqa: E402
from app.benchmark.runner import (  # noqa: E402
    build_engines,
    read_manifest,
    report_to_file,
    run_comparison,
)


def main() -> int:
    cli = argparse.ArgumentParser(description="Paired RapidOCR vs Tesseract traineddata benchmark")
    data = cli.add_mutually_exclusive_group(required=True)
    data.add_argument("--synthetic", action="store_true", help="Fictional synthetic fixture tests")
    data.add_argument(
        "--manifest", type=Path, help="Private JSONL manifest with images and verified GT"
    )
    cli.add_argument("--engines", default="rapidocr,tesseract-ktp", help="Comma-separated engines")
    cli.add_argument("--variants", default="raw,gray", help="raw,gray,contrast,unsharp")
    cli.add_argument("--tessdata-dir", type=Path, help="Directory containing ktp.traineddata")
    cli.add_argument("--seed", type=int, default=20261105)
    cli.add_argument("--output", type=Path, default=Path("reports/ocr_benchmark.json"))
    cli.add_argument("--allow-errors", action="store_true", help="Count engine errors explicitly")
    args = cli.parse_args()
    names = [name.strip() for name in args.engines.split(",") if name.strip()]
    variants = [name.strip() for name in args.variants.split(",") if name.strip()]
    try:
        engines = build_engines(names, args.tessdata_dir)
        with tempfile.TemporaryDirectory(prefix="ktp-ocr-benchmark-") as tmpdir:
            if args.synthetic:
                cases = generate_synthetic(Path(tmpdir), seed=args.seed)
                kind = "synthetic_smoke_not_real_ktp_accuracy"
            else:
                cases = read_manifest(args.manifest)
                kind = "private_holdout_unverified_by_tool"
            report = run_comparison(
                cases, engines, variants, dataset_kind=kind, allow_errors=args.allow_errors
            )
        report_to_file(report, args.output)
        print(
            f"Benchmark complete: {report['sample_count']} samples, "
            f"{len(report['summary'])} aggregate groups"
        )
        print(f"Aggregate output: {args.output}")
        print("No model promoted; reviewer must verify real held-out accuracy and licensing.")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        # Avoid raw exception details: they might include private image paths.
        print(
            f"Benchmark could not complete: {type(exc).__name__}. "
            "Check dependencies, model, and input.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
