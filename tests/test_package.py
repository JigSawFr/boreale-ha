"""scripts/package.py: the zip HACS installs from a release."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "custom_components" / "playguard"

_spec = importlib.util.spec_from_file_location("package", ROOT / "scripts" / "package.py")
package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(package)


def test_contents(tmp_path: Path) -> None:
    """The integration's files at the root, as HACS extracts them, and nothing else."""
    out = tmp_path / "playguard.zip"
    package.build(out, epoch=1_760_000_000)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert names == sorted(names)
        assert {
            "manifest.json",
            "__init__.py",
            "icons.json",
            "quality_scale.yaml",
            "translations/en.json",
            "translations/fr.json",
            "brand/icon.png",
        } <= set(names)
        assert not [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]
        assert set(names) == {p.relative_to(SOURCE).as_posix() for p in package.files(SOURCE)}
        assert json.loads(zf.read("manifest.json")) == json.loads((SOURCE / "manifest.json").read_text())
        info = zf.getinfo("manifest.json")
        assert info.date_time == (2025, 10, 9, 8, 53, 20)
        assert info.external_attr >> 16 == 0o100644


def test_same_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same sources and date give the same zip; SOURCE_DATE_EPOCH sets the date."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1760000000")
    first = package.build(tmp_path / "a.zip")
    second = package.build(tmp_path / "b.zip")
    assert first == second
    assert (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()
    # Before 1980, the oldest date a zip can hold.
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    package.build(tmp_path / "old.zip")
    with zipfile.ZipFile(tmp_path / "old.zip") as zf:
        assert zf.getinfo("manifest.json").date_time == (1980, 1, 1, 0, 0, 0)


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A release's tag must be manifest.json's version."""
    version = json.loads((SOURCE / "manifest.json").read_text())["version"]
    out = tmp_path / "dist" / "playguard.zip"
    assert package.main(["--out", str(out), "--version-must-be", f"v{version}"]) == 0
    assert out.is_file() and f"version {version}" in capsys.readouterr().out
    assert package.main(["--out", str(out), "--version-must-be", "v99.0.0"]) == 1
    assert "the release is v99.0.0" in capsys.readouterr().err
