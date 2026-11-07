"""A Lantern bridge: found on the broker or by its prefix, its state pushed over MQTT, one order."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.boreale.bridge import bridge_of, parse_state
from custom_components.boreale.const import (
    CONF_BRIDGE_ID,
    CONF_BRIDGE_PREFIX,
    CONF_KIND,
    DEFAULT_BRIDGE_PREFIX,
    DOMAIN,
    KIND_BRIDGE,
)
from custom_components.boreale.diagnostics import async_get_config_entry_diagnostics

from .conftest import start_console_flow  # noqa: F401  (the console path is tested in test_config_flow)

UID = "0c9c2a8e-5d3a-4c7e-8b0a-6f1d2e3c4b5a"
BASE = f"lantern-bridge/{UID}"
STATE: dict[str, Any] = {
    "schema": 1,
    "ts": 1_000_000,
    "bridge": {"uid": UID, "name": "Shelf", "version": "0.1.0"},
    "status": "ok",
    "checks": [{"name": "disk", "status": "ok"}],
    "library": {"titles": 12, "apps": 14},
    "files": {"hashed": 30, "pending": 3, "pending_bytes": 100},
    "traffic": {"requests": 9, "sent_bytes": 1000, "errors": 4, "refused": 0, "transfers": 1},
    "sources": [{"id": "games", "kind": "folder", "up": True}, {"id": "shop", "kind": "tinfoil", "up": False}],
    "uptime": 60,
}
INTEGRATION = Path(__file__).parent.parent / "custom_components" / "boreale"


def _info(topic: str, payload: str) -> MqttServiceInfo:
    return MqttServiceInfo(
        topic=topic, payload=payload, qos=0, retain=True, subscribed_topic="lantern-bridge/+/state", timestamp=0
    )


def _publish(hass: HomeAssistant, sub: str, doc: Any, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, f"{BASE}/{sub}", doc if isinstance(doc, str) else json.dumps(doc), retain=retain)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Shelf",
        unique_id=f"bridge_{UID}",
        data={CONF_KIND: KIND_BRIDGE, CONF_BRIDGE_ID: UID, CONF_BRIDGE_PREFIX: DEFAULT_BRIDGE_PREFIX},
        minor_version=3,
    )


async def _set_up(hass: HomeAssistant, mqtt_mock, state: dict | None = STATE) -> MockConfigEntry:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    _publish(hass, "availability", "online", retain=True)
    if state is not None:
        _publish(hass, "state", state, retain=True)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, platform: str, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"bridge_{UID}_bridge_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


def test_a_state_is_read_by_its_schema_and_its_topic() -> None:
    assert parse_state(json.dumps(STATE)) == STATE
    for bad in ("", "not json", "[]", json.dumps({**STATE, "schema": 2}), json.dumps({**STATE, "schema": True})):
        assert parse_state(bad) is None
    assert bridge_of(f"{BASE}/state", json.dumps(STATE)) == ("lantern-bridge", UID, "Shelf")
    assert bridge_of(f"a/b/{UID}/state", json.dumps(STATE)) == ("a/b", UID, "Shelf")
    assert bridge_of("lantern-bridge/other/state", json.dumps(STATE)) is None  # not the id the state gives
    assert bridge_of(f"{BASE}/availability", json.dumps(STATE)) is None
    nameless = {**STATE, "bridge": {"uid": UID}}
    assert bridge_of(f"{BASE}/state", json.dumps(nameless)) == ("lantern-bridge", UID, "Lantern bridge")


async def test_found_on_the_broker(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_info(f"{BASE}/state", json.dumps(STATE))
    )
    assert result["step_id"] == "confirm_bridge" and result["description_placeholders"] == {"name": "Shelf"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["title"] == "Shelf"
    assert result["data"] == {CONF_KIND: KIND_BRIDGE, CONF_BRIDGE_ID: UID, CONF_BRIDGE_PREFIX: "lantern-bridge"}


async def test_found_again_under_another_prefix_it_follows(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _set_up(hass, mqtt_mock)
    moved = f"home/shelf/{UID}/state"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_info(moved, json.dumps(STATE))
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert entry.data[CONF_BRIDGE_PREFIX] == "home/shelf"


async def _manual(hass: HomeAssistant, prefix: str, answer: dict | None):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU and result["menu_options"] == ["console", "bridge"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "bridge"})
    assert result["step_id"] == "bridge"
    found = None if answer is None else ("lantern-bridge", UID, "Shelf")
    with patch("custom_components.boreale.config_flow._async_wait_for_bridge", return_value=found):
        return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: prefix})


async def test_added_by_its_prefix(hass: HomeAssistant, mqtt_mock) -> None:
    result = await _manual(hass, "/lantern-bridge/", STATE)
    assert result["step_id"] == "confirm_bridge"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["data"][CONF_BRIDGE_ID] == UID


async def test_by_prefix_errors(hass: HomeAssistant, mqtt_mock) -> None:
    assert (await _manual(hass, "a/#", STATE))["errors"] == {CONF_BRIDGE_PREFIX: "invalid_prefix"}
    assert (await _manual(hass, "lantern-bridge", None))["errors"] == {"base": "no_bridge"}


async def test_by_prefix_listens_for_the_state_for_real(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "bridge"})
    with patch("custom_components.boreale.config_flow.STATE_TIMEOUT", 0.01):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: "nothing"})
    assert result["errors"] == {"base": "no_bridge"}


async def test_a_bridge_set_up_is_not_offered_twice(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock)
    captured: dict[str, Any] = {}

    async def wait(_hass, prefix, bridge_id=None, skip=None):
        captured["skip"] = skip

    with patch("custom_components.boreale.config_flow._async_wait_for_bridge", wait):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "bridge"})
        await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: "lantern-bridge"})
    assert captured["skip"] == {UID}


async def test_reconfigured_to_another_prefix(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _set_up(hass, mqtt_mock)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_bridge"
    with patch("custom_components.boreale.config_flow._async_wait_for_bridge", return_value=None):
        bad = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: "home/shelf"})
    assert bad["errors"] == {"base": "no_bridge"}
    invalid = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: "a/+"})
    assert invalid["errors"] == {CONF_BRIDGE_PREFIX: "invalid_prefix"}
    with patch(
        "custom_components.boreale.config_flow._async_wait_for_bridge", return_value=("home/shelf", UID, "Shelf")
    ):
        done = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_BRIDGE_PREFIX: "home/shelf"})
    assert done["type"] is FlowResultType.ABORT and entry.data[CONF_BRIDGE_PREFIX] == "home/shelf"


async def test_its_status_and_figures_are_pushed(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock)
    assert _state(hass, "sensor", "status").state == "ok" and _state(hass, "sensor", "version").state == "0.1.0"
    assert _state(hass, "sensor", "titles").state == "12" and _state(hass, "sensor", "files_pending").state == "3"
    assert _state(hass, "sensor", "errors").state == "4" and _state(hass, "sensor", "transfers").state == "1"
    assert _state(hass, "sensor", "sources_down").state == "1"
    assert _state(hass, "binary_sensor", "reachable").state == "on"
    _publish(hass, "state", {**STATE, "status": "warn", "bridge": {**STATE["bridge"], "version": "0.2.0"}})
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "status").state == "warn"


async def test_the_update_entity_follows_the_bridges_own_check(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock)
    entity_id = er.async_get(hass).async_get_entity_id("update", DOMAIN, f"bridge_{UID}_bridge_update")
    assert entity_id
    # No check in the state (off, or not made yet): the installed version, nothing to update.
    shown = hass.states.get(entity_id)
    assert shown.state == "off" and shown.attributes["installed_version"] == "0.1.0"
    assert shown.attributes["latest_version"] == "0.1.0" and shown.attributes["release_url"] is None
    # A newer release found by the bridge.
    _publish(hass, "state", {**STATE, "update": {"available": True, "latest": "v0.2.0"}})
    await hass.async_block_till_done()
    shown = hass.states.get(entity_id)
    assert shown.state == "on" and shown.attributes["latest_version"] == "0.2.0"
    assert shown.attributes["release_url"].endswith("/releases/tag/v0.2.0")
    # Checked and up to date, or a malformed answer: not an update.
    for answer in ({"available": False, "latest": "v0.1.0"}, {"available": True, "latest": None}, "nonsense"):
        _publish(hass, "state", {**STATE, "update": answer})
        await hass.async_block_till_done()
        shown = hass.states.get(entity_id)
        assert shown.state == "off" and shown.attributes["release_url"] is None, answer
    # The entity cannot install anything.
    assert not shown.attributes["supported_features"]


async def test_a_state_this_version_does_not_read_is_skipped(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock)
    for bad in ("garbage", json.dumps({**STATE, "schema": 2, "status": "fail"})):
        _publish(hass, "state", bad)
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "status").state == "ok"


async def test_nothing_is_known_before_its_state_and_all_goes_when_it_does(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock, state=None)
    assert _state(hass, "sensor", "status").state == "unavailable"
    assert _state(hass, "binary_sensor", "reachable").state == "on"
    _publish(hass, "state", STATE)
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "status").state == "ok"
    _publish(hass, "availability", "offline")  # live: the retained flag is for a new subscription
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "status").state == "unavailable"
    assert _state(hass, "binary_sensor", "reachable").state == "off"
    assert _state(hass, "button", "rescan").state == "unavailable"


async def test_the_rescan_button_orders_it_unretained(hass: HomeAssistant, mqtt_mock) -> None:
    await _set_up(hass, mqtt_mock)
    entity_id = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"bridge_{UID}_bridge_rescan")
    assert entity_id
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    mqtt_mock.async_publish.assert_called_once()
    assert mqtt_mock.async_publish.call_args.args == (f"{BASE}/order/rescan", "", 0, False)


async def test_unloaded_and_removed_like_any_entry(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _set_up(hass, mqtt_mock)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_remove(entry.entry_id) == {"require_restart": False}


async def test_diagnostics_do_not_give_the_id_or_the_name(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _set_up(hass, mqtt_mock)
    report = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(report)
    assert report["state"]["status"] == "ok" and UID not in text and "Shelf" not in text


def test_every_bridge_entity_is_named_and_has_its_icon() -> None:
    names = json.loads((INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))["entity"]
    keys = {
        "sensor": ["status", "version", "titles", "files_pending", "transfers", "errors", "sources_down"],
        "binary_sensor": ["reachable"],
        "button": ["rescan"],
        "update": ["update"],
    }
    for platform, found in keys.items():
        for key in found:
            assert f"bridge_{key}" in names[platform] and f"bridge_{key}" in icons[platform], key
