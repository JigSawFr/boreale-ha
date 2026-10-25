"""The console itself (the system document) and its games: the totals, and
one sensor per game."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.playguard.const import DOMAIN

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
    assert sd.state == "21344" and sd.attributes["unit_of_measurement"] == "MiB"
    assert _state(hass, "sensor", "nand_total").state == "26592"
    assert _state(hass, "binary_sensor", "charging").state == STATE_ON
    assert _state(hass, "binary_sensor", "docked").state == STATE_OFF
    assert _state(hass, "sensor", "temperature").state == "41"
    assert _state(hass, "sensor", "network").state == "wifi"
    assert _state(hass, "sensor", "ip_address").state == "192.168.1.20"
    assert _state(hass, "sensor", "wifi_signal").state == "3"
    assert _state(hass, "sensor", "last_boot").state == "2026-10-02T20:13:00+00:00"

    # The serial number and the Wi-Fi network's name: off until wanted.
    registry = er.async_get(hass)
    for key in ("serial", "ssid"):
        assert registry.async_get(_id(hass, "sensor", key)).disabled_by is er.RegistryEntryDisabler.INTEGRATION

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

    # Offline: its entities go with the console's.
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "sd_free").state == STATE_UNAVAILABLE


async def test_games(hass: HomeAssistant, setup) -> None:
    assert _state(hass, "sensor", "games_installed").state == STATE_UNAVAILABLE
    publish(hass, "games", fixture("games.json"), retain=True)
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "games_installed").state == "2"
    total = _state(hass, "sensor", "play_time_total")
    assert total.state == "2400" and total.attributes["state_class"] == "total_increasing"
    assert _state(hass, "sensor", "accounts").state == "3"

    # One sensor per game, uninstalled ones too.
    odyssey = _state(hass, "sensor", "game_0100000000010000")
    assert odyssey.state == "1234"
    assert odyssey.name == "Salon Play time · Super Mario Odyssey"
    assert odyssey.attributes["unit_of_measurement"] == "min"
    assert odyssey.attributes["installed"] is True and odyssey.attributes["version"] == "1.3.0"
    assert odyssey.attributes["launches"] == 56
    assert odyssey.attributes["first_played"] == "2023-11-14T22:13:20+00:00"
    assert odyssey.attributes["last_played"] == "2026-09-21T14:13:20+00:00"
    xeno = _state(hass, "sensor", "game_0100e95004038000")
    assert xeno.state == "186" and xeno.attributes["installed"] is False and xeno.attributes["version"] is None

    # A new game: its sensor appears; one no longer listed keeps its sensor, unavailable.
    doc = fixture("games.json")
    del doc["games"]["0100E95004038000"]
    doc["games"]["0100F8F0000A2000"] = {
        "name": "Splatoon 3",
        "version": "9.1.0",
        "installed": True,
        "total_min": 12,
        "launches": None,
        "first_played": None,
        "last_played": None,
    }
    publish(hass, "games", doc)
    await hass.async_block_till_done()
    splatoon = _state(hass, "sensor", "game_0100f8f0000a2000")
    assert splatoon.state == "12" and splatoon.attributes["first_played"] is None
    assert splatoon.attributes["launches"] is None
    assert _state(hass, "sensor", "game_0100e95004038000").state == STATE_UNAVAILABLE

    # A document that is not one: no game, nothing breaks.
    publish(hass, "games", {"schema": 1, "games": ["not", "a", "table"]})
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "game_0100000000010000").state == STATE_UNAVAILABLE
