"""The play time as an action's response, the intents, and the LLM tools."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, intent
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext
from homeassistant.setup import async_setup_component
import pytest

from custom_components.boreale import llm
from custom_components.boreale.const import DOMAIN
from custom_components.boreale.intent import INTENT_ADD_TIME, INTENT_PLAY_TIME, INTENT_STOP_TODAY

from .conftest import BASE, CONSOLE_ID, fixture, publish


def _device_id(hass: HomeAssistant) -> str:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    assert device
    return device.id


async def test_play_time_today(hass: HomeAssistant, setup) -> None:
    today = await hass.services.async_call(
        DOMAIN, "get_play_time", {"device_id": _device_id(hass)}, blocking=True, return_response=True
    )
    activity = fixture("activity.json")
    assert today["console"] == "Salon"
    assert today["date"] == activity["local_date"] and today["minutes"] == activity["total_min"]
    assert today["games"][0]["minutes"] >= today["games"][-1]["minutes"]
    assert today["now_playing"]["name"] == "Super Mario Odyssey"
    assert today["limit_minutes"] == 120 and today["remaining_minutes"] == 45 and today["extra_minutes"] == 30
    assert today["blocked"] is False


async def test_play_time_week(hass: HomeAssistant, setup) -> None:
    activity = fixture("activity.json")
    activity["local_date"] = "2026-10-04"
    activity["per_app"] = [{"app_id": "0100000000010000", "min": 70}, {"app_id": "01000A10041EA000", "min": 5}]
    publish(hass, "activity", activity)
    await hass.async_block_till_done()
    week = await hass.services.async_call(
        DOMAIN, "get_play_time", {"device_id": _device_id(hass), "period": "week"}, blocking=True, return_response=True
    )
    assert [d["date"] for d in week["days"]][-1] == "2026-10-04"
    assert week["minutes"] == 75
    assert week["games"][0] == {
        "app_id": "0100000000010000",
        "name": "Super Mario Odyssey",
        "minutes": 70,
        "per_day": [0, 0, 0, 0, 0, 0, 70],
    }


async def _intent(hass: HomeAssistant, intent_type: str, slots: dict | None = None) -> intent.IntentResponse:
    assert await async_setup_component(hass, "intent", {})
    return await intent.async_handle(
        hass, "test", intent_type, {k: {"value": v} for k, v in (slots or {}).items()}, language="en"
    )


async def test_intent_play_time(hass: HomeAssistant, setup) -> None:
    response = await _intent(hass, INTENT_PLAY_TIME)
    minutes = fixture("activity.json")["total_min"]
    assert response.speech["plain"]["speech"] == (
        f"Salon: {minutes} minutes played today. Super Mario Odyssey is being played. 45 minutes left."
    )
    assert response.speech_slots["remaining_minutes"] == 45


async def test_intent_play_time_no_limit_or_blocked(hass: HomeAssistant, setup, state) -> None:
    state["timer"]["limit_today_min"] = 1440
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    await hass.async_block_till_done()
    response = await _intent(hass, INTENT_PLAY_TIME, {"name": "salon"})
    assert response.speech["plain"]["speech"].endswith("There is no limit today.")
    state["timer"]["limit_reached"] = True
    publish(hass, "state", state)
    await hass.async_block_till_done()
    response = await _intent(hass, INTENT_PLAY_TIME)
    assert response.speech["plain"]["speech"].endswith("Games are blocked.")


async def test_intent_orders(hass: HomeAssistant, setup, mqtt_mock) -> None:
    mqtt_mock.async_publish.reset_mock()
    response = await _intent(hass, INTENT_ADD_TIME, {"minutes": "20"})
    assert response.speech["plain"]["speech"] == "20 minutes added today on Salon."
    response = await _intent(hass, INTENT_STOP_TODAY)
    assert response.speech["plain"]["speech"] == "No more play today on Salon."
    published = [c.args[:2] for c in mqtt_mock.async_publish.call_args_list]
    assert published == [(f"{BASE}/add_bonus_time/set", "20"), (f"{BASE}/stop_today/set", "PRESS")]

    with (
        patch(
            "custom_components.boreale.coordinator.PlayGuardConsole.async_order",
            side_effect=HomeAssistantError("refused"),
        ),
        pytest.raises(intent.IntentHandleError, match="refused"),
    ):
        await _intent(hass, INTENT_STOP_TODAY)


async def test_intent_which_console(hass: HomeAssistant, setup) -> None:
    with pytest.raises(intent.IntentHandleError, match="No PlayGuard console named Bedroom"):
        await _intent(hass, INTENT_PLAY_TIME, {"name": "Bedroom"})
    console = setup.runtime_data
    with (
        patch("custom_components.boreale.intent._consoles", return_value=[console, console]),
        pytest.raises(intent.IntentHandleError, match="Which console: Salon, Salon"),
    ):
        await _intent(hass, INTENT_PLAY_TIME)
    with (
        patch("custom_components.boreale.intent._consoles", return_value=[]),
        pytest.raises(intent.IntentHandleError, match="No PlayGuard console"),
    ):
        await _intent(hass, INTENT_PLAY_TIME)


async def test_llm_tools(hass: HomeAssistant, setup) -> None:
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    context = LLMContext(platform="test", context=None, language="en", assistant="conversation", device_id=None)
    assert llm.async_get_tools(hass, context, "other") is None
    registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(registry, setup.entry_id):
        async_expose_entity(hass, "conversation", entry.entity_id, False)
    assert llm.async_get_tools(hass, context, LLM_API_ASSIST) is None  # nothing of the console's exposed
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_now_playing")
    async_expose_entity(hass, "conversation", entity_id, True)
    tools = llm.async_get_tools(hass, context, LLM_API_ASSIST)
    assert sorted(t.name for t in tools.tools) == [
        f"{DOMAIN}__{INTENT_ADD_TIME}",
        f"{DOMAIN}__{INTENT_PLAY_TIME}",
        f"{DOMAIN}__{INTENT_STOP_TODAY}",
    ]
