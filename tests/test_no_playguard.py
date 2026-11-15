"""A console that runs without PlayGuard's module (an agent installed by
itself, or PlayGuard removed): the entities that need PlayGuard's documents
are not there, the console's own ones are, and they come back with PlayGuard."""

from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.boreale.const import (
    CONF_CONSOLE_ID,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_TREE,
    CONF_UNPUBLISHED,
    DOMAIN,
    NO_PLAYGUARD,
)

from .conftest import CONSOLE_ID, fixture

TREE = f"boreale/{CONSOLE_ID}"
# Of PlayGuard's documents, and of the console's own.
PLAYGUARD = (
    (Platform.LOCK, "parental_controls"),
    (Platform.SENSOR, "now_playing"),
    (Platform.UPDATE, "playguard_update"),
)
CONSOLE = ((Platform.SENSOR, "battery"), (Platform.SENSOR, "last_seen"), (Platform.SENSOR, "homebrew_notices"))


@pytest.fixture
def tree_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "boreale", CONF_TREE: 2},
        options={CONF_TAKE_OVER: True},
        minor_version=3,
    )


def _capabilities(*modules: str) -> str:
    known = {"playguard": {"schema": 1, "version": "1.4.0"}, "playshelf": {"version": "1.2.0"}}
    return json.dumps({"schema": 1, "platform": "switch", "modules": {m: known[m] for m in modules}})


def _id(hass: HomeAssistant, platform: Platform, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")


async def _start(hass: HomeAssistant, entry: MockConfigEntry, state: dict) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, f"{TREE}/playguard/state", json.dumps(state), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/system", json.dumps(fixture("system.json")), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/availability", "online", retain=True)
    await hass.async_block_till_done()


async def test_playguard_leaves_and_comes_back(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard"), retain=True)
    await hass.async_block_till_done()
    for platform, key in PLAYGUARD + CONSOLE:
        assert _id(hass, platform, key), key
    assert CONF_UNPUBLISHED not in tree_entry.data

    # Announced without it: its entities go, the console's stay.
    async_fire_mqtt_message(
        hass, f"{TREE}/capabilities", _capabilities("playshelf")
    )  # live: a retained one counts once
    await hass.async_block_till_done()
    for platform, key in PLAYGUARD:
        assert _id(hass, platform, key) is None, key
    for platform, key in CONSOLE:
        assert _id(hass, platform, key), key
    assert NO_PLAYGUARD in tree_entry.data[CONF_UNPUBLISHED]

    # The same again: nothing more (an entity added by hand meanwhile goes too).
    er.async_get(hass).async_get_or_create("lock", DOMAIN, f"{CONSOLE_ID}_parental_controls", config_entry=tree_entry)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playshelf"))
        await hass.async_block_till_done()
    reload.assert_not_called()
    assert _id(hass, Platform.LOCK, "parental_controls") is None

    # Back: the entry reloads and its entities come back.
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"))
    await hass.async_block_till_done()
    assert tree_entry.state is ConfigEntryState.LOADED
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    for platform, key in PLAYGUARD:
        assert _id(hass, platform, key), key
    assert NO_PLAYGUARD not in tree_entry.data.get(CONF_UNPUBLISHED, [])


async def test_accounts_go_with_playguard(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor", DOMAIN, f"{CONSOLE_ID}_account_0123456789abcdef_today", config_entry=tree_entry
    )
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playshelf"))
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_account_0123456789abcdef_today") is None


async def test_unknown_modules_remove_nothing(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    """No `modules` (a document we do not know the shape of): PlayGuard stays."""
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", json.dumps({"schema": 1, "platform": "switch"}), retain=True)
    await hass.async_block_till_done()
    for platform, key in PLAYGUARD:
        assert _id(hass, platform, key), key
    assert CONF_UNPUBLISHED not in tree_entry.data


async def test_not_created_without_playguard(hass: HomeAssistant, mqtt_mock, tree_entry) -> None:
    """The next start does not create what the last one found it did not need."""
    tree_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(tree_entry, data={**tree_entry.data, CONF_UNPUBLISHED: [NO_PLAYGUARD]})
    assert await hass.config_entries.async_setup(tree_entry.entry_id)
    await hass.async_block_till_done()
    for platform, key in PLAYGUARD:
        assert _id(hass, platform, key) is None, key
    for platform, key in CONSOLE:
        assert _id(hass, platform, key), key


async def test_the_agent_says_how_it_is_doing(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    """The agent's own diagnostics, from the system document's `agent` block."""
    registry = er.async_get(hass)
    for key in ("agent_memory", "agent_uptime"):
        registry.async_get_or_create("sensor", DOMAIN, f"{CONSOLE_ID}_{key}", disabled_by=None)
    tree_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(tree_entry.entry_id)
    await hass.async_block_till_done()
    system = {
        **fixture("system.json"),
        "agent": {
            "uptime_s": 7200,
            "heap_used": 409600,
            "heap_total": 1572864,
            "protocols": {"relay": 1, "ipc": 3},
            "module": False,
        },
    }
    async_fire_mqtt_message(hass, f"{TREE}/system", json.dumps(system), retain=True)
    await hass.async_block_till_done()
    memory = hass.states.get(_id(hass, Platform.SENSOR, "agent_memory") or "")
    uptime = hass.states.get(_id(hass, Platform.SENSOR, "agent_uptime") or "")
    assert (
        memory is not None and float(memory.state) == 409600.0
    )  # bytes (the suggested unit is the registry's, for a new entity)
    assert uptime is not None and float(uptime.state) == 7200.0  # seconds
