#!/usr/bin/env python3
"""Privacy-conscious KTP OCR dataset collector.

Only synthetic flat samples and synthetic generator code are downloaded by
default. Other sources need an explicit acknowledgement after permission review.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

ROOT = Path(os.environ.get("KTP_DATA_DIR", "./data")).expanduser()
HF_REPO = "cloverx-id/indonesian-id-card-dummy"
SYNTHETIC_GITHUB = [
    "veldanava/EKTP-Generator",
    "YoshCasaster/e-ktp-generator",
    "khazulys/Fake_ektp",
]
REVIEW_GITHUB = [
    "fathurp01/Fake-EKTP-Generator-With-Local-LLM-GAN-For-Data-Generator",
    "bukalapak/KTPextractor",
    "taqiin/OCR-KTP-ID",
]
ROBOFLOW = [
    ("outer-space", "ktp-scanner-uhtxs"),
    ("ocr-ktp-indoneisa", "deteksi-ktp-indonesia"),
    ("ceel", "ktp-ocr-bjfs7"),
]


def log(message: str) -> None:
    print(message, flush=True)


def load_catalog() -> list[dict]:
    path = Path(__file__).resolve().parent / "sources.json"
    return json.loads(path.read_text(encoding="utf-8"))


def show_sources(_args: argparse.Namespace) -> None:
    for item in load_catalog():
        print(f"[{item['type']}] {item['id']}\n  {item['url']}\n  {item['access']}\n")


def safe_name(value: object, i: int) -> str:
    stem = Path(str(value or f"sample_{i:06d}")).stem
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem)[:70].strip("_-")
    return f"{i:06d}_{stem or 'image'}"


def get_img(row: dict):
    from io import BytesIO
    from PIL import Image
    entry = row.get("image")
    if isinstance(entry, Image.Image):
        return entry
    if isinstance(entry, dict):
        if entry.get("bytes"):
            return Image.open(BytesIO(entry["bytes"]))
        if entry.get("path"):
            return Image.open(entry["path"])
    raise TypeError(f"Unexpected image field type: {type(entry).__name__}")


def hf_one(config: str, out_dir: Path, limit: int) -> dict:
    from datasets import load_dataset
    log(f"[Hugging Face] Streaming {HF_REPO} config={config}, limit={limit or 'ALL'}")
    ds = load_dataset(HF_REPO, name=config, split="train", streaming=True)
    target = out_dir / "huggingface" / config
    images = target / "images"
    images.mkdir(parents=True, exist_ok=True)
    label_path = target / "ground_truth.jsonl"
    count = skipped = errors = 0
    # Images are reused on resume; labels are recreated to avoid duplicates.
    with label_path.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(ds):
            if limit and i >= limit:
                break
            try:
                image = get_img(row)
                ext = "png" if config == "flat" else "jpg"
                name = safe_name(row.get("image_name"), i) + "." + ext
                path = images / name
                if path.exists():
                    skipped += 1
                else:
                    if ext == "jpg":
                        image.convert("RGB").save(path, "JPEG", quality=93)
                    else:
                        image.save(path, "PNG")
                ground_truth = {k: v for k, v in row.items() if k != "image"}
                fh.write(json.dumps({
                    "file": "images/" + name,
                    "source": HF_REPO,
                    "config": config,
                    "ground_truth": ground_truth,
                }, ensure_ascii=False, default=str) + "\n")
                count += 1
                if count % 1000 == 0:
                    log(f"  {config}: {count} records processed")
            except Exception as ex:
                errors += 1
                print(f"ERROR record {i}: {type(ex).__name__}: {ex}", file=sys.stderr)
    summary = {"config": config, "processed": count, "reused_images": skipped, "errors": errors}
    (target / "download_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"[Hugging Face] {config}: {summary}")
    return summary


def hf(args: argparse.Namespace) -> None:
    # The augmented split may contain third-party images in negative samples.
    if args.config in {"augmented", "both"} and not args.ack_authorization:
        raise SystemExit(
            "Denied: augmented samples may include personal data. "
            "Review the dataset card and permissions, then pass --ack-authorization."
        )
    configs = ["flat", "augmented"] if args.config == "both" else [args.config]
    for config in configs:
        hf_one(config, Path(args.out), args.limit)


def github_one(repo: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        log(f"[GitHub] Existing directory; skipping: {target}")
        return
    url = f"https://github.com/{repo}.git"
    log(f"[GitHub] Cloning {url}")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--", url, str(target)],
        check=True,
        timeout=3600,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def github(args: argparse.Namespace) -> None:
    if args.group == "review" and not args.ack_authorization:
        raise SystemExit(
            "Denied: GitHub review group may contain real personal KTP data. "
            "Use --ack-authorization only after verifying consent and lawful use."
        )
    repos = SYNTHETIC_GITHUB if args.group == "synthetic" else REVIEW_GITHUB
    out = Path(args.out) / "github" / args.group
    if args.group == "review":
        out.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(out, 0o700)
    for repo in repos:
        github_one(repo, out / repo.replace("/", "__"))


def roboflow(args: argparse.Namespace) -> None:
    if not args.ack_authorization:
        raise SystemExit(
            "Denied: Roboflow projects may contain genuine KTP personal data. "
            "Only use --ack-authorization after confirming permission from owners."
        )
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set ROBOFLOW_API_KEY locally first (never commit it).")
    from roboflow import Roboflow
    rf = Roboflow(api_key=key)
    root = Path(args.out) / "roboflow"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    for workspace, slug in ROBOFLOW:
        log(f"[Roboflow] Inspecting {workspace}/{slug}")
        project = rf.workspace(workspace).project(slug)
        available = project.get_version_information()
        versions = []
        for item in available:
            try:
                versions.append(int(str(item["id"]).rstrip("/").split("/")[-1]))
            except (ValueError, KeyError, TypeError):
                pass
        if not versions:
            log(f"  No downloadable version for {workspace}/{slug}; check in browser")
            continue
        version = max(versions)
        target = root / (workspace + "__" + slug + "__v" + str(version))
        if target.exists() and any(target.iterdir()):
            log(f"  Already downloaded: {target}")
            continue
        log(f"  Downloading version {version} as YOLOv8")
        project.version(version).download("yolov8", location=str(target))
        log(f"  Saved: {target}")


def all_sources(args: argparse.Namespace) -> None:
    """Synthetic flat by default; restricted sources require acknowledgement."""
    hf(args)
    github(argparse.Namespace(out=args.out, group="synthetic", ack_authorization=False))
    if args.ack_authorization:
        github(argparse.Namespace(out=args.out, group="review", ack_authorization=True))
        if os.environ.get("ROBOFLOW_API_KEY"):
            roboflow(argparse.Namespace(out=args.out, ack_authorization=True))
        else:
            log("Roboflow skipped: ROBOFLOW_API_KEY is not set.")
    log("JEECS 78-image research dataset is not publicly downloadable; request author permission.")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KTP OCR dataset collector (privacy-aware)")
    parser.add_argument("--out", default=str(ROOT), help="Output directory")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources", help="List all identified source URLs")
    h = sub.add_parser("hf", help="Fetch Hugging Face images + ground truth")
    h.add_argument("--config", choices=["flat", "augmented", "both"], default="flat")
    h.add_argument("--limit", type=int, default=100, help="Max per config; 0=all")
    h.add_argument("--ack-authorization", action="store_true")
    g = sub.add_parser("github", help="Clone generator source or restricted review examples")
    g.add_argument("--group", choices=["synthetic", "review"], default="synthetic")
    g.add_argument("--ack-authorization", action="store_true")
    r = sub.add_parser("roboflow", help="Fetch three Roboflow datasets if authorized")
    r.add_argument("--ack-authorization", action="store_true")
    a = sub.add_parser("all", help="Synthetic flat by default, restricted sources only with --ack")
    a.add_argument("--config", choices=["flat", "augmented", "both"], default="flat")
    a.add_argument("--limit", type=int, default=100, help="Max per config; 0=all")
    a.add_argument("--ack-authorization", action="store_true")
    return parser


def main() -> None:
    args = make_parser().parse_args()
    if args.cmd in {"hf", "all"} and args.limit < 0:
        raise SystemExit("--limit must be 0 or greater")
    try:
        {
            "sources": show_sources,
            "hf": hf,
            "github": github,
            "roboflow": roboflow,
            "all": all_sources,
        }[args.cmd](args)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as ex:
        log(f"FAILED: {type(ex).__name__}: {ex}")
        if os.environ.get("DEBUG") == "1":
            traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
