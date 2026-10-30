"""Finding a console: MQTT discovery, by hand, reconfiguring, the options."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import json
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.playguard.const import (
    CONF_CONSOLE_ID,
    CONF_KEEP_VALUES,
    CONF_NOTIFY_REFUSED,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_TREE,
    DOMAIN,
)

from .conftest import CONSOLE_ID, fixture


def _info(topic: str, payload: str) -> MqttServiceInfo:
    return MqttServiceInfo(
        topic=topic, payload=payload, qos=0, retain=True, subscribed_topic="playguard/+/state", timestamp=0
    )


async def _answered(hass: HomeAssistant, mqtt_mock, step: Awaitable, topic: str, payload: str) -> dict:
    """A flow step that waits for the console's state, the console publishing
    `payload` on `topic` once the step listens (after something that is not
    a state, which the step ignores)."""
    task = hass.async_create_task(step)
    for _ in range(100):
        if any(c.args[0] == topic for c in mqtt_mock.async_subscribe.call_args_list):
            break
        await asyncio.sleep(0)
    else:
        pytest.fail(f"nothing subscribed to {topic}")
    async_fire_mqtt_message(hass, topic, "not json")
    async_fire_mqtt_message(hass, topic, payload)
    return await task


@pytest.fixture
def no_wait():
    """No console answers: the flows give up at once."""
    with patch("custom_components.playguard.config_flow.STATE_TIMEOUT", 0.01):
        yield


@pytest.fixture(autouse=True)
def short_scan():
    """Adding a console by hand listens for the consoles briefly."""
    with patch("custom_components.playguard.config_flow.SCAN_TIMEOUT", 0.01):
        yield


async def _scanned(hass: HomeAssistant, mqtt_mock, retained: list[tuple[str, str]]) -> dict:
    """Adding a console by hand, the broker handing these retained states over
    once the flow listens."""
    task = hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    )
    with patch("custom_components.playguard.config_flow.SCAN_TIMEOUT", 0.5):
        for _ in range(100):
            subscribed = {c.args[0] for c in mqtt_mock.async_subscribe.call_args_list}
            if {"+/+/state", "+/+/+/state"} <= subscribed:
                break
            await asyncio.sleep(0)
        else:
            pytest.fail("the flow did not listen")
        for topic, payload in retained:
            async_fire_mqtt_message(hass, topic, payload, retain=True)
        return await task


def _choices(result: dict) -> list[tuple[str, str]]:
    [selector] = result["data_schema"].schema.values()
    return [(o["value"], o["label"]) for o in selector.config["options"]]


def _state_of(name: str | None, ts: int) -> str:
    doc = {**fixture("state.json"), "ts": ts}
    doc["console"] = {**doc["console"], "name": name} if name else {}
    return json.dumps(doc)


async def test_discovered(hass: HomeAssistant) -> None:
    info = _info(f"playguard/{CONSOLE_ID}/state", json.dumps(fixture("state.json")))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": "Salon", "console_id": CONSOLE_ID}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Salon"
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard", CONF_TREE: 1}
    assert result["options"] == {CONF_TAKE_OVER: True}
    assert result["result"].unique_id == CONSOLE_ID
    assert (result["result"].version, result["result"].minor_version) == (1, 3)  # nothing to migrate

    # The retained state comes again at every start: already set up.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
async def moved(hass: HomeAssistant, mqtt_mock, state: dict) -> MockConfigEntry:
    """A console set up under another prefix, its state (ts 1791000000) read there."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "home/playguard"},
        options={CONF_TAKE_OVER: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, f"home/playguard/{CONSOLE_ID}/state", json.dumps(state))
    await hass.async_block_till_done()
    assert entry.runtime_data.state["ts"] == 1791000000
    return entry


async def _rediscovered(hass: HomeAssistant, ts: object) -> dict:
    """The console's state found under the default prefix, built at `ts`."""
    doc = {**fixture("state.json"), "ts": ts}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=_info(f"playguard/{CONSOLE_ID}/state", json.dumps(doc)),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    return result


async def test_rediscovery_ignores_a_stale_state(hass: HomeAssistant, moved) -> None:
    """A state left retained under the console's former prefix (older, or no
    time at all) does not move the entry back."""
    console = moved.runtime_data
    for ts in (1790000000, 1791000000, None, True):
        await _rediscovered(hass, ts)
        assert moved.data[CONF_PREFIX] == "home/playguard", ts
    assert moved.runtime_data is console  # not reloaded


async def test_rediscovery_follows_a_newer_state(hass: HomeAssistant, moved) -> None:
    """The console moved back to the default prefix: the entry follows, and reloads."""
    console = moved.runtime_data
    await _rediscovered(hass, 1792000000)
    assert moved.data[CONF_PREFIX] == "playguard"
    assert moved.state is config_entries.ConfigEntryState.LOADED
    assert moved.runtime_data is not console and moved.runtime_data.base == f"playguard/{CONSOLE_ID}"


async def test_rediscovery_waits_for_a_loaded_entry(hass: HomeAssistant) -> None:
    """Not loaded yet: nothing to compare with; the console's next state will do."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CONSOLE_ID, data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "home/playguard"}
    )
    entry.add_to_hass(hass)
    await _rediscovered(hass, 1792000000)
    assert entry.data[CONF_PREFIX] == "home/playguard"


async def test_rediscovery_under_the_same_prefix(hass: HomeAssistant, setup) -> None:
    console = setup.runtime_data
    await _rediscovered(hass, 1792000000)
    assert setup.data[CONF_PREFIX] == "playguard"
    assert setup.runtime_data is console


async def test_discovery_ignores_other_messages(hass: HomeAssistant) -> None:
    for topic, payload in (
        ("playguard/NOT-AN-ID/state", json.dumps(fixture("state.json"))),
        (f"playguard/{CONSOLE_ID}/state", ""),  # cleared
        (f"playguard/{CONSOLE_ID}/state", "not json"),
        (f"playguard/{CONSOLE_ID}/state", json.dumps({"a": 1})),  # no schema: not PlayGuard's
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_info(topic, payload)
        )
        assert result["type"] is FlowResultType.ABORT, topic
        assert result["reason"] == "invalid_discovery_info"


async def test_found_on_the_broker(hass: HomeAssistant, mqtt_mock) -> None:
    """The consoles whose state is on the broker, under a prefix of one level
    or two, to pick from; what is not a console's state is left out."""
    result = await _scanned(
        hass,
        mqtt_mock,
        [
            (f"playguard/{CONSOLE_ID}/state", _state_of("Salon", 1791000000)),
            ("home/playguard/0badc0de/state", _state_of("Chambre", 1791000000)),
            ("old/0badc0de/state", _state_of("Chambre", 1780000000)),  # its former prefix: older
            ("playguard/0000abcd/state", _state_of(None, 1791000000)),  # no name
            ("zigbee2mqtt/bridge/state", json.dumps({"state": "online"})),
            ("playguard/deadbeef/state", "not json"),
        ],
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert _choices(result) == [
        ("0badc0de", "Chambre (0badc0de), home/playguard"),
        ("0000abcd", "Nintendo Switch (0000abcd)"),
        (CONSOLE_ID, f"Salon ({CONSOLE_ID})"),
        ("manual", "Another console, by its id"),
    ]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"console": "0badc0de"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Chambre"
    assert result["data"] == {CONF_CONSOLE_ID: "0badc0de", CONF_PREFIX: "home/playguard", CONF_TREE: 1}
    assert result["result"].unique_id == "0badc0de"


async def test_found_then_by_its_id(hass: HomeAssistant, mqtt_mock) -> None:
    result = await _scanned(hass, mqtt_mock, [(f"playguard/{CONSOLE_ID}/state", _state_of("Salon", 1))])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"console": "manual"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_found_but_set_up_meanwhile(hass: HomeAssistant, mqtt_mock) -> None:
    result = await _scanned(hass, mqtt_mock, [(f"playguard/{CONSOLE_ID}/state", _state_of("Salon", 1))])
    MockConfigEntry(domain=DOMAIN, unique_id=CONSOLE_ID, data={CONF_CONSOLE_ID: CONSOLE_ID}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"console": CONSOLE_ID})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_found_already_set_up(hass: HomeAssistant, setup, mqtt_mock) -> None:
    """A console set up already is not offered: none left, its id is asked."""
    result = await _scanned(hass, mqtt_mock, [(f"playguard/{CONSOLE_ID}/state", _state_of("Salon", 1))])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_by_hand(hass: HomeAssistant, mqtt_mock, no_wait) -> None:
    # No console on the broker: its id is asked at once.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: "nope", CONF_PREFIX: "playguard"}
    )
    assert result["errors"] == {CONF_CONSOLE_ID: "invalid_console_id"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: "A1B2C3D4", CONF_PREFIX: "bad/+/prefix"}
    )
    assert result["errors"] == {CONF_PREFIX: "invalid_prefix"}
    # Nothing from this console under that prefix.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: "A1B2C3D4", CONF_PREFIX: "elsewhere"}
    )
    assert result["errors"] == {"base": "no_state"}
    # It answers under the right one.
    step = hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: " A1B2C3D4 ", CONF_PREFIX: "home/playguard/"}
    )
    topic = f"home/playguard/{CONSOLE_ID}/state"
    with patch("custom_components.playguard.config_flow.STATE_TIMEOUT", 5):
        result = await _answered(hass, mqtt_mock, step, topic, json.dumps(fixture("state.json")))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Salon"  # the console's name
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "home/playguard", CONF_TREE: 1}
    assert result["result"].unique_id == CONSOLE_ID


async def test_by_hand_while_discovered(hass: HomeAssistant, mqtt_mock) -> None:
    """The console waits in Discovered: adding it by hand still works."""
    info = _info(f"playguard/{CONSOLE_ID}/state", json.dumps(fixture("state.json")))
    discovered = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert discovered["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    topic = f"playguard/{CONSOLE_ID}/state"
    step = hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"}
    )
    result = await _answered(hass, mqtt_mock, step, topic, json.dumps(fixture("state.json")))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == CONSOLE_ID


async def test_by_hand_already_configured(hass: HomeAssistant, setup) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_by_hand_without_mqtt(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_ready"


async def test_reconfigure(hass: HomeAssistant, setup, mqtt_mock, no_wait) -> None:
    result = await setup.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PREFIX: "bad/+/prefix"})
    assert result["errors"] == {CONF_PREFIX: "invalid_prefix"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PREFIX: "elsewhere"})
    assert result["errors"] == {"base": "no_state"}
    step = hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PREFIX: " home/playguard/ "})
    topic = f"home/playguard/{CONSOLE_ID}/state"
    with patch("custom_components.playguard.config_flow.STATE_TIMEOUT", 5):
        result = await _answered(hass, mqtt_mock, step, topic, json.dumps(fixture("state.json")))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert setup.data == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "home/playguard", CONF_TREE: 1}
    assert setup.options == {CONF_TAKE_OVER: True}

    # Reloaded: the console is heard under the new prefix only.
    async_fire_mqtt_message(hass, f"home/playguard/{CONSOLE_ID}/availability", "online")
    async_fire_mqtt_message(hass, f"playguard/{CONSOLE_ID}/availability", "offline")
    await hass.async_block_till_done()
    online = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, f"{CONSOLE_ID}_online")
    assert hass.states.get(online).state == STATE_ON


async def test_reconfigure_without_mqtt(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_ready"


async def test_options(hass: HomeAssistant, setup) -> None:
    result = await hass.config_entries.options.async_init(setup.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_TAKE_OVER: False, CONF_KEEP_VALUES: False, CONF_NOTIFY_REFUSED: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert setup.options == {CONF_TAKE_OVER: False, CONF_KEEP_VALUES: False, CONF_NOTIFY_REFUSED: False}
