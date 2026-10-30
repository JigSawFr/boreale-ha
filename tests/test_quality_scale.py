"""quality_scale.yaml, checked as hassfest checks a core integration's
(hassfest skips custom integrations). The rules are those of Home Assistant
2026.10's script/hassfest/quality_scale.py."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.util.yaml import load_yaml_dict

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "boreale"

TIERS: dict[str, tuple[str, ...]] = {
    "bronze": (
        "action-setup",
        "appropriate-polling",
        "brands",
        "common-modules",
        "config-flow",
        "config-flow-test-coverage",
        "dependency-transparency",
        "docs-actions",
        "docs-conditions",
        "docs-high-level-description",
        "docs-installation-instructions",
        "docs-removal-instructions",
        "docs-triggers",
        "entity-event-setup",
        "entity-unique-id",
        "has-entity-name",
        "runtime-data",
        "test-before-configure",
        "test-before-setup",
        "unique-config-entry",
    ),
    "silver": (
        "action-exceptions",
        "config-entry-unloading",
        "docs-configuration-parameters",
        "docs-installation-parameters",
        "entity-unavailable",
        "integration-owner",
        "log-when-unavailable",
        "parallel-updates",
        "reauthentication-flow",
        "test-coverage",
    ),
    "gold": (
        "devices",
        "diagnostics",
        "discovery",
        "discovery-update-info",
        "docs-data-update",
        "docs-examples",
        "docs-known-limitations",
        "docs-supported-devices",
        "docs-supported-functions",
        "docs-troubleshooting",
        "docs-use-cases",
        "dynamic-devices",
        "entity-category",
        "entity-device-class",
        "entity-disabled-by-default",
        "entity-translations",
        "exception-translations",
        "icon-translations",
        "reconfiguration-flow",
        "repair-issues",
        "stale-devices",
    ),
    "platinum": ("async-dependency", "inject-websession", "strict-typing"),
}


def _statuses() -> dict[str, tuple[str, str | None]]:
    """Each rule's (status, comment), the file's format checked on the way."""
    rules = load_yaml_dict(str(INTEGRATION / "quality_scale.yaml"))["rules"]
    out: dict[str, tuple[str, str | None]] = {}
    for name, value in rules.items():
        if isinstance(value, str):
            assert value in ("done", "todo"), (name, value)
            out[name] = (value, None)
            continue
        assert isinstance(value, dict) and set(value) == {"status", "comment"}, name
        assert value["status"] in ("done", "todo", "exempt"), name
        assert isinstance(value["comment"], str) and value["comment"].strip(), name
        out[name] = (value["status"], value["comment"])
    return out


def test_every_rule_is_listed() -> None:
    known = {rule for rules in TIERS.values() for rule in rules}
    assert set(_statuses()) == known


def test_exempt_and_todo_say_why() -> None:
    for name, (status, comment) in _statuses().items():
        if status in ("exempt", "todo"):
            assert comment, name


def test_the_declared_tier_is_met() -> None:
    declared = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))["quality_scale"]
    assert declared in TIERS
    statuses = _statuses()
    for tier, rules in TIERS.items():
        missing = [rule for rule in rules if statuses[rule][0] not in ("done", "exempt")]
        assert not missing, f"{tier} needs: {missing}"
        if tier == declared:
            break
