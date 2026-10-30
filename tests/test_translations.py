"""Every language has en.json's keys, no other, and the same placeholders."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / "boreale" / "translations"
EN = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))


def _flat(doc: Any, prefix: str = "") -> dict[str, str]:
    if not isinstance(doc, dict):
        return {prefix: str(doc)}
    out: dict[str, str] = {}
    for key, value in doc.items():
        out |= _flat(value, f"{prefix}.{key}" if prefix else key)
    return out


@pytest.mark.parametrize("path", sorted(p for p in TRANSLATIONS.glob("*.json") if p.name != "en.json"), ids=str)
def test_language(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert text == json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    en, other = _flat(EN), _flat(doc)
    assert other.keys() == en.keys()
    for key, value in en.items():
        assert sorted(re.findall(r"\{\w+\}", other[key])) == sorted(re.findall(r"\{\w+\}", value)), key
