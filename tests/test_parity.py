"""The entity table against PlayGuard's (tests/fixtures/entities.json).

PlayGuard's host tests export its table (source/sync/sync_entities.c) as
build/host-tests/sync/entities.json; copy it here when it changes. This test
fails when the two disagree, so the integration's entities stay the native
discovery's, under the same object ids.
"""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.playguard.entities import BY_KEY, ENTITIES

from .conftest import fixture

STRINGS = Path(__file__).parent.parent / "custom_components" / "playguard" / "strings.json"


def _template(definition) -> str | None:
    if definition.path is None:
        return "{{ None }}" if definition.platform in ("select",) else None
    expr = "value_json." + ".".join(definition.path)
    if definition.fallback:
        expr += " or value_json." + ".".join(definition.fallback)
    return "{{ " + expr + " }}"


def test_same_entities_as_playguard() -> None:
    table = fixture("entities.json")
    assert table["schema"] == 1
    ours = {e.key for e in ENTITIES if not e.extra}
    theirs = {e["id"] for e in table["entities"]}
    assert ours == theirs, f"only here: {sorted(ours - theirs)}, only in PlayGuard: {sorted(theirs - ours)}"
    names = json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]
    for e in table["entities"]:
        d = BY_KEY[e["id"]]
        extra = e["extra"]
        assert str(d.platform) == e["platform"], e["id"]
        assert d.write == e["write"], e["id"]
        assert _template(d) == e["value_template"], e["id"]
        assert names[e["platform"]][e["id"]]["name"] == e["name"], e["id"]
        assert d.icon == extra.get("ic"), e["id"]
        assert d.category == extra.get("ent_cat"), e["id"]
        assert d.enabled == extra.get("en", True), e["id"]
        assert d.unit == extra.get("unit_of_meas"), e["id"]
        assert d.device_class == extra.get("dev_cla"), e["id"]
        assert d.state_class == extra.get("stat_cla"), e["id"]
        if "ops" in extra:
            assert list(d.options or ()) == extra["ops"], e["id"]
        for ours_attr, key in (("minimum", "min"), ("maximum", "max"), ("step", "step")):
            assert getattr(d, ours_attr) == extra.get(key), (e["id"], key)


def test_every_entity_is_named() -> None:
    names = json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]
    for d in ENTITIES:
        assert d.key in names[str(d.platform)], d.key
