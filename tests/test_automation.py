"""The console's triggers and conditions, in an automation."""

from __future__ import annotations

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import condition, device_registry as dr, entity_registry as er, trigger
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.playguard.const import DOMAIN

from .conftest import CONSOLE_ID, publish


def _id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


def _device_id(hass: HomeAssistant) -> str:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    assert device
    return device.id


async def _automation(hass: HomeAssistant, trigger: dict, conditions: list[dict] | None = None) -> list[ServiceCall]:
    calls = async_mock_service(hass, "test", "automation")
    config = {
        "triggers": [trigger],
        "conditions": conditions or [],
        "actions": [{"action": "test.automation", "data": {"event": "{{ trigger.to_state.attributes.event_type }}"}}],
    }
    assert await async_setup_component(hass, automation.DOMAIN, {automation.DOMAIN: config})
    await hass.async_block_till_done()
    return calls


def _event(hass: HomeAssistant, event_type: str, ts: int, **data) -> None:
    publish(hass, "event", {"schema": 1, "source": "agent", "ts": ts, "event_type": event_type, **data})


async def test_game_started(hass: HomeAssistant, setup) -> None:
    """The console's device as the target: its Events entity."""
    calls = await _automation(hass, {"trigger": "playguard.game_started", "target": {"device_id": _device_id(hass)}})
    _event(hass, "play_stopped", 1, app_id="0100000000010000")
    _event(hass, "play_started", 2, app_id="0100000000010000")
    await hass.async_block_till_done()
    assert [c.data["event"] for c in calls] == ["play_started"]


async def test_games_blocked(hass: HomeAssistant, setup) -> None:
    trigger = {
        "trigger": "playguard.games_blocked",
        "target": {"entity_id": _id(hass, "event", "events")},
        "options": {"blocked_by": ["bedtime"]},
    }
    calls = await _automation(hass, trigger)
    _event(hass, "play_blocked", 1, blocked_by="limit")
    await hass.async_block_till_done()
    _event(hass, "play_blocked", 2, blocked_by="bedtime")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_conditions(hass: HomeAssistant, setup, state) -> None:
    """A game is played (the fixture's state plays one), the limit is not
    reached, parental controls are on."""
    device = {"device_id": _device_id(hass)}
    conditions = [
        {"condition": "playguard.is_playing", "target": device, "options": {"behavior": "any"}},
        {"condition": "playguard.parental_controls_on", "target": device, "options": {"behavior": "any"}},
        {
            "condition": "not",
            "conditions": [{"condition": "playguard.limit_reached", "target": device, "options": {"behavior": "any"}}],
        },
    ]
    calls = await _automation(hass, {"trigger": "playguard.order_refused", "target": device}, conditions)
    _event(hass, "command_rejected", 1, entity="limit_mon", payload="5000", reason="out_of_range")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # No game played: not any more.
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    _event(hass, "command_rejected", 2, entity="limit_mon", payload="5000", reason="out_of_range")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_descriptions(hass: HomeAssistant, setup) -> None:
    """triggers.yaml and conditions.yaml are read (the automation editor's)."""
    assert await async_setup_component(hass, automation.DOMAIN, {})
    triggers = await trigger.async_get_all_descriptions(hass)
    conditions = await condition.async_get_all_descriptions(hass)
    for key in ("game_started", "game_stopped", "time_running_out", "games_blocked", "order_refused"):
        assert triggers[f"{DOMAIN}.{key}"]["target"], key
    assert triggers[f"{DOMAIN}.games_blocked"]["fields"]["blocked_by"]["default"] == ["limit", "bedtime"]
    for key in ("is_playing", "limit_reached", "parental_controls_on"):
        assert conditions[f"{DOMAIN}.{key}"]["fields"]["behavior"], key
