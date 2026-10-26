"""When play ends, and each account's play time."""

from __future__ import annotations

import copy

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.playguard.const import DOMAIN

from .conftest import CONSOLE_ID, fixture, publish

LEA, TOM = "00112233445566778899AABBCCDDEEFF", "FFEEDDCCBBAA99887766554433221100"


def _id(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


async def _state(hass: HomeAssistant, state: dict, **timer) -> None:
    doc = copy.deepcopy(state)
    doc["timer"].update(timer)
    publish(hass, "state", doc)
    await hass.async_block_till_done()


async def test_play_ends(hass: HomeAssistant, setup, state: dict) -> None:
    """The state's time is 06:00 in Paris, 45 minutes left, bedtime at 21:30."""
    await hass.config.async_set_time_zone("Europe/Paris")
    ends = _id(hass, "play_ends")

    await _state(hass, state)
    assert hass.states.get(ends).state == "2026-10-03T04:45:00+00:00"  # 06:45 in Paris
    assert hass.states.get(ends).attributes["ends_by"] == "limit"

    await _state(hass, state, remaining_min=1000)  # bedtime comes first
    assert hass.states.get(ends).state == "2026-10-03T19:30:00+00:00"
    assert hass.states.get(ends).attributes["ends_by"] == "bedtime"

    await _state(hass, state, limit_today_min=1440, bedtime={"enabled": True, "start": "05:00:00", "end": "06:00:00"})
    assert hass.states.get(ends).state == "2026-10-04T03:00:00+00:00"  # no limit; bedtime tomorrow

    for timer in (
        {"limit_reached": True},  # already blocked
        {"limit_today_min": 1440, "bedtime": {"enabled": False, "start": None, "end": None}},  # nothing ends it
        {"supported": False},
        {"enabled": False},  # the play timer off: its bedtime does not block either
    ):
        await _state(hass, state, **timer)
        assert hass.states.get(ends).state == STATE_UNKNOWN, timer
        assert hass.states.get(ends).attributes["ends_by"] is None

    doc = copy.deepcopy(state)
    doc["activity_today"]["now_playing"] = None  # PlayGuard in front: nobody plays
    publish(hass, "state", doc)
    await hass.async_block_till_done()
    assert hass.states.get(ends).state == STATE_UNKNOWN

    doc = copy.deepcopy(state)
    doc["ts"] = None  # no time of its own: when it was last seen
    publish(hass, "state", doc)
    await hass.async_block_till_done()
    assert hass.states.get(ends).state != STATE_UNKNOWN


async def test_accounts(hass: HomeAssistant, setup) -> None:
    names = {"games": {"0100000000010000": "Super Mario Odyssey"}, "accounts": {LEA: "Léa"}}
    publish(hass, "names", {"schema": 1, "ts": 1, **names})
    today = _id(hass, "used_screen_time_log")
    week = _id(hass, "week_play_time")
    await hass.async_block_till_done()
    assert hass.states.get(today).attributes["accounts"] is None  # the agent does not read them

    activity = fixture("activity.json")
    activity["per_account"] = [
        {"uid": TOM, "s": 600, "min": 10},
        {"uid": LEA, "s": 3840, "min": 64},
        {"uid": 7, "min": 1},
        {"uid": LEA.lower(), "min": "x"},
        "junk",
    ]
    publish(hass, "activity", activity)
    publish(
        hass,
        "week",
        {
            "schema": 1,
            "ts": 1,
            "days": ["2026-10-03", "2026-10-04"],
            "games": [{"app_id": "0100000000010000", "min": [30, 60]}],
            "accounts": [{"uid": LEA, "min": [30, 45]}, {"uid": TOM, "min": [0, 15, "x"]}],
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(today).attributes["accounts"] == {"Léa": 64, TOM: 10}  # by name, else by id
    # The table's two days, and today's log (5 October) on the third.
    assert hass.states.get(week).attributes["accounts"] == {"Léa": 30 + 45 + 64, TOM: 15 + 10}

    # The agent's finished day says it too: no table needed.
    final = fixture("activity.json") | {"local_date": "2026-10-04", "final": True}
    final["per_account"] = [{"uid": LEA, "min": 50}]
    publish(hass, "activity/2026-10-04", final)
    publish(hass, "week", {"schema": 1, "ts": 2, "days": ["2026-10-04"], "games": []})
    await hass.async_block_till_done()
    assert hass.states.get(week).attributes["accounts"] == {"Léa": 50 + 64, TOM: 10}
