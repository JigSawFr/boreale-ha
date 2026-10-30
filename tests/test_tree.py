"""Boréale's topic tree: a console moving to it, an entry set up on it."""

from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.playguard.config_flow import _where
from custom_components.playguard.const import CONF_CONSOLE_ID, CONF_PREFIX, CONF_TAKE_OVER, CONF_TREE, DOMAIN

from .conftest import BASE, CONSOLE_ID, fixture
from .test_config_flow import _answered, _choices, _scanned, _state_of

TREE = f"boreale/{CONSOLE_ID}"  # the device's topics
MODULE = f"{TREE}/playguard"  # PlayGuard's


def _published(mqtt_mock) -> list[tuple]:
    return [c.args for c in mqtt_mock.async_publish.call_args_list]


def test_where() -> None:
    assert _where(f"playguard/{CONSOLE_ID}/state") == ("playguard", CONSOLE_ID, 1)
    assert _where(f"home/playguard/{CONSOLE_ID}/state") == ("home/playguard", CONSOLE_ID, 1)
    assert _where(f"boreale/{CONSOLE_ID}/playguard/state") == ("boreale", CONSOLE_ID, 2)
    assert _where(f"home/switch/{CONSOLE_ID}/playguard/state") == ("home/switch", CONSOLE_ID, 2)
    for topic in ("state", f"{CONSOLE_ID}/state", "boreale/nope/playguard/state", f"boreale/{CONSOLE_ID}/system"):
        assert _where(topic) is None, topic


async def test_discovered_on_the_tree(hass: HomeAssistant) -> None:
    info = MqttServiceInfo(
        topic=f"{MODULE}/state",
        payload=json.dumps(fixture("state.json")),
        qos=0,
        retain=True,
        subscribed_topic="boreale/+/playguard/state",
        timestamp=0,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "boreale", CONF_TREE: 2}


async def test_rediscovered_on_the_tree(hass: HomeAssistant, setup) -> None:
    """An entry on the old tree, the console found on the new one: the entry
    follows it by itself (the flow changes nothing)."""
    doc = {**fixture("state.json"), "ts": 1792000000}
    info = MqttServiceInfo(
        topic=f"{MODULE}/state", payload=json.dumps(doc), qos=0, retain=False,
        subscribed_topic="boreale/+/playguard/state", timestamp=0,
    )  # fmt: skip
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_the_console_moves(hass: HomeAssistant, mqtt_mock, setup, state: dict) -> None:
    """A console on the old tree updated to a PlayGuard on Boréale's: the entry
    follows it at its first message there, leaves the old tree behind, and
    sends its orders and its version to the new one."""
    console = setup.runtime_data
    assert (console.tree, console.base) == (1, BASE)
    mqtt_mock.async_publish.reset_mock()
    moved = {**state, "ts": state["ts"] + 60}
    async_fire_mqtt_message(hass, f"{MODULE}/state", json.dumps(moved))
    await hass.async_block_till_done()
    assert (console.tree, console.prefix, console.base) == (2, "boreale", TREE)
    assert setup.data[CONF_TREE] == 2 and setup.data[CONF_PREFIX] == "boreale"
    assert console.state["ts"] == moved["ts"]
    version = [args for args in _published(mqtt_mock) if args[0] == f"{TREE}/integration"]
    assert version and json.loads(version[0][1])["schema"] == 1

    # What the console clears on the old tree is not read.
    async_fire_mqtt_message(hass, f"{BASE}/state", "", retain=True)
    async_fire_mqtt_message(hass, f"{BASE}/availability", "offline", retain=True)
    await hass.async_block_till_done()
    assert console.state["ts"] == moved["ts"] and console.online is not False

    # The device's topics stay at its level, PlayGuard's under its module.
    async_fire_mqtt_message(hass, f"{TREE}/system", json.dumps({**fixture("system.json"), "platform": "switch"}))
    async_fire_mqtt_message(
        hass,
        f"{TREE}/capabilities",
        json.dumps({"schema": 1, "platform": "switch", "modules": {"playguard": {"schema": 1, "version": "1.4.0"}}}),
    )
    await hass.async_block_till_done()
    assert console.system is not None and console.capabilities["modules"]["playguard"]["version"] == "1.4.0"
    assert console.platform == "switch"
    mqtt_mock.async_publish.reset_mock()
    await console.async_send("stop_today", "PRESS")
    assert _published(mqtt_mock) == [(f"{MODULE}/stop_today/set", "PRESS", 1, True)]


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


async def test_set_up_on_the_tree(hass: HomeAssistant, mqtt_mock, tree_entry: MockConfigEntry, state: dict) -> None:
    """An entry on Boréale's tree listens to it alone."""
    tree_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(tree_entry.entry_id)
    await hass.async_block_till_done()
    subscribed = {c.args[0] for c in mqtt_mock.async_subscribe.call_args_list}
    assert {f"{MODULE}/state", f"{MODULE}/activity/+", f"{TREE}/availability", f"{TREE}/system"} <= subscribed
    assert {f"{TREE}/capabilities", f"{TREE}/icon/+"} <= subscribed
    assert not any(t.startswith(f"playguard/{CONSOLE_ID}/") for t in subscribed)
    async_fire_mqtt_message(hass, f"{MODULE}/state", json.dumps(state), retain=True)
    async_fire_mqtt_message(hass, f"{TREE}/availability", "online", retain=True)
    await hass.async_block_till_done()
    console = tree_entry.runtime_data
    assert console.state is not None and console.online is True
    assert console.platform == "switch"  # not said yet: a Switch


async def test_by_hand_on_the_tree(hass: HomeAssistant, mqtt_mock) -> None:
    """The default prefix finds a console on Boréale's tree too."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "manual"
    step = hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"}
    )
    with patch("custom_components.playguard.config_flow.STATE_TIMEOUT", 5):
        result = await _answered(hass, mqtt_mock, step, f"{MODULE}/state", json.dumps(fixture("state.json")))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "boreale", CONF_TREE: 2}


async def test_found_on_the_tree(hass: HomeAssistant, mqtt_mock) -> None:
    result = await _scanned(hass, mqtt_mock, [(f"{MODULE}/state", _state_of("Salon", 1))])
    assert _choices(result)[0] == (CONSOLE_ID, f"Salon ({CONSOLE_ID})")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"console": CONSOLE_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "boreale", CONF_TREE: 2}
