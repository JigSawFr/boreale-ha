"""PlayShelf's module: its entities once the console announces it, its state
and the pause button, what happens when it leaves and comes back."""

from __future__ import annotations

import json

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.boreale.const import (
    CONF_CONSOLE_ID,
    CONF_KEEP_VALUES,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_TREE,
    DOMAIN,
)

from .conftest import CONSOLE_ID

TREE = f"boreale/{CONSOLE_ID}"
SHELF = f"{TREE}/playshelf"
KEYS = {
    Platform.SENSOR: ("shelf_pending", "shelf_progress", "shelf_last_installed", "shelf_free"),
    Platform.BINARY_SENSOR: ("shelf_downloading", "shelf_failed"),
    Platform.BUTTON: ("shelf_pause",),
}
STATE = {
    "schema": 1,
    "version": "1.2.0",
    "downloads": {"pending": 3, "running": 1, "paused": 0, "failed": 0, "progress": 42},
    "last_installed": "Pixel Cats",
    "storage": {"free": 5368709120},
}


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
    async_fire_mqtt_message(hass, f"{TREE}/availability", "online", retain=True)
    await hass.async_block_till_done()


async def test_nothing_until_announced(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    subscribed = {c.args[0] for c in mqtt_mock.async_subscribe.call_args_list}
    assert f"{SHELF}/state" in subscribed
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard"), retain=True)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    await hass.async_block_till_done()
    assert not tree_entry.runtime_data.has_playshelf
    assert all(_id(hass, p, k) is None for p, keys in KEYS.items() for k in keys)


async def test_entities_and_values(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    console = tree_entry.runtime_data
    assert console.has_playshelf and console.playshelf["version"] == "1.2.0"

    def value(platform: Platform, key: str) -> str:
        entity_id = _id(hass, platform, key)
        assert entity_id, key
        return hass.states.get(entity_id).state

    assert value(Platform.SENSOR, "shelf_pending") == "3"
    assert value(Platform.SENSOR, "shelf_progress") == "42"
    assert value(Platform.SENSOR, "shelf_last_installed") == "Pixel Cats"
    assert float(value(Platform.SENSOR, "shelf_free")) == pytest.approx(5.0)  # shown in GiB
    assert value(Platform.BINARY_SENSOR, "shelf_downloading") == STATE_ON
    assert value(Platform.BINARY_SENSOR, "shelf_failed") == "off"

    # Nothing runs and nothing was installed: no progress, no last game; a failure turns the problem on.
    quiet = {**STATE, "downloads": {"pending": 0, "running": 0, "paused": 0, "failed": 2, "progress": None}}
    quiet["last_installed"] = None
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(quiet))
    await hass.async_block_till_done()
    assert value(Platform.SENSOR, "shelf_progress") == STATE_UNKNOWN
    assert value(Platform.SENSOR, "shelf_last_installed") == STATE_UNKNOWN
    assert value(Platform.BINARY_SENSOR, "shelf_downloading") == "off"
    assert value(Platform.BINARY_SENSOR, "shelf_failed") == STATE_ON

    # A key it does not know is skipped; a document of a newer schema is not read (the last one stays).
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps({**STATE, "something_new": [1]}))
    await hass.async_block_till_done()
    assert value(Platform.SENSOR, "shelf_pending") == "3"
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps({**quiet, "schema": 99}))
    await hass.async_block_till_done()
    assert value(Platform.SENSOR, "shelf_pending") == "3"
    # Nothing like a number where one is expected: unknown, not an error.
    async_fire_mqtt_message(
        hass, f"{SHELF}/state", json.dumps({**STATE, "downloads": {"pending": "x", "failed": True}})
    )
    await hass.async_block_till_done()
    assert value(Platform.SENSOR, "shelf_pending") == STATE_UNKNOWN
    assert value(Platform.BINARY_SENSOR, "shelf_failed") == STATE_UNKNOWN


async def test_pause_button(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        "button", SERVICE_PRESS, {ATTR_ENTITY_ID: _id(hass, Platform.BUTTON, "shelf_pause")}, blocking=True
    )
    # Not retained: pressed while PlayShelf is closed it does nothing, it does not pause a later session.
    assert [c.args for c in mqtt_mock.async_publish.call_args_list] == [
        (f"{SHELF}/pause_downloads/set", "PRESS", 1, False)
    ]


async def test_leaves_and_comes_back(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    pending = _id(hass, Platform.SENSOR, "shelf_pending")
    assert hass.states.get(pending).state == "3"

    # PlayShelf closed: no longer announced, its entities stay, unavailable.
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard"))
    await hass.async_block_till_done()
    assert hass.states.get(pending).state == STATE_UNAVAILABLE
    assert hass.states.get(_id(hass, Platform.BUTTON, "shelf_pause")).state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"))
    await hass.async_block_till_done()
    assert hass.states.get(pending).state == "3"

    # The console out of reach: the entry keeps the last values (its option, on by default).
    async_fire_mqtt_message(hass, f"{TREE}/availability", "offline")
    await hass.async_block_till_done()
    assert hass.states.get(pending).state == "3"


async def test_unavailable_when_the_console_is_out_of_reach(hass: HomeAssistant, mqtt_mock, state: dict) -> None:
    """With the entry set not to keep the last values, the console off the broker makes them unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "boreale", CONF_TREE: 2},
        options={CONF_TAKE_OVER: True, CONF_KEEP_VALUES: False},
        minor_version=3,
    )
    await _start(hass, entry, state)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    pending = _id(hass, Platform.SENSOR, "shelf_pending")
    assert hass.states.get(pending).state == "3"
    async_fire_mqtt_message(hass, f"{TREE}/availability", "offline")
    await hass.async_block_till_done()
    assert hass.states.get(pending).state == STATE_UNAVAILABLE


async def test_known_entities_stay_after_a_restart(hass: HomeAssistant, mqtt_mock, tree_entry, state: dict) -> None:
    """The entities the registry knows come back at set-up, unavailable until the
    console announces the module again: not lost, not shown as removed."""
    await _start(hass, tree_entry, state)
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(tree_entry.entry_id)
    await hass.async_block_till_done()
    pending = _id(hass, Platform.SENSOR, "shelf_pending")
    assert hass.states.get(pending).state == STATE_UNAVAILABLE
    assert not tree_entry.runtime_data.has_playshelf
    async_fire_mqtt_message(hass, f"{SHELF}/state", json.dumps(STATE), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/capabilities", _capabilities("playguard", "playshelf"), retain=True)
    await hass.async_block_till_done()
    assert hass.states.get(pending).state == "3"


async def test_an_old_tree_has_no_module(hass: HomeAssistant, mqtt_mock, setup) -> None:
    """A console still on the old tree has no PlayShelf, and an order for it goes nowhere."""
    console = setup.runtime_data
    assert console.tree == 1 and not console.has_playshelf
    mqtt_mock.async_publish.reset_mock()
    await console.async_playshelf_order("pause_downloads/set", "PRESS")
    assert mqtt_mock.async_publish.call_count == 0
