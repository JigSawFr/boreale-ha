"""The calendar of play sessions."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.playguard.calendar import sessions
from custom_components.playguard.const import DOMAIN

from .conftest import CONSOLE_ID, publish

T = datetime(2026, 10, 3, 14, 0, tzinfo=dt_util.UTC)


def _state(entity_id: str, state: str, minutes: int) -> State:
    when = T + timedelta(minutes=minutes)
    return State(entity_id, state, last_changed=when, last_updated=when)


def test_sessions() -> None:
    """A game while online, cut by another game, by sleep and by nothing played."""
    playing, online = "sensor.playing", "binary_sensor.online"
    history = {
        playing: [
            _state(playing, "unknown", 0),
            _state(playing, "Mario", 10),
            _state(playing, "Zelda", 40),  # straight from one game to another
            _state(playing, "unknown", 70),
            _state(playing, "Kart", 80),  # still shown while it sleeps
        ],
        online: [_state(online, "on", 0), _state(online, "off", 90), _state(online, "on", 120)],
    }
    found = sessions(history, playing, online, T + timedelta(minutes=150))
    assert [(e.summary, e.start, e.end) for e in found] == [
        ("Mario", T + timedelta(minutes=10), T + timedelta(minutes=40)),
        ("Zelda", T + timedelta(minutes=40), T + timedelta(minutes=70)),
        ("Kart", T + timedelta(minutes=80), T + timedelta(minutes=90)),
        ("Kart", T + timedelta(minutes=120), T + timedelta(minutes=150)),  # awake again, not over
    ]
    # Without Online's history (turned off): online all along.
    assert len(sessions({playing: history[playing]}, playing, online, T + timedelta(minutes=150))) == 3
    assert sessions({}, playing, None, T) == []


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock: Recorder, enable_custom_integrations: None) -> None:
    """The recorder first: it must start before Home Assistant does."""


async def test_calendar(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, state: dict) -> None:
    calendar = er.async_get(hass).async_get_entity_id("calendar", DOMAIN, f"{CONSOLE_ID}_play_sessions")
    assert calendar
    start = dt_util.utcnow()

    doc = dict(state)
    doc["activity_today"] = {"now_playing": None}
    publish(hass, "state", doc)
    await hass.async_block_till_done()
    assert hass.states.get(calendar).state == "off"  # nothing played

    freezer.tick(timedelta(minutes=5))
    publish(hass, "state", state)  # the fixture plays Super Mario Odyssey
    await hass.async_block_till_done()
    current = hass.states.get(calendar)
    assert current.state == "on" and current.attributes["message"] == "Super Mario Odyssey"

    freezer.tick(timedelta(minutes=30))
    publish(hass, "state", doc)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": calendar, "start_date_time": start - timedelta(hours=1), "end_date_time": dt_util.utcnow()},
        blocking=True,
        return_response=True,
    )
    [event] = events[calendar]["events"]
    assert event["summary"] == "Super Mario Odyssey"
    assert dt_util.parse_datetime(event["end"]) - dt_util.parse_datetime(event["start"]) == timedelta(minutes=30)
