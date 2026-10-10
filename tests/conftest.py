"""Fixtures: a console on a mocked broker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.playguard.const import CONF_CONSOLE_ID, CONF_PREFIX, CONF_TAKE_OVER, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES = Path(__file__).parent / "fixtures"
CONSOLE_ID = "a1b2c3d4"  # the id in PlayGuard's state example
BASE = f"playguard/{CONSOLE_ID}"


def fixture(name: str) -> Any:
    """A JSON file of tests/fixtures (PlayGuard's own examples)."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Loads custom_components/."""


@pytest.fixture
def state() -> dict:
    """PlayGuard's example state, orders allowed to change the timer, with profiles."""
    doc = fixture("state.json")
    doc["link"]["remote_timer_writes"] = True
    doc["profiles"] = ["School week", "Holidays"]
    return doc


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"},
        options={CONF_TAKE_OVER: True},
    )


def publish(hass: HomeAssistant, sub: str, doc: Any, retain: bool = False) -> None:
    """The console publishes `doc` on its topic `sub`. A broker hands a retained
    message over with the retain flag only to a new subscription (Home
    Assistant's client takes one per topic): live ones come without it."""
    payload = doc if isinstance(doc, str) else json.dumps(doc)
    async_fire_mqtt_message(hass, f"{BASE}/{sub}", payload, retain=retain)


@pytest.fixture
async def setup(hass: HomeAssistant, mqtt_mock, entry: MockConfigEntry, state: dict):
    """The integration set up, the console online with its state and activity."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    publish(hass, "availability", "online", retain=True)
    publish(hass, "state", state, retain=True)
    publish(hass, "activity", fixture("activity.json"), retain=True)
    names = {"0100000000010000": "Super Mario Odyssey", "01000A10041EA000": "Mario Kart 8 Deluxe"}
    publish(hass, "names", {"schema": 1, "ts": 1, "games": names}, retain=True)
    await hass.async_block_till_done()
    return entry
