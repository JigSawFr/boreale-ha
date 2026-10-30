"""boreale.zip: what HACS installs from a release (hacs.json's zip_release).

The files of custom_components/boreale/ at the zip's root (manifest.json
first-level, as HACS extracts it into custom_components/boreale/), Python's
caches left out, in a fixed order with fixed dates and modes, so the same
commit gives the same bytes. The date is SOURCE_DATE_EPOCH (POSIX seconds),
else the last commit's time.

    python scripts/package.py [--out dist/boreale.zip] [--version-must-be 0.1.0]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "custom_components" / "boreale"
# The oldest date a zip entry can carry.
ZIP_EPOCH = 315532800  # 1980-01-01T00:00:00Z


def source_date_epoch() -> int:
    """SOURCE_DATE_EPOCH, else the last commit's time, else now."""
    if (value := os.environ.get("SOURCE_DATE_EPOCH", "").strip()).isdigit():
        return int(value)
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return int(out)
    except OSError, subprocess.CalledProcessError, ValueError:
        return int(time.time())


def files(source: Path) -> list[Path]:
    """Every file of the integration, by path, without Python's caches."""
    return sorted(
        p
        for p in source.rglob("*")
        if p.is_file() and "__pycache__" not in p.relative_to(source).parts and p.suffix not in (".pyc", ".pyo")
    )


def build(out: Path, source: Path = SOURCE, epoch: int | None = None) -> str:
    """Writes the zip; returns its SHA-256."""
    stamp = time.gmtime(max(ZIP_EPOCH, source_date_epoch() if epoch is None else epoch))[:6]
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        for path in files(source):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=stamp)
            info.create_system = 3  # Unix, whatever builds it
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes(), compresslevel=9)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "boreale.zip")
    parser.add_argument("--version-must-be", help="fail unless manifest.json says this version (a release tag)")
    args = parser.parse_args(argv)
    version = json.loads((SOURCE / "manifest.json").read_text())["version"]
    if args.version_must_be is not None and args.version_must_be.removeprefix("v") != version:
        print(f"manifest.json says {version}, the release is {args.version_must_be}", file=sys.stderr)
        return 1
    digest = build(args.out)
    print(f"{args.out}: version {version}, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
