"""PlayGuard's version against its latest release."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION, ATTR_RELEASE_URL
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boreale.const import DOMAIN
from custom_components.boreale.update import RELEASES, async_latest_release

from .conftest import CONSOLE_ID, publish


def _id(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("update", DOMAIN, f"{CONSOLE_ID}_playguard_update")
    assert entity_id
    return entity_id


async def test_update(hass: HomeAssistant, setup, state, latest_release, freezer: FrozenDateTimeFactory) -> None:
    """The fixture's PlayGuard (1.1.0) is behind the latest release (1.4.0)."""
    await hass.async_block_till_done()
    update = hass.states.get(_id(hass))
    assert update.state == STATE_ON
    assert update.attributes[ATTR_INSTALLED_VERSION] == "1.1.0"
    assert update.attributes[ATTR_LATEST_VERSION] == "1.4.0"
    assert update.attributes[ATTR_RELEASE_URL].endswith("/v1.4.0")
    entity = hass.data["entity_components"]["update"].get_entity(_id(hass))
    assert await entity.async_release_notes() == "## What changed"
    assert entity.release_summary == "PlayGuard 1.4.0"
    assert latest_release.call_count == 1

    # Read again with the console's documents, once six hours have passed.
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert latest_release.call_count == 1
    freezer.tick(timedelta(hours=7))
    latest_release.return_value = None  # GitHub out of reach: the last release read stays
    state["console"]["app_version"] = "1.4.0"
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert latest_release.call_count == 2
    update = hass.states.get(_id(hass))
    assert update.state == STATE_OFF and update.attributes[ATTR_LATEST_VERSION] == "1.4.0"


async def test_no_release_yet(hass: HomeAssistant, setup, state, latest_release) -> None:
    """Nothing read yet: up to date, not "update available"."""
    latest_release.return_value = None
    entity = hass.data["entity_components"]["update"].get_entity(_id(hass))
    entity._release = None
    assert entity.latest_version == "1.1.0"
    assert entity.release_url is None and entity.release_summary is None
    assert await entity.async_release_notes() is None
    state["console"]["app_version"] = None
    state["console"]["agent_version"] = None
    publish(hass, "state", state)
    await hass.async_block_till_done()
    assert entity.installed_version is None


async def test_latest_release(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(RELEASES, json={"tag_name": "v1.5.0"})
    assert await async_latest_release(hass) == {"tag_name": "v1.5.0"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(RELEASES, json=["not", "a", "release"])
    assert await async_latest_release(hass) is None
    aioclient_mock.clear_requests()
    aioclient_mock.get(RELEASES, status=403)
    assert await async_latest_release(hass) is None
