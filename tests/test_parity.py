"""The entity table against PlayGuard's (tests/fixtures/entities.json).

PlayGuard's host tests export its table (source/sync/sync_entities.c) as
build/host-tests/sync/entities.json; copy it here when it changes. This test
fails when the two disagree, so the integration's entities stay the native
discovery's, under the same object ids.
"""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.util.yaml import load_yaml

from custom_components.playguard.const import RETIRED
from custom_components.playguard.entities import ACCOUNT_ENTITIES, BY_KEY, ENTITIES, EntityDef

from .conftest import fixture

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "playguard"
STRINGS = INTEGRATION / "translations" / "en.json"
ICONS = INTEGRATION / "icons.json"


def _template(definition: EntityDef) -> str | None:
    if definition.path is None:
        return None
    expr = "value_json." + ".".join(definition.path)
    if definition.platform == "lock":  # locked while set up and not unlocked for now
        return "{{ 'LOCKED' if value_json.controls.enabled and not " + expr + " else 'UNLOCKED' }}"
    if definition.fallback:
        expr += " or value_json." + ".".join(definition.fallback)
    for value, option in definition.renamed:
        expr = f"'{option}' if {expr} == '{value}' else {expr}"
    if definition.device_class == "timestamp":  # POSIX seconds, null unknown
        return "{{ as_datetime(" + expr + ") if " + expr + " else None }}"
    return "{{ " + expr + " }}"


def _command_template(definition: EntityDef) -> str | None:
    """The order of an option shown under another name is still the value's."""
    if not definition.renamed:
        return None
    expr = "value"
    for value, option in definition.renamed:
        expr = f"'{value}' if value == '{option}' else {expr}"
    return "{{ " + expr + " }}"


def test_same_entities_as_playguard() -> None:
    table = fixture("entities.json")
    assert table["schema"] == 1
    ours = {e.key for e in ENTITIES if not e.extra}
    theirs = {e["id"] for e in table["entities"]}
    assert ours == theirs, f"only here: {sorted(ours - theirs)}, only in PlayGuard: {sorted(theirs - ours)}"
    names = json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]
    icons = json.loads(ICONS.read_text(encoding="utf-8"))["entity"]
    for e in table["entities"]:
        d = BY_KEY[e["id"]]
        extra = e["extra"]
        assert str(d.platform) == e["platform"], e["id"]
        assert d.write == e["write"], e["id"]
        assert d.topic == e["topic"], e["id"]
        assert d.publish == e["publish"], e["id"]
        assert _template(d) == e["value_template"], e["id"]
        assert _command_template(d) == extra.get("cmd_tpl"), e["id"]
        assert names[e["platform"]][e["id"]]["name"] == e["name"], e["id"]
        assert icons.get(e["platform"], {}).get(e["id"], {}).get("default") == extra.get("ic"), e["id"]
        assert d.category == extra.get("ent_cat"), e["id"]
        assert d.enabled == extra.get("en", True), e["id"]
        assert d.unit == extra.get("unit_of_meas"), e["id"]
        assert d.device_class == extra.get("dev_cla"), e["id"]
        assert d.state_class == extra.get("stat_cla"), e["id"]
        if "ops" in extra:
            assert list(d.options or ()) == extra["ops"], e["id"]
        if "sug_dsp_prc" in extra:
            assert d.precision == extra["sug_dsp_prc"], e["id"]
        for ours_attr, key in (("minimum", "min"), ("maximum", "max"), ("step", "step")):
            assert getattr(d, ours_attr) == extra.get(key), (e["id"], key)


def test_retired_as_playguard() -> None:
    """What the migration removes is what PlayGuard's discovery removes."""
    retired = {(r["platform"], r["id"]) for r in fixture("entities.json")["retired"]}
    assert set(RETIRED) == retired
    assert not {key for _platform, key in RETIRED} & set(BY_KEY)


def test_every_entity_is_named() -> None:
    names = json.loads(STRINGS.read_text(encoding="utf-8"))["entity"]
    for d in ENTITIES:
        assert d.key in names[str(d.platform)], d.key


def test_icons_are_for_entities_and_actions() -> None:
    icons = json.loads(ICONS.read_text(encoding="utf-8"))
    for platform, keys in icons["entity"].items():
        for key in keys:
            d = BY_KEY.get(key) or next((a for a in ACCOUNT_ENTITIES if a.key == key), None)
            assert d and str(d.platform) == platform, key
    assert set(icons["services"]) == set(load_yaml(INTEGRATION / "services.yaml"))
