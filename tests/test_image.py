"""The icon of the app in front."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.boreale.const import DOMAIN

from .conftest import BASE, CONSOLE_ID, publish

JPEG = b"\xff\xd8\xff\xe0 an icon"
PLAYED = "0100000000010000"  # the fixture's game being played


def _entity(hass: HomeAssistant):
    entity_id = er.async_get(hass).async_get_entity_id("image", DOMAIN, f"{CONSOLE_ID}_now_playing_icon")
    assert entity_id
    return entity_id, hass.data["entity_components"]["image"].get_entity(entity_id)


async def test_now_playing_icon(hass: HomeAssistant, setup, state) -> None:
    entity_id, entity = _entity(hass)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN  # no icon yet
    assert await entity.async_image() is None

    async_fire_mqtt_message(hass, f"{BASE}/icon/{PLAYED.lower()}", JPEG, retain=True)
    async_fire_mqtt_message(hass, f"{BASE}/icon/01000A10041EA000", b"\xff\xd8 another", retain=True)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNKNOWN
    assert await entity.async_image() == JPEG
    assert entity.content_type == "image/jpeg"

    # Another game: its icon.
    state["activity_today"]["now_playing"] = {"app_id": "01000A10041EA000", "since": 1}
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert await entity.async_image() == b"\xff\xd8 another"

    # Its icon cleared, then no game at all.
    async_fire_mqtt_message(hass, f"{BASE}/icon/01000A10041EA000", b"")  # live: not retained
    await hass.async_block_till_done()
    assert await entity.async_image() is None and hass.states.get(entity_id).state == STATE_UNKNOWN
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert await entity.async_image() is None


async def test_current_app_icon(hass: HomeAssistant, setup, state) -> None:
    """Any app's icon, a homebrew's too; Boréale's own in its applet; none for a system program."""
    entity_id, entity = _entity(hass)
    homebrew = "050537E2542E2000"
    async_fire_mqtt_message(hass, f"{BASE}/icon/{homebrew.lower()}", b"\xff\xd8 sphaira", retain=True)
    await hass.async_block_till_done()
    state["activity_today"]["now_playing"] = {"app_id": homebrew, "kind": "homebrew", "since": 1}
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert await entity.async_image() == b"\xff\xd8 sphaira" and entity.content_type == "image/jpeg"

    state["activity_today"]["now_playing"] = {"app_id": "0100000000001000", "kind": "system", "since": 2}
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert await entity.async_image() is None  # a system program has no icon

    state["activity_today"]["now_playing"] = None
    state["activity_today"]["now"] = "playguard"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert (await entity.async_image()).startswith(b"\x89PNG") and entity.content_type == "image/png"
    assert hass.states.get(entity_id).state != STATE_UNKNOWN

    state["activity_today"]["now"] = "home"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert await entity.async_image() is None and entity.content_type == "image/jpeg"


async def test_icons_not_published(hass: HomeAssistant, setup, state) -> None:
    state["link"]["publishes"]["icons"] = False
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get_entity_id("image", DOMAIN, f"{CONSOLE_ID}_now_playing_icon") is None
