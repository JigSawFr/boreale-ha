"""A pre-release of the next version, from release-please's release PR.

The release PR (branch release-please--branches--main) carries the next
version (.release-please-manifest.json) and its changelog (CHANGELOG.md's
first section). Each update of it is published as a GitHub pre-release,
vX.Y.Z-dev.N, which HACS offers to whoever turns the repository's
Pre-release switch on; merging the PR publishes vX.Y.Z as before.

    python scripts/prerelease.py version < tags.txt    # the next pre-release's version
    python scripts/prerelease.py stamp 0.9.0-dev.3      # manifest.json says it
    python scripts/prerelease.py notes 0.9.0-dev.3 --out notes.md
    python scripts/prerelease.py stale 0.9.0 --keep 5 < tags.txt   # tags to delete
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components" / "boreale" / "manifest.json"
PLEASE = ROOT / ".release-please-manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def next_version() -> str:
    """The version release-please prepares (its release PR's manifest)."""
    return str(json.loads(PLEASE.read_text(encoding="utf-8"))["."])


def dev_numbers(tags: list[str], version: str) -> list[int]:
    """N of each vVERSION-dev.N tag, in order."""
    pattern = re.compile(rf"^v{re.escape(version)}-dev\.(\d+)$")
    return sorted(int(m.group(1)) for t in tags if (m := pattern.match(t.strip())))


def prerelease_version(tags: list[str], version: str) -> str:
    """The next pre-release: one more than the last one published (deleted ones are not reused)."""
    numbers = dev_numbers(tags, version)
    return f"{version}-dev.{(numbers[-1] if numbers else 0) + 1}"


def stale(tags: list[str], version: str, keep: int) -> list[str]:
    """The pre-releases of VERSION beyond the KEEP newest."""
    numbers = dev_numbers(tags, version)
    return [f"v{version}-dev.{n}" for n in numbers[: max(0, len(numbers) - keep)]]


def stamp(version: str, manifest: Path = MANIFEST) -> None:
    """manifest.json says VERSION (the zip and Home Assistant show it)."""
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["version"] = version
    manifest.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def notes(version: str, changelog: Path = CHANGELOG) -> str:
    """The pre-release's notes: the release PR's changelog section, under a heading saying what it is."""
    text = changelog.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)
    body = sections[1].split("\n", 1)[1].strip() if len(sections) > 1 else ""
    base = version.split("-", 1)[0]
    head = (
        f"Pre-release of {base}, built from the release pull request: what {base} will hold so far. "
        "HACS offers it with the repository's *Pre-release* switch on.\n\n"
    )
    return head + (body or "_No change listed yet._") + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="the next pre-release's version (published tags on stdin)")
    p = sub.add_parser("stamp", help="manifest.json says this version")
    p.add_argument("version")
    p = sub.add_parser("notes", help="the pre-release's notes")
    p.add_argument("version")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("stale", help="the pre-releases of a version to delete (published tags on stdin)")
    p.add_argument("version")
    p.add_argument("--keep", type=int, default=5)
    args = parser.parse_args(argv)
    if args.command == "version":
        print(prerelease_version(sys.stdin.read().split(), next_version()))
    elif args.command == "stamp":
        stamp(args.version, MANIFEST)
    elif args.command == "notes":
        args.out.write_text(notes(args.version), encoding="utf-8")
    else:
        print("\n".join(stale(sys.stdin.read().split(), args.version, args.keep)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
