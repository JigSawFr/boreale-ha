"""scripts/prerelease.py: the pre-releases built from release-please's release PR."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("prerelease", ROOT / "scripts" / "prerelease.py")
prerelease = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prerelease)

TAGS = ["v0.8.0", "v0.9.0-dev.1", "v0.9.0-dev.3", "v0.9.0-dev.10", "v0.8.0-dev.7", "v0.9.0-dev.x", "v0.9.0"]


def test_version() -> None:
    assert prerelease.prerelease_version(TAGS, "0.9.0") == "0.9.0-dev.11"  # after the last, not the count
    assert prerelease.prerelease_version([], "0.9.0") == "0.9.0-dev.1"
    assert prerelease.prerelease_version(TAGS, "0.10.0") == "0.10.0-dev.1"
    assert prerelease.next_version() == json.loads((ROOT / ".release-please-manifest.json").read_text())["."]


def test_stale() -> None:
    assert prerelease.stale(TAGS, "0.9.0", keep=2) == ["v0.9.0-dev.1"]
    assert prerelease.stale(TAGS, "0.9.0", keep=5) == []
    assert prerelease.stale(TAGS, "0.9.0", keep=0) == ["v0.9.0-dev.1", "v0.9.0-dev.3", "v0.9.0-dev.10"]


def test_stamp(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text((ROOT / "custom_components" / "playguard" / "manifest.json").read_text())
    prerelease.stamp("0.9.0-dev.2", manifest)
    text = manifest.read_text()
    assert json.loads(text)["version"] == "0.9.0-dev.2"
    assert text == json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"


def test_notes(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [0.9.0](https://x/compare/v0.8.0...v0.9.0) (2026-10-28)\n\n\n### 🚀 Features\n\n"
        "* **activity:** what the console is doing\n\n## [0.8.0](https://x) (2026-10-26)\n\n* older\n"
    )
    text = prerelease.notes("0.9.0-dev.4", changelog)
    assert text.startswith("Pre-release of 0.9.0, built from the release pull request")
    assert "* **activity:** what the console is doing" in text and "older" not in text
    changelog.write_text("# Changelog\n")
    assert "_No change listed yet._" in prerelease.notes("0.9.0-dev.1", changelog)


def test_main(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("\n".join(TAGS)))
    assert prerelease.main(["stale", "0.9.0", "--keep", "1"]) == 0
    assert capsys.readouterr().out.split() == ["v0.9.0-dev.1", "v0.9.0-dev.3"]
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))
    assert prerelease.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"{prerelease.next_version()}-dev.1"
    out = tmp_path / "notes.md"
    assert prerelease.main(["notes", "0.9.0-dev.1", "--out", str(out)]) == 0 and out.read_text()
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": "0.8.0"}')
    monkeypatch.setattr(prerelease, "MANIFEST", manifest)
    assert prerelease.main(["stamp", "0.9.0-dev.1"]) == 0
    assert json.loads(manifest.read_text())["version"] == "0.9.0-dev.1"
