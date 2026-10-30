"""Repairs for the settings that refuse orders, the console's events on the
bus and in the logbook, the device's diagnostics."""

from __future__ import annotations

from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.boreale import logbook
from custom_components.boreale.const import DOMAIN, EVENT_PLAYGUARD
from custom_components.boreale.diagnostics import async_get_device_diagnostics

from .conftest import CONSOLE_ID, publish


def _device(hass: HomeAssistant, entry) -> dr.DeviceEntry:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    assert device
    return device


def _issue(hass: HomeAssistant, reason: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"refused_{reason}_{CONSOLE_ID}")


async def test_refusal_repairs(hass: HomeAssistant, setup, state) -> None:
    device_id = _device(hass, setup).id
    state["link"]["policy"] = "off"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _issue(hass, "policy_off") is None  # not until an order is refused
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": device_id}, blocking=True)
    issue = _issue(hass, "policy_off")
    assert issue.translation_key == "refused_policy_off" and issue.translation_placeholders == {"name": "Salon"}

    # Refused by the console itself (the setting changed since the last state).
    event = {"schema": 1, "source": "agent", "ts": 1, "event_type": "command_rejected", "entity": "limit_mon"}
    publish(hass, "event", {**event, "payload": "90", "reason": "timer_writes_disabled", "rc": None})
    await hass.async_block_till_done()
    assert _issue(hass, "timer_writes_disabled") is not None

    # The console says it changed: they go.
    state["link"]["policy"] = "auto"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _issue(hass, "policy_off") is None and _issue(hass, "timer_writes_disabled") is None

    state["console"]["read_only"] = True
    publish(hass, "state", state)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": device_id}, blocking=True)
    assert _issue(hass, "read_only") is not None
    await hass.config_entries.async_unload(setup.entry_id)
    assert _issue(hass, "read_only") is None


async def test_bus_and_logbook(hass: HomeAssistant, setup) -> None:
    events = async_capture_events(hass, EVENT_PLAYGUARD)
    described = {}
    logbook.async_describe_events(hass, lambda domain, event, fn: described.setdefault(event, fn))
    describe = described[EVENT_PLAYGUARD]

    base = {"schema": 1, "source": "agent", "ts": 1}
    publish(hass, "event", {**base, "event_type": "play_started", "app_id": "0100000000010000"})
    publish(hass, "event", {**base, "event_type": "time_warning", "app_id": "0100000000010000", "minutes_left": 10})
    publish(hass, "event", {**base, "event_type": "play_blocked", "app_id": None, "blocked_by": "bedtime"})
    order = {"entity": "add_bonus_time", "payload": "30", "rc": None}
    publish(hass, "event", {**base, "event_type": "command_rejected", **order, "reason": "no_limit_today"})
    publish(hass, "event", {**base, "event_type": "command_applied", "entity": "sync_now", "payload": "PRESS"})
    publish(hass, "event", {**base, "event_type": "something_new"})
    await hass.async_block_till_done()
    assert len(events) == 5  # not the event type it does not know
    assert events[0].data["device_id"] == _device(hass, setup).id
    assert events[0].data["game"] == "Super Mario Odyssey"
    assert [describe(e) for e in events] == [
        {"name": "Salon", "message": "started Super Mario Odyssey"},
        {"name": "Salon", "message": "has 10 minutes of play left"},
        {"name": "Salon", "message": "blocked the games: bedtime"},
        {"name": "Salon", "message": "refused add_bonus_time: 30: there is no limit today"},
        {"name": "Salon", "message": f"carried out {hass.states.get('button.salon_sync_now').name}"},
    ]

    # The console gone (its entry unloaded): the event as it was.
    await hass.config_entries.async_unload(setup.entry_id)
    gone = describe(Event(EVENT_PLAYGUARD, {"console_id": CONSOLE_ID, "event_type": "new_thing"}))
    assert gone == {"name": "PlayGuard", "message": "new_thing"}


async def test_device_diagnostics(hass: HomeAssistant, setup) -> None:
    diagnostics = await async_get_device_diagnostics(hass, setup, _device(hass, setup))
    assert diagnostics["online"] is True and diagnostics["state"]["console"]["name"] == "**REDACTED**"
