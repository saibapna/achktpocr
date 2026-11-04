"""Explicitly fetch and integrity-check taqiin's ktp.traineddata for research.

This DOES NOT grant usage/redistribution rights. Upstream package.json says MIT,
but LICENSE contains the Artistic License 2.0. Check rights and model provenance.
This file does not change the default OCR engine or production image.
"""

import argparse
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

COMMIT = "56026700d951845897eed5f48339d19c00604147"
GIT_BLOB_SHA1 = "8df4926187c806b35607519eee0c5a6e970a630a"
URL = f"https://raw.githubusercontent.com/taqiin/OCR-KTP-ID/{COMMIT}/ktp.traineddata"
MAX_BYTES = 100 * 1024 * 1024


def download(output: Path) -> dict[str, str | int]:
    """Stream binary, bound size and verify the upstream Git blob identity."""
    request = urllib.request.Request(URL, headers={"User-Agent": "achktpocr-benchmark/0.1"})
    with urllib.request.urlopen(request, timeout=40) as response:
        with tempfile.TemporaryDirectory(prefix="ktp-traineddata-") as directory:
            temporary = Path(directory) / "ktp.traineddata"
            hasher = hashlib.sha256()
            length = 0
            with temporary.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    length += len(chunk)
                    if length > MAX_BYTES:
                        raise ValueError("Model file exceeds configured limit")
                    handle.write(chunk)
                    hasher.update(chunk)
            # Git blob SHA1 includes the full file size in its object header.
            git_sha = hashlib.sha1(b"blob " + str(length).encode() + b"\0")
            with temporary.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    git_sha.update(chunk)
            if git_sha.hexdigest() != GIT_BLOB_SHA1:
                raise ValueError("Model SHA mismatch: refusing potentially changed artifact")
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(output)
            return {"git_blob_sha1": git_sha.hexdigest(), "sha256": hasher.hexdigest(),
                    "bytes": length}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("models/benchmark/ktp.traineddata"))
    parser.add_argument("--acknowledge-license-review", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_license_review:
        print(
            "Review model rights: upstream LICENSE=Artistic-2.0, "
            "package.json=MIT; provenance unknown. "
            "Run again with --acknowledge-license-review after checking "
            "license and usage rights.",
            file=sys.stderr,
        )
        return 2
    try:
        info = download(args.output)
        print(f"Integrity-verified model: Git blob {info['git_blob_sha1']}; "
              f"SHA256 {info['sha256']}; {info['bytes']} bytes. Not committed to Git.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Download failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
