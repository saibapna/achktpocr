"""Paired OCR benchmark. No raw text, NIK or user image paths in its output."""

import json
import math
import platform
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.benchmark.adapters import BenchmarkEngine, RapidOCRAdapter, TesseractAdapter
from app.benchmark.fixtures import Fixture
from app.extraction.ktp_parser import parse_ktp_lines
from app.preprocessing.image_loader import prepare_image

FIELDS = ("nik", "nama", "tanggal_lahir", "tempat_lahir", "alamat")
PREPROCESS = ("raw", "gray", "contrast", "unsharp", "deskew", "perspective", "perspective_deskew")


def _normalized(value: str | None) -> str:
    return " ".join((value or "").strip().upper().split())


def _distance(a: str, b: str) -> int:
    """Levenshtein character edit distance, bounded memory."""
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for i, character in enumerate(b, 1):
        curr = [i]
        for j, match in enumerate(a, 1):
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (character != match)))
        prev = curr
    return prev[-1]


def _pct(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 2)


def normalize_image(data: bytes, name: str) -> bytes:
    """Apply strictly defined ablations, never fabricate characters."""
    if name == "raw":
        return data
    if name not in PREPROCESS:
        raise ValueError("Unsupported preprocessing variant")
    if name == "deskew":
        from app.benchmark.geometry import deskew_png

        return deskew_png(data)
    if name in ("perspective", "perspective_deskew"):
        from app.benchmark.perspective import perspective_png

        corrected = perspective_png(data)
        if name == "perspective_deskew":
            from app.benchmark.geometry import deskew_png

            return deskew_png(corrected)
        return corrected
    import io

    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        if name == "gray":
            image = ImageOps.grayscale(image).convert("RGB")
        elif name == "contrast":
            image = ImageEnhance.Contrast(image).enhance(1.5)
        elif name == "unsharp":
            image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        out = io.BytesIO()
        image.save(out, format="PNG")
        image.close()
        return out.getvalue()


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def build_engines(names: list[str], tessdata_dir: Path | None) -> dict[str, BenchmarkEngine]:
    engines: dict[str, BenchmarkEngine] = {}
    for name in names:
        if name == "rapidocr":
            try:
                engines[name] = RapidOCRAdapter()
            except (ImportError, OSError) as exc:
                raise RuntimeError("rapidocr unavailable: install .[ocr]") from exc
        elif name.startswith("tesseract-"):
            lang = name.removeprefix("tesseract-")
            directory = tessdata_dir or Path("/usr/share/tesseract-ocr/5/tessdata")
            engines[name] = TesseractAdapter(tessdata_dir=directory, lang=lang)
        else:
            raise ValueError(f"Unknown engine: {name}")
    return engines


@dataclass
class Counter:
    fields: dict[str, dict[str, int]]
    timings_ms: list[float]
    variant_timings_ms: list[float]
    statuses: dict[str, int]
    errors: int
    total: int

    @classmethod
    def create(cls) -> "Counter":
        return cls(defaultdict(lambda: {"gt": 0, "read": 0, "correct": 0, "edit": 0, "chars": 0}),
                   [], [], defaultdict(int), 0, 0)

    def add(
        self,
        truth: dict[str, str],
        fields: object,
        state: str,
        millis: float,
        variant_ms: float = 0.0,
    ) -> None:
        self.total += 1
        self.timings_ms.append(millis)
        self.variant_timings_ms.append(variant_ms)
        self.statuses[state] += 1
        for name in FIELDS:
            if name not in truth:
                continue
            gt = _normalized(truth[name])
            if not gt:
                continue
            predicted = _normalized(getattr(fields, name).value)
            ctr = self.fields[name]
            ctr["gt"] += 1
            ctr["read"] += int(bool(predicted))
            ctr["correct"] += int(predicted == gt)
            ctr["edit"] += _distance(predicted, gt)
            ctr["chars"] += len(gt)

    def add_error(self, truth: dict[str, str], elapsed_ms: float, variant_ms: float = 0.0) -> None:
        self.errors += 1
        self.total += 1
        self.timings_ms.append(elapsed_ms)
        self.variant_timings_ms.append(variant_ms)
        self.statuses["error"] += 1
        for name in FIELDS:
            if name in truth and _normalized(truth[name]):
                gt = _normalized(truth[name])
                ctr = self.fields[name]
                ctr["gt"] += 1
                ctr["edit"] += len(gt)
                ctr["chars"] += len(gt)

    def summary(self) -> dict[str, object]:
        fields = {
            name: {
                "samples": x["gt"],
                "exact_count": x["correct"],
                "exact_rate": round(x["correct"] / x["gt"], 4) if x["gt"] else None,
                "read_rate": round(x["read"] / x["gt"], 4) if x["gt"] else None,
                "cer": round(x["edit"] / x["chars"], 4) if x["chars"] else None,
            }
            for name, x in self.fields.items()
        }
        return {
            "cases": self.total,
            "errors": self.errors,
            "statuses": dict(self.statuses),
            "fields": fields,
            "latency_ms": {"p50": _pct(self.timings_ms, 50), "p95": _pct(self.timings_ms, 95)},
            # Variant time is tracked separately to avoid hiding deskew CPU cost.
            # The common decode/prepare_image stage is excluded for both variants.
            "variant_preprocessing_ms": {
                "p50": _pct(self.variant_timings_ms, 50),
                "p95": _pct(self.variant_timings_ms, 95),
            },
            "inference_plus_variant_ms": {
                "p50": _pct([x + y for x, y in zip(self.timings_ms, self.variant_timings_ms)], 50),
                "p95": _pct([x + y for x, y in zip(self.timings_ms, self.variant_timings_ms)], 95),
            },
        }


@dataclass
class PairedCounts:
    """Only publish outcome totals, never per-document predictions or identifiers."""

    both_correct: int = 0
    baseline_only: int = 0
    candidate_only: int = 0
    both_wrong: int = 0

    def add(self, baseline: bool, candidate: bool) -> None:
        if baseline and candidate:
            self.both_correct += 1
        elif baseline:
            self.baseline_only += 1
        elif candidate:
            self.candidate_only += 1
        else:
            self.both_wrong += 1

    def summary(self) -> dict[str, int]:
        return {
            "both_correct": self.both_correct,
            "baseline_only": self.baseline_only,
            "candidate_only": self.candidate_only,
            "both_wrong": self.both_wrong,
        }


def run_comparison(
    cases: Iterable[Fixture],
    engines: dict[str, BenchmarkEngine],
    variants: list[str],
    *,
    dataset_kind: str,
    allow_errors: bool = False,
) -> dict[str, object]:
    """Run all engines on the same images and truth. Results are aggregate only."""
    if not engines or not variants:
        raise ValueError("At least one engine and preprocessing variant required")
    if any(x not in PREPROCESS for x in variants):
        raise ValueError("Unknown preprocessing variant")
    cases = list(cases)
    if not cases:
        raise ValueError("No benchmark cases supplied")
    counters: dict[tuple[str, str, str], Counter] = defaultdict(Counter.create)
    overall_counters: dict[tuple[str, str], Counter] = defaultdict(Counter.create)
    variant_pair_counts: dict[tuple[str, str, str], PairedCounts] = defaultdict(PairedCounts)
    engine_pair_counts: dict[tuple[str, str, str], PairedCounts] = defaultdict(PairedCounts)
    model_metadata = {
        name: {"model_sha256": getattr(engine, "model_sha256", None)}
        for name, engine in engines.items()
    }
    for case in cases:
        original = case.image.read_bytes()
        prepared = prepare_image(original, max_side=2500, max_dimension=8000, max_pixels=16_000_000)
        nik_correct: dict[tuple[str, str], bool] = {}
        for variant in variants:
            variant_start = time.perf_counter()
            data = normalize_image(prepared, variant)
            variant_ms = (time.perf_counter() - variant_start) * 1000
            for name, engine in engines.items():
                ctr = counters[(name, variant, case.condition)]
                overall_ctr = overall_counters[(name, variant)]
                start = time.perf_counter()
                try:
                    lines = engine.read(data)
                    fields, kind, _warnings = parse_ktp_lines(lines)
                except Exception:
                    # Never include raw errors/filenames, which may contain personal data.
                    elapsed = (time.perf_counter() - start) * 1000
                    for counter in (ctr, overall_ctr):
                        counter.add_error(case.truth, elapsed, variant_ms)
                    nik_correct[(name, variant)] = False
                    if not allow_errors:
                        raise RuntimeError(
                            f"OCR engine {name} failed; aborted to avoid misleading metrics"
                        ) from None
                    continue
                elapsed = (time.perf_counter() - start) * 1000
                status = "ktp" if kind == "ktp_el" else "unknown"
                for counter in (ctr, overall_ctr):
                    counter.add(case.truth, fields, status, elapsed, variant_ms)
                gt_nik = _normalized(case.truth.get("nik"))
                nik_correct[(name, variant)] = bool(gt_nik) and (
                    _normalized(fields.nik.value) == gt_nik
                )

        # Compare identical cases, rather than unrelated aggregate percentages.
        # Never serialize any case-level outcome or truth from this local dict.
        if _normalized(case.truth.get("nik")):
            for engine in engines:
                if "raw" in variants:
                    for variant in variants:
                        if variant != "raw":
                            variant_pair_counts[(engine, variant, case.condition)].add(
                                nik_correct[(engine, "raw")], nik_correct[(engine, variant)]
                            )
                            variant_pair_counts[(engine, variant, "all")].add(
                                nik_correct[(engine, "raw")], nik_correct[(engine, variant)]
                            )
            engine_names = list(engines)
            if len(engine_names) >= 2:
                primary = engine_names[0]
                for candidate in engine_names[1:]:
                    for variant in variants:
                        engine_pair_counts[(candidate, variant, case.condition)].add(
                            nik_correct[(primary, variant)], nik_correct[(candidate, variant)]
                        )
                        engine_pair_counts[(candidate, variant, "all")].add(
                            nik_correct[(primary, variant)], nik_correct[(candidate, variant)]
                        )

    summary = []
    for (name, variant, condition), ctr in sorted(counters.items()):
        summary.append({"engine": name, "preprocess": variant, "condition": condition,
                        **ctr.summary()})
    # Synthetic images cannot establish accuracy on photographed real KTPs.
    return {
        "schema_version": 1,
        "dataset_kind": dataset_kind,
        "sample_count": len(cases),
        "independent_groups": len({case.group for case in cases}),
        "engines": model_metadata,
        "variants": variants,
        "summary": summary,
        "overall": [
            {"engine": name, "preprocess": variant, **counter.summary()}
            for (name, variant), counter in sorted(overall_counters.items())
        ],
        "paired_nik_variants": [
            {"engine": name, "baseline": "raw", "candidate": variant,
             "condition": condition, **counts.summary()}
            for (name, variant, condition), counts in sorted(variant_pair_counts.items())
        ],
        "paired_nik_engines": [
            {"baseline_engine": next(iter(engines)), "candidate_engine": candidate,
             "preprocess": variant, "condition": condition, **counts.summary()}
            for (candidate, variant, condition), counts in sorted(engine_pair_counts.items())
        ],
        "promotion_eligible": False,
        "reason": (
            "Candidate needs a sufficiently sized, authorized real held-out dataset, "
            "manual approval, and a license/provenance review before any deployment."
        ),
        "privacy": (
            "Only aggregate metrics; no source paths, raw OCR text, NIK "
            "or ground truth serialized."
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "rapidocr_version": _package_version("rapidocr"),
            "onnxruntime_version": _package_version("onnxruntime"),
        },
    }


def read_manifest(file: Path) -> list[Fixture]:
    """Read private JSONL; reject relative path escapes; never print samples."""
    root = file.parent.resolve()
    cases = []
    with file.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError(f"Invalid JSONL record at line {lineno}")
            rel = Path(data["image"])
            image = (root / rel).resolve()
            if image != root and root not in image.parents:
                raise ValueError("Image path must be inside manifest directory")
            if not image.is_file():
                raise ValueError(f"Image missing at manifest line {lineno}")
            if not isinstance(data.get("ground_truth"), dict):
                raise ValueError(f"Missing ground_truth at manifest line {lineno}")
            cases.append(Fixture(image, str(data.get("condition", "unknown")),
                                 str(data.get("group", f"row_{lineno}")), data["ground_truth"]))
    return cases


def report_to_file(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Prevent leaking raw paths, contents, or ground truth in the aggregate report.
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=".benchmark_", delete=False) as temporary:
        temp = Path(temporary.name)
        temporary.write(content)
    temp.replace(output)
