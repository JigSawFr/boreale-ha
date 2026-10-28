"""What the console is doing, the homebrews' counts and their play time
(PlayGuard 1.5 lists games only)."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.playguard.const import DOMAIN

from .conftest import CONSOLE_ID, fixture, publish


def _id(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


async def _now(hass: HomeAssistant, state: dict, now: object, **today: object) -> object:
    state["activity_today"] = {**state["activity_today"], "now": now, **today}
    publish(hass, "state", state)
    await hass.async_block_till_done()
    return hass.states.get(_id(hass, "console_activity"))


async def test_activity(hass: HomeAssistant, setup, state) -> None:
    # An older PlayGuard (no "now"): the fixture plays a game, published by the app.
    activity = hass.states.get(_id(hass, "console_activity"))
    assert activity.state == "game" and activity.attributes["title"] == "Super Mario Odyssey"
    assert activity.attributes["options"] == ["game", "homebrew", "playguard", "home", "suspended", "offline"]

    homebrew = {"app_id": "050537E2542E2000", "name": "sphaira", "kind": "homebrew", "since": 1}
    activity = await _now(hass, state, "homebrew", now_playing=homebrew)
    assert activity.state == "homebrew" and activity.attributes["title"] == "sphaira"
    activity = await _now(hass, state, "home", now_playing=None)
    assert activity.state == "home" and activity.attributes["title"] is None
    assert (await _now(hass, state, "suspended")).state == "suspended"
    assert (await _now(hass, state, None)).state == STATE_UNKNOWN  # play time not published

    # An older PlayGuard, nothing played: PlayGuard publishing, else the agent on the HOME menu.
    del state["activity_today"]["now"]
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "console_activity")).state == "playguard"
    state["source"] = "agent"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "console_activity")).state == "home"

    # Off the broker: offline, shown all the same.
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "console_activity")).state == "offline"


async def test_homebrews(hass: HomeAssistant, setup, state) -> None:
    games = fixture("games.json") | {"homebrews": 23, "forwarders": 4, "homebrew_min": 640}
    publish(hass, "games", games)
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "homebrews")).state == "23"
    assert hass.states.get(_id(hass, "forwarders")).state == "4"

    # Their play time: today's, and the week's each day, with the games'.
    activity = fixture("activity.json") | {"local_date": "2026-10-04", "homebrew_min": 10}
    activity["per_app"] = [{"app_id": "0100000000010000", "min": 70}]
    publish(hass, "activity", activity)
    week = {"schema": 1, "ts": 1, "days": ["2026-10-03", "2026-10-04"], "games": [], "homebrew_min": [20, 5]}
    publish(hass, "week", week)
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "used_screen_time_log")).attributes["homebrew"] == 10
    sensor = hass.states.get(_id(hass, "week_play_time"))
    assert sensor.attributes["days"] == {"2026-10-03": 20, "2026-10-04": 80}  # 70 + 10 (today's is more)
    assert sensor.attributes["homebrew"] == 30

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    response = await hass.services.async_call(
        DOMAIN, "get_play_time", {"device_id": device.id, "period": "week"}, blocking=True, return_response=True
    )
    assert response["homebrew_minutes"] == 30 and response["minutes"] == 100
    state["activity_today"]["now"] = "game"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    today = await hass.services.async_call(
        DOMAIN, "get_play_time", {"device_id": device.id}, blocking=True, return_response=True
    )
    assert today["homebrew_minutes"] == 10 and today["activity"] == "game"
