"""A console on the broker: its entities, its orders, its events."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry
import voluptuous as vol

from custom_components.playguard.const import DOMAIN

from .conftest import BASE, CONSOLE_ID, fixture, publish


def _published(mqtt_mock) -> list[tuple]:
    """What was published: (topic, payload, qos, retain) per message."""
    return [c.args for c in mqtt_mock.async_publish.call_args_list]


def _id(platform: str, key: str, hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


async def test_entities_from_the_state(hass: HomeAssistant, setup) -> None:
    def state(platform: str, key: str) -> str:
        return hass.states.get(_id(platform, key, hass)).state

    assert state("binary_sensor", "parental_controls_enabled") == STATE_ON
    assert state("binary_sensor", "limit_reached") == STATE_OFF
    assert state("binary_sensor", "online") == STATE_ON
    assert state("sensor", "used_screen_time") == "75"
    used = hass.states.get(_id("sensor", "used_screen_time", hass))
    assert used.attributes["state_class"] == "total_increasing"  # back to 0 at midnight
    assert state("sensor", "screen_time_remaining") == "45"
    assert state("sensor", "now_playing") == "Super Mario Odyssey"
    assert state("sensor", "firmware") == "23.0.1"
    assert state("number", "limit_mon") == "120"
    assert state("number", "limit_sat") == "1440"
    assert state("number", "limit_uniform") == STATE_UNKNOWN  # the days differ
    assert state("time", "bedtime_alarm") == "21:30:00"
    assert state("time", "bedtime_end_time") == "06:00:00"
    assert state("switch", "bedtime_enabled") == STATE_ON
    assert state("switch", "vr_restricted") == STATE_UNKNOWN  # null: not read
    assert state("select", "restriction_level") == "child"
    profile = hass.states.get(_id("select", "profile", hass))
    assert profile.attributes["options"] == ["School week", "Holidays"]

    log = hass.states.get(_id("sensor", "used_screen_time_log", hass))
    assert log.state == "74"
    assert log.attributes["games"] == {"Super Mario Odyssey": 60, "Mario Kart 8 Deluxe": 14}

    # The integration's own diagnostics: the link, and the agent (rarely needed: off).
    registry = er.async_get(hass)
    assert registry.async_get(_id("binary_sensor", "online", hass)).entity_category is EntityCategory.DIAGNOSTIC
    agent = registry.async_get(_id("binary_sensor", "agent", hass))
    assert agent.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(_id("button", "sync_now", hass)).entity_category is EntityCategory.DIAGNOSTIC

    # The device takes the console's name and versions.
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    assert device.name == "Salon" and device.sw_version == "1.1.0" and device.hw_version == "23.0.1"


async def test_unavailable_while_offline(
    hass: HomeAssistant, setup, mqtt_mock, caplog: pytest.LogCaptureFixture
) -> None:
    """The console's last will makes its entities unavailable, logged once;
    the actions still send their orders, which wait on the broker."""
    publish(hass, "availability", "offline")
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    assert hass.states.get(_id("binary_sensor", "online", hass)).state == STATE_OFF
    for platform, key in (("number", "limit_mon"), ("event", "events"), ("sensor", "used_screen_time")):
        assert hass.states.get(_id(platform, key, hass)).state == STATE_UNAVAILABLE, key
    assert caplog.text.count("Salon is offline") == 1

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(DOMAIN, "add_bonus_time", {"device_id": device.id, "minutes": 15}, blocking=True)
    assert _published(mqtt_mock) == [(f"{BASE}/add_bonus_time/set", "15", 1, True)]

    publish(hass, "availability", "online")
    publish(hass, "availability", "online")
    await hass.async_block_till_done()
    assert hass.states.get(_id("number", "limit_mon", hass)).state == "120"
    assert caplog.text.count("Salon is back online") == 1


async def test_unavailable_before_the_state(hass: HomeAssistant, mqtt_mock, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(_id("number", "limit_mon", hass)).state == STATE_UNAVAILABLE
    assert hass.states.get(_id("binary_sensor", "online", hass)).state == STATE_UNAVAILABLE


async def test_waits_for_mqtt(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "mqtt_not_ready"


async def test_takes_over_the_native_discovery(hass: HomeAssistant, setup, mqtt_mock) -> None:
    assert (f"{BASE}/discovery/set", "OFF", 1, True) in _published(mqtt_mock)
    count = mqtt_mock.async_publish.call_count
    # Once: the console clears it, its next state says so.
    publish(hass, "state", fixture("state.json"))
    await hass.async_block_till_done()
    assert mqtt_mock.async_publish.call_count == count


async def test_tells_the_console_its_version(hass: HomeAssistant, setup, mqtt_mock) -> None:
    """Retained, once at set-up: PlayGuard warns of a newer release of the integration."""
    manifest = json.loads((Path(__file__).parents[1] / "custom_components/playguard/manifest.json").read_text())
    told = [p for p in _published(mqtt_mock) if p[0] == f"{BASE}/integration"]
    assert len(told) == 1
    _topic, payload, qos, retain = told[0]
    assert (qos, retain) == (1, True)
    assert json.loads(payload) == {"schema": 1, "version": manifest["version"], "homeassistant": HA_VERSION}


async def test_version_not_told(hass: HomeAssistant, mqtt_mock, entry, caplog: pytest.LogCaptureFixture) -> None:
    """The broker refusing it does not fail the set-up."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.playguard.coordinator.mqtt.async_publish", side_effect=HomeAssistantError("MQTT is gone")
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert "could not tell the console the integration's version" in caplog.text


async def test_orders(hass: HomeAssistant, setup, mqtt_mock) -> None:
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        "number", "set_value", {"entity_id": _id("number", "limit_mon", hass), "value": 90}, blocking=True
    )
    await hass.services.async_call(
        "time", "set_value", {"entity_id": _id("time", "bedtime_alarm", hass), "time": "21:00:00"}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": _id("switch", "console_lock", hass)}, blocking=True
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _id("select", "restriction_level", hass), "option": "teen"},
        blocking=True,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": _id("button", "add_bonus_time_30", hass)}, blocking=True
    )
    assert _published(mqtt_mock) == [
        (f"{BASE}/limit_mon/set", "90", 1, True),
        (f"{BASE}/bedtime_alarm/set", "21:00", 1, True),
        (f"{BASE}/console_lock/set", "OFF", 1, True),
        (f"{BASE}/restriction_level/set", "teen", 1, True),
        (f"{BASE}/add_bonus_time_30/set", "PRESS", 1, True),
    ]


async def test_restriction_level_unrestricted(hass: HomeAssistant, setup, mqtt_mock, state) -> None:
    """PlayGuard's level "none" is the option "unrestricted"; its order is still "none"."""
    state["controls"]["level"] = "none"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    entity_id = _id("select", "restriction_level", hass)
    select = hass.states.get(entity_id)
    assert select.state == "unrestricted" and "none" not in select.attributes["options"]
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "unrestricted"}, blocking=True
    )
    assert _published(mqtt_mock) == [(f"{BASE}/restriction_level/set", "none", 1, True)]


async def test_orders_the_console_would_refuse(hass: HomeAssistant, setup, mqtt_mock, state) -> None:
    state["link"]["remote_timer_writes"] = False
    publish(hass, "state", state)
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "number", "set_value", {"entity_id": _id("number", "limit_mon", hass), "value": 90}, blocking=True
        )
    assert err.value.translation_key == "timer_writes_disabled"
    # Locking again and the restrictions need no timer writes.
    await hass.services.async_call("switch", "turn_off", {"entity_id": _id("switch", "unlocked", hass)}, blocking=True)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": _id("switch", "vr_restricted", hass)}, blocking=True
    )
    assert _published(mqtt_mock) == [
        (f"{BASE}/unlocked/set", "OFF", 1, True),
        (f"{BASE}/vr_restricted/set", "ON", 1, True),
    ]

    state["console"]["read_only"] = True
    publish(hass, "state", state)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call("button", "press", {"entity_id": _id("button", "sync_now", hass)}, blocking=True)
    assert err.value.translation_key == "read_only"


async def test_events(hass: HomeAssistant, setup) -> None:
    entity_id = _id("event", "events", hass)
    publish(
        hass,
        "event",
        {
            "schema": 1,
            "source": "app",
            "ts": 1,
            "event_type": "command_rejected",
            "entity": "limit_mon",
            "payload": "5000",
            "reason": "out_of_range",
            "rc": None,
        },
        retain=False,
    )
    await hass.async_block_till_done()
    event = hass.states.get(entity_id)
    assert event.attributes["event_type"] == "command_rejected"
    assert event.attributes["reason"] == "out_of_range" and event.attributes["entity"] == "limit_mon"


async def test_week_and_names(hass: HomeAssistant, setup) -> None:
    publish(
        hass,
        "week",
        {
            "schema": 1,
            "ts": 1,
            "days": ["2026-10-03", "2026-10-04"],
            "games": [{"app_id": "0100000000010000", "min": [30, 60]}, {"app_id": "01000A10041EA000", "min": [0, 15]}],
        },
    )
    await hass.async_block_till_done()
    week = hass.states.get(_id("sensor", "week_play_time", hass))
    assert week.state == "105"
    assert week.attributes["days"] == {"2026-10-03": 30, "2026-10-04": 75}
    assert week.attributes["games"] == {"Super Mario Odyssey": 90, "Mario Kart 8 Deluxe": 15}


async def test_services(hass: HomeAssistant, setup, mqtt_mock) -> None:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(DOMAIN, "set_limits", {"device_id": device.id, "minutes": 60}, blocking=True)
    await hass.services.async_call(
        DOMAIN, "set_limits", {"device_id": device.id, "minutes": 45, "day": "today"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "set_limits", {"device_id": device.id, "week": [60, 60, 60, 60, 60, 120, 120]}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "add_bonus_time", {"device_id": device.id, "minutes": 20}, blocking=True)
    await hass.services.async_call(
        DOMAIN, "apply_profile", {"device_id": device.id, "profile": "Holidays"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "request_report", {"device_id": device.id}, blocking=True)
    assert _published(mqtt_mock) == [
        (f"{BASE}/limit_uniform/set", "60", 1, True),
        (f"{BASE}/max_screentime_today/set", "45", 1, True),
        (f"{BASE}/limits_week/set", "60,60,60,60,60,120,120", 1, True),
        (f"{BASE}/add_bonus_time/set", "20", 1, True),
        (f"{BASE}/profile/set", "Holidays", 1, True),
        (f"{BASE}/export_report/set", "PRESS", 1, True),
    ]
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "apply_profile", {"device_id": device.id, "profile": "Nope"}, blocking=True
        )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": "not-a-device"}, blocking=True)
    assert err.value.translation_key == "service_device_not_found"
    with pytest.raises(vol.Invalid):  # out of bounds: the schema refuses it
        await hass.services.async_call(
            DOMAIN, "add_bonus_time", {"device_id": device.id, "minutes": 500}, blocking=True
        )


async def test_newer_schema(hass: HomeAssistant, setup, state) -> None:
    state["schema"] = 2
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"newer_schema_{CONSOLE_ID}")
    state["schema"] = 1
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert not ir.async_get(hass).async_get_issue(DOMAIN, f"newer_schema_{CONSOLE_ID}")


async def test_native_discovery_repair(hass: HomeAssistant, setup, mqtt_mock, state) -> None:
    """Asked off, the console's own discovery stays on: a repair asks again."""
    assert await async_setup_component(hass, "repairs", {})
    issue_id = f"native_discovery_{CONSOLE_ID}"
    publish(hass, "state", state)  # may have been published before the order
    await hass.async_block_till_done()
    assert not ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    publish(hass, "state", state)
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue and issue.is_fixable and issue.translation_placeholders == {"name": "Salon"}

    mqtt_mock.async_publish.reset_mock()
    flows = repairs_flow_manager(hass)
    result = await flows.async_init(DOMAIN, context={"issue_id": issue_id})
    assert result["step_id"] == "confirm"
    result = await flows.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert _published(mqtt_mock) == [(f"{BASE}/discovery/set", "OFF", 1, True)]
    assert not ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    # Back again, then gone for good.
    publish(hass, "state", state)
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    state["link"]["ha_discovery"] = False
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert not ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


async def test_issues_go_with_the_entry(hass: HomeAssistant, setup, state) -> None:
    state["schema"] = 2
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"newer_schema_{CONSOLE_ID}")
    assert await hass.config_entries.async_unload(setup.entry_id)
    assert not ir.async_get(hass).async_get_issue(DOMAIN, f"newer_schema_{CONSOLE_ID}")


async def test_diagnostics(hass: HomeAssistant, setup, hass_client) -> None:
    activity = fixture("activity.json")
    activity["per_account"] = [{"uid": "00112233445566778899AABBCCDDEEFF", "s": 600, "min": 10}]
    publish(hass, "activity", activity)
    publish(hass, "report", "=== PlayGuard report ===\nfirmware 23.0.1\n")
    system = fixture("system.json")
    system["hardware"]["serial"] = "XAW10012345678"
    publish(hass, "system", system)
    publish(hass, "games", fixture("games.json"))
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, setup)
    assert diag["system"]["hardware"]["model"] == "oled" and diag["games"] == {"installed": 2, "listed": 3}
    for key in ("serial", "nickname"):
        assert diag["system"]["hardware"][key] == REDACTED
    assert diag["system"]["network"]["ssid"] == REDACTED and diag["system"]["network"]["ip"] == REDACTED
    assert "XAW10012345678" not in json.dumps(diag) and "Maison" not in json.dumps(diag)
    assert diag["report"].startswith("=== PlayGuard report ===")
    assert diag["online"] is True
    assert diag["state"]["console"]["firmware"] == "23.0.1"
    # What may name someone is not there.
    assert diag["state"]["console"]["name"] == REDACTED
    assert diag["state"]["profiles"] == REDACTED
    assert diag["activity"]["per_account"][0]["uid"] == REDACTED
    assert "Salon" not in json.dumps(diag)


async def test_unload_and_remove(hass: HomeAssistant, setup, mqtt_mock) -> None:
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()
    await hass.config_entries.async_remove(setup.entry_id)
    await hass.async_block_till_done()
    # The console's own discovery comes back, and it forgets the integration's version.
    assert _published(mqtt_mock) == [(f"{BASE}/discovery/set", "ON", 1, True), (f"{BASE}/integration", "", 1, True)]


async def test_remove_without_mqtt(hass: HomeAssistant, setup, caplog: pytest.LogCaptureFixture) -> None:
    """MQTT may be gone when the entry is removed: the removal still goes through."""
    assert await hass.config_entries.async_unload(setup.entry_id)
    with patch(
        "custom_components.playguard.coordinator.mqtt.async_publish", side_effect=HomeAssistantError("MQTT is gone")
    ):
        await hass.config_entries.async_remove(setup.entry_id)
        await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(setup.entry_id) is None
    assert "could not be turned back on" in caplog.text
