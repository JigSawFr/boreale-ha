"""What PlayGuard publishes and how the console shows: the lock, why games
are blocked, the profile in effect, the device as Nintendo names it, when
the console last spoke, the entities of what is not published, and the
entities 0.4 had that the lock replaced."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.playguard.const import CONF_UNPUBLISHED, DOMAIN

from .conftest import BASE, CONSOLE_ID, fixture, publish


def _id(hass: HomeAssistant, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")


def _state(hass: HomeAssistant, platform: str, key: str) -> Any:
    entity_id = _id(hass, platform, key)
    assert entity_id, key
    return hass.states.get(entity_id)


def _published(mqtt_mock: Any) -> list[tuple[Any, ...]]:
    return [c.args for c in mqtt_mock.async_publish.call_args_list]


async def test_the_lock(hass: HomeAssistant, setup: MockConfigEntry, mqtt_mock: Any, state: dict[str, Any]) -> None:
    """Locked while parental controls are set up and not unlocked for now."""
    assert _state(hass, "lock", "parental_controls").state == "locked"
    state["controls"]["temp_unlocked"] = True
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "lock", "parental_controls").state == "unlocked"
    state["controls"]["temp_unlocked"] = False
    state["controls"]["enabled"] = False  # nothing to lock
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "lock", "parental_controls").state == "unlocked"
    state["controls"]["enabled"] = None  # not read
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "lock", "parental_controls").state == STATE_UNKNOWN

    lock = _id(hass, "lock", "parental_controls")
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call("lock", "unlock", {"entity_id": lock}, blocking=True)
    await hass.services.async_call("lock", "lock", {"entity_id": lock}, blocking=True)
    assert _published(mqtt_mock) == [
        (f"{BASE}/parental_controls/set", "UNLOCK", 1, True),
        (f"{BASE}/parental_controls/set", "LOCK", 1, True),
    ]


async def test_why_games_are_blocked(hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any]) -> None:
    blocked = _state(hass, "binary_sensor", "limit_reached")
    assert blocked.state == STATE_OFF and blocked.attributes["reason"] is None
    state["timer"]["limit_reached"] = True
    state["timer"]["blocked_by"] = "bedtime"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    blocked = _state(hass, "binary_sensor", "limit_reached")
    assert blocked.state == STATE_ON and blocked.attributes["reason"] == "bedtime"
    state["timer"]["blocked_by"] = "something new"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", "limit_reached").attributes["reason"] is None


async def test_the_profile_in_effect(hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any]) -> None:
    assert _state(hass, "select", "profile").state == STATE_UNKNOWN
    state["timer"]["profile"] = "Holidays"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "select", "profile").state == "Holidays"
    state["timer"]["profile"] = "Deleted since"  # not among the profiles
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _state(hass, "select", "profile").state == STATE_UNKNOWN


async def test_the_device_is_the_console(hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any]) -> None:
    """Nintendo's: the model from the system document, the system as the software."""
    publish(hass, "system", fixture("system.json"), retain=True)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    assert device.manufacturer == "Nintendo"
    assert (device.model, device.model_id) == ("Nintendo Switch – OLED Model", "HEG-001")
    assert device.sw_version == "23.0.1 · Atmosphère 1.12.0"
    # Without Atmosphère's version: the firmware alone.
    system = fixture("system.json")
    system["versions"]["atmosphere"] = None
    system["hardware"]["model"] = "other"
    state["console"]["atmosphere"] = None
    publish(hass, "state", state)
    publish(hass, "system", system)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    assert (device.model, device.model_id, device.sw_version) == ("Nintendo Switch", None, "23.0.1")


async def test_last_seen(
    hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """A retained document may be hours old: the state's own time then. A
    live one is now. Shown while the console sleeps."""
    seen = _state(hass, "sensor", "last_seen")
    assert seen.state == datetime.fromtimestamp(state["ts"], UTC).isoformat()
    freezer.move_to("2026-10-26 08:00:00+00:00")
    publish(hass, "names", {"schema": 1, "ts": 2, "games": {}})
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "last_seen").state == "2026-10-26T08:00:00+00:00"
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "last_seen").state == "2026-10-26T08:00:00+00:00"
    freezer.move_to("2026-10-26 09:00:00+00:00")
    for sub, doc in (("availability", "online"), ("system", fixture("system.json")), ("week", {"days": []})):
        publish(hass, sub, doc)
    publish(hass, "event", {"schema": 1, "event_type": "command_applied", "entity": "sync_now"})
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "last_seen").state == "2026-10-26T09:00:00+00:00"


async def test_last_seen_before_any_state(hass: HomeAssistant, mqtt_mock: Any, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(_id(hass, "sensor", "last_seen")).state == "unavailable"


async def test_what_is_not_published(hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any]) -> None:
    """Its entities go; back on, the entry reloads and they come back."""
    assert _id(hass, "sensor", "ip_address") and _id(hass, "sensor", "serial")
    state["link"]["publishes"]["network"] = False
    state["link"]["publishes"]["hardware"] = False  # the serial number goes with it
    publish(hass, "state", state)
    await hass.async_block_till_done()
    for platform, key in (("sensor", "ip_address"), ("sensor", "ssid"), ("sensor", "model"), ("sensor", "serial")):
        assert _id(hass, platform, key) is None, key
    assert _id(hass, "sensor", "battery") and _id(hass, "lock", "parental_controls")
    assert setup.data[CONF_UNPUBLISHED] == ["hardware", "network", "serial"]

    # The same again: nothing changes (an entity turned on by hand meanwhile goes too).
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, f"{CONSOLE_ID}_ssid", config_entry=setup)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        publish(hass, "state", state)
        await hass.async_block_till_done()
    reload.assert_not_called()
    assert _id(hass, "sensor", "ssid") is None

    # The network back: the entry reloads, its entities come back; the rest stays off.
    state["link"]["publishes"]["network"] = True
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert setup.state is ConfigEntryState.LOADED
    publish(hass, "state", state, retain=True)
    await hass.async_block_till_done()
    assert _id(hass, "sensor", "ip_address") is not None
    assert _id(hass, "sensor", "model") is None and setup.data[CONF_UNPUBLISHED] == ["hardware", "serial"]


async def test_older_playguard_publishes_everything(
    hass: HomeAssistant, setup: MockConfigEntry, state: dict[str, Any]
) -> None:
    """Without link.publishes (an older PlayGuard), nothing is removed."""
    del state["link"]["publishes"]
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert _id(hass, "sensor", "ip_address") and _id(hass, "sensor", "serial")
    assert CONF_UNPUBLISHED not in setup.data


async def test_not_created_when_not_published(hass: HomeAssistant, mqtt_mock: Any, entry: MockConfigEntry) -> None:
    """What the last state said is off is not created at the next start."""
    known = MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={**entry.data, CONF_UNPUBLISHED: ["games"]},
        options=dict(entry.options),
        minor_version=3,
    )
    known.add_to_hass(hass)
    assert await hass.config_entries.async_setup(known.entry_id)
    await hass.async_block_till_done()
    assert _id(hass, "sensor", "games_installed") is None
    assert _id(hass, "sensor", "battery") is not None


async def test_the_lock_replaces_three_entities(hass: HomeAssistant, mqtt_mock: Any, entry: MockConfigEntry) -> None:
    """An entry from 0.4 (1.2): Unlocked, Turn parental controls back on and
    Temporarily unlocked leave the registry; the rest stays."""
    old = MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data=dict(entry.data),
        options=dict(entry.options),
        minor_version=2,
    )
    old.add_to_hass(hass)
    registry = er.async_get(hass)
    gone = [
        registry.async_get_or_create(platform, DOMAIN, f"{CONSOLE_ID}_{key}", config_entry=old)
        for platform, key in (("switch", "unlocked"), ("button", "lock_now"), ("binary_sensor", "temp_unlocked"))
    ]
    kept = registry.async_get_or_create("switch", DOMAIN, f"{CONSOLE_ID}_console_lock", config_entry=old)
    # A sensor whose id only looks like a game's (none exist since 1.2) is not touched.
    game = registry.async_get_or_create("sensor", DOMAIN, f"{CONSOLE_ID}_game_0100000000010000", config_entry=old)
    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()
    assert old.minor_version == 3
    for reg in gone:
        assert registry.async_get(reg.entity_id) is None, reg.entity_id
    assert registry.async_get(kept.entity_id) is not None
    assert registry.async_get(game.entity_id) is not None
