"""What the main tests do not send: malformed, partial or cleared documents,
a console that changes its name, orders before any state, and the hooks
Home Assistant calls later on."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.playguard.const import DOMAIN, WRITE_NONE
from custom_components.playguard.entities import BY_KEY
from custom_components.playguard.event import PlayGuardEvent
from custom_components.playguard.sensor import PlayGuardSensor

from .conftest import BASE, CONSOLE_ID, fixture, publish


def _state(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    return hass.states.get(entity_id).state


def _device(hass: HomeAssistant, entry) -> dr.DeviceEntry:
    return dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)


async def test_malformed_documents(hass: HomeAssistant, setup) -> None:
    """Not JSON, not an object, an unknown availability: the last good ones stay."""
    for sub, payload in (("state", "not json"), ("state", "[1, 2]"), ("event", ""), ("availability", "maybe")):
        publish(hass, sub, payload)
    await hass.async_block_till_done()
    assert _state(hass, "number", "limit_mon") == "120"
    assert _state(hass, "binary_sensor", "online") == "on"
    assert _state(hass, "event", "events") == STATE_UNKNOWN


async def test_partial_state(hass: HomeAssistant, setup, state) -> None:
    """Values of the wrong type, or missing, read as unknown."""
    state["timer"] = "not an object"
    state["controls"]["level"] = 3
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "number", "limit_mon") == STATE_UNKNOWN
    assert _state(hass, "select", "restriction_level") == STATE_UNKNOWN
    assert _state(hass, "sensor", "now_playing") == STATE_UNKNOWN
    assert _state(hass, "time", "bedtime_alarm") == STATE_UNKNOWN

    state["timer"] = fixture("state.json")["timer"]
    state["timer"]["bedtime"]["start"] = "25:99:00"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "time", "bedtime_alarm") == STATE_UNKNOWN
    assert _state(hass, "time", "bedtime_end_time") == "06:00:00"


async def test_odd_activity_and_week(hass: HomeAssistant, setup) -> None:
    """Entries that are not a game, minutes that are not a number, a short week."""
    activity = fixture("activity.json")
    activity["per_app"] += ["junk", {"app_id": 5, "min": 3}]
    publish(hass, "activity", activity)
    publish(
        hass,
        "week",
        {"schema": 1, "days": ["2026-10-03"], "games": [{"app_id": "0100000000010000", "min": [30, 60, "x"]}, None]},
    )
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_used_screen_time_log")
    assert hass.states.get(entity_id).attributes["games"] == {"Super Mario Odyssey": 60, "Mario Kart 8 Deluxe": 14}
    week = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_week_play_time")
    assert hass.states.get(week).state == "30"
    assert hass.states.get(week).attributes["days"] == {"2026-10-03": 30}


async def test_the_device_follows_the_console(hass: HomeAssistant, setup, state) -> None:
    state["console"]["name"] = "Chambre"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _device(hass, setup).name == "Chambre"

    # A name given in Home Assistant stays.
    dr.async_get(hass).async_update_device(_device(hass, setup).id, name_by_user="Léa's Switch")
    state["console"]["name"] = "Salon"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _device(hass, setup).name == "Chambre"

    # The device removed by hand: nothing to update.
    dr.async_get(hass).async_remove_device(_device(hass, setup).id)
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _device(hass, setup) is None


async def test_orders_before_any_state(hass: HomeAssistant, mqtt_mock, entry) -> None:
    """Nothing known yet: the console decides, the order waits on the broker."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(DOMAIN, "stop_today", {"device_id": _device(hass, entry).id}, blocking=True)
    assert [c.args for c in mqtt_mock.async_publish.call_args_list] == [(f"{BASE}/stop_today/set", "PRESS", 1, True)]


async def test_orders_refused_here(hass: HomeAssistant, setup, state) -> None:
    console = setup.runtime_data
    with pytest.raises(ServiceValidationError) as err:
        console.check_order("firmware", WRITE_NONE, "1")
    assert err.value.translation_key == "read_only_entity"

    state["link"]["policy"] = "off"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": _device(hass, setup).id}, blocking=True)
    assert err.value.translation_key == "policy_off"


async def test_unknown_event_type(hass: HomeAssistant, setup) -> None:
    publish(hass, "event", {"schema": 1, "event_type": "something_new", "entity": "limit_mon"})
    await hass.async_block_till_done()
    assert _state(hass, "event", "events") == STATE_UNKNOWN


async def test_statistics_without_the_recorder(hass: HomeAssistant, setup) -> None:
    """No recorder: the finished days are kept, nothing is imported."""
    publish(hass, "activity/2026-10-04", {"schema": 1, "final": True, "total_min": 90, "per_app": []}, retain=True)
    await hass.async_block_till_done()
    with patch("homeassistant.components.recorder.statistics.async_add_external_statistics") as add:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done()
    add.assert_not_called()
    assert sorted(setup.runtime_data.finals) == ["2026-10-04"]


async def test_unload_with_statistics_pending(hass: HomeAssistant, setup) -> None:
    publish(hass, "activity/2026-10-04", {"schema": 1, "final": True, "total_min": 90, "per_app": []}, retain=True)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()


async def test_remove_without_mqtt_set_up(hass: HomeAssistant, entry) -> None:
    """Never set up (no MQTT): removing it publishes nothing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_repair_of_a_gone_entry(hass: HomeAssistant, setup) -> None:
    """The issue outlived its entry: the repair just closes it."""
    assert await async_setup_component(hass, "repairs", {})
    ir.async_create_issue(
        hass,
        DOMAIN,
        "native_discovery_gone",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="native_discovery",
        translation_placeholders={"name": "Salon"},
        data={"entry_id": "gone"},
    )
    flows = repairs_flow_manager(hass)
    result = await flows.async_init(DOMAIN, context={"issue_id": "native_discovery_gone"})
    result = await flows.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not ir.async_get(hass).async_get_issue(DOMAIN, "native_discovery_gone")


async def test_entity_helpers(hass: HomeAssistant, setup, state) -> None:
    """The name falls back to the id; entity id changes in place (2026.11)."""
    console = setup.runtime_data
    state["activity_today"]["now_playing"]["name"] = None
    console.state = state
    sensor = PlayGuardSensor(console, BY_KEY["now_playing"])
    assert sensor.read() == "0100000000010000"

    with patch("homeassistant.helpers.entity.Entity.async_entity_id_changed", Mock(), create=True) as changed:
        sensor.async_entity_id_changed("sensor.old")
        PlayGuardEvent(console, BY_KEY["events"]).async_entity_id_changed("event.old")
    assert [c.args for c in changed.call_args_list] == [("sensor.old",), ("event.old",)]
