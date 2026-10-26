"""The console itself (the system document) and its games: the totals and
the list (no sensor per game since 0.4)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.playguard.const import CONF_TAKE_OVER, DOMAIN

from .conftest import CONSOLE_ID, fixture, publish


def _id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


def _state(hass: HomeAssistant, platform: str, key: str):
    return hass.states.get(_id(hass, platform, key))


async def test_the_console_itself(hass: HomeAssistant, setup) -> None:
    # Before its document: unavailable (the state's entities are there).
    assert _state(hass, "sensor", "battery").state == STATE_UNAVAILABLE
    publish(hass, "system", fixture("system.json"), retain=True)
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "model").state == "oled"
    assert _state(hass, "sensor", "model").attributes["options"] == ["erista", "mariko", "lite", "oled", "other"]
    assert _state(hass, "sensor", "region").state == "eur"
    assert _state(hass, "sensor", "system_storage").state == "emummc"
    assert _state(hass, "sensor", "nickname").state == "Switch de Léa"
    assert _state(hass, "sensor", "hekate").state == "6.5.4"
    assert _state(hass, "binary_sensor", "prodinfo_blanked").state == STATE_ON
    battery = _state(hass, "sensor", "battery")
    assert battery.state == "87" and battery.attributes["device_class"] == "battery"
    sd = _state(hass, "sensor", "sd_free")
    # MiB from PlayGuard, shown in GiB (Home Assistant converts).
    assert sd.state == "20.84375" and sd.attributes["unit_of_measurement"] == "GiB"
    # Registered beforehand (the fixture turns it on): an existing entity
    # keeps its unit.
    assert _state(hass, "sensor", "nand_total").state == "26592"
    assert _state(hass, "binary_sensor", "charging").state == STATE_ON
    assert _state(hass, "binary_sensor", "docked").state == STATE_OFF
    assert _state(hass, "sensor", "temperature").state == "41"
    assert _state(hass, "sensor", "network").state == "wifi"
    assert _state(hass, "sensor", "ip_address").state == "192.168.1.20"
    assert _state(hass, "sensor", "wifi_signal").state == "3"
    assert _state(hass, "sensor", "last_boot").state == "2026-10-02T20:13:00+00:00"

    # What the console could not read is unknown; an option this
    # integration does not know too.
    doc = fixture("system.json")
    doc["hardware"]["model"] = "switch_3"
    doc["boot_ts"] = None
    doc["power"]["battery_pct"] = None
    publish(hass, "system", doc)
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "model").state == STATE_UNKNOWN
    assert _state(hass, "sensor", "last_boot").state == STATE_UNKNOWN
    assert _state(hass, "sensor", "battery").state == STATE_UNKNOWN

    # Offline: its sensors keep their last values (the option's default).
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "sd_free").state == "20.84375"


async def test_games(hass: HomeAssistant, setup) -> None:
    assert _state(hass, "sensor", "games_installed").state == STATE_UNAVAILABLE
    publish(hass, "games", fixture("games.json"), retain=True)
    await hass.async_block_till_done()
    installed = _state(hass, "sensor", "games_installed")
    assert installed.state == "2"
    # Every game the console lists, the last played first.
    assert [g["name"] for g in installed.attributes["games"]] == [
        "Super Mario Odyssey",
        "Mario Kart 8 Deluxe",
        "Xenoblade Chronicles 2",
    ]
    assert installed.attributes["games"][2] == {
        "app_id": "0100E95004038000",
        "name": "Xenoblade Chronicles 2",
        "minutes": 186,
        "installed": False,
        "last_played": "2024-10-27T03:33:20+00:00",
    }
    total = _state(hass, "sensor", "play_time_total")
    # Minutes from PlayGuard, shown in hours.
    assert total.state == "40.0" and total.attributes["state_class"] == "total_increasing"
    assert total.attributes["unit_of_measurement"] == "h"
    assert _state(hass, "sensor", "accounts").state == "3"

    # Xenoblade played again: first on the list. A new game never played,
    # last; none gets a sensor of its own.
    doc = fixture("games.json")
    doc["ts"] = 1793000000
    doc["games"]["0100E95004038000"]["last_played"] = 1792990000
    doc["games"]["0100F8F0000A2000"] = {
        "name": "Splatoon 3",
        "version": "9.1.0",
        "installed": True,
        "total_min": 0,
        "launches": None,
        "first_played": None,
        "last_played": None,
    }
    publish(hass, "games", doc)
    await hass.async_block_till_done()
    games = _state(hass, "sensor", "games_installed").attributes["games"]
    assert games[0]["name"] == "Xenoblade Chronicles 2"
    assert games[-1]["name"] == "Splatoon 3" and games[-1]["last_played"] is None and games[-1]["minutes"] == 0
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, setup.entry_id)
    assert not [e for e in entries if e.unique_id.startswith(f"{CONSOLE_ID}_game_")]

    # A document that is not one: no game, nothing breaks.
    publish(hass, "games", {"schema": 1, "games": ["not", "a", "table"]})
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "games_installed").attributes["games"] == []


async def test_game_sensors_go(hass: HomeAssistant, mqtt_mock, entry) -> None:
    """An entry from 0.3 or before (1.1): its sensors per game leave the
    registry, and their option the entry; the list and the rest stay."""
    old = MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data=dict(entry.data),
        options={**entry.options, "game_sensors": "all"},
        minor_version=1,
    )
    registry = er.async_get(hass)
    old.add_to_hass(hass)
    odyssey = registry.async_get_or_create("sensor", DOMAIN, f"{CONSOLE_ID}_game_0100000000010000", config_entry=old)
    installed = registry.async_get_or_create("sensor", DOMAIN, f"{CONSOLE_ID}_games_installed", config_entry=old)
    other = registry.async_get_or_create("sensor", DOMAIN, "0badc0de_game_0100000000010000")
    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()
    assert old.minor_version == 3 and "game_sensors" not in old.options
    assert old.options[CONF_TAKE_OVER] is True
    assert registry.async_get(odyssey.entity_id) is None
    assert registry.async_get(installed.entity_id) is not None
    assert registry.async_get(other.entity_id) is not None  # not this entry's
    publish(hass, "games", fixture("games.json"), retain=True)
    await hass.async_block_till_done()
    assert len(hass.states.get(installed.entity_id).attributes["games"]) == 3


async def test_newer_entry(hass: HomeAssistant, mqtt_mock, entry) -> None:
    """An entry a newer integration wrote (2.x): not set up, left as it is."""
    newer = MockConfigEntry(domain=DOMAIN, unique_id=CONSOLE_ID, data=dict(entry.data), version=2)
    newer.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(newer.entry_id)
    assert newer.state is ConfigEntryState.MIGRATION_ERROR
