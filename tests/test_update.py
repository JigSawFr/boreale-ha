"""PlayGuard's version against its latest release."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION, ATTR_RELEASE_URL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boreale.const import DOMAIN
from custom_components.boreale.update import RELEASES, async_latest_release

from .conftest import CONSOLE_ID, fixture, publish


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


def _system_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


async def test_system_updates(hass: HomeAssistant, setup, state, latest_release) -> None:
    """The system's versions against what the agent's checks found."""
    system = fixture("system.json")
    system["latest"] = {
        "checked": 1790990000,
        "firmware": "23.1.0",
        "atmosphere": "1.12.0",
        "hekate": "v6.6.0",
        "syspatch": "1.5.5",
        "integration": "v99.0.0",
    }
    publish(hass, "system", system)
    await hass.async_block_till_done()

    firmware = hass.states.get(_system_id(hass, "update", "firmware_update"))
    assert firmware.state == STATE_ON
    assert firmware.attributes[ATTR_INSTALLED_VERSION] == "23.0.1"
    assert firmware.attributes[ATTR_LATEST_VERSION] == "23.1.0"
    assert hass.states.get(_system_id(hass, "update", "atmosphere_update")).state == STATE_OFF
    hekate = hass.states.get(_system_id(hass, "update", "hekate_update"))
    assert hekate.state == STATE_ON and hekate.attributes[ATTR_LATEST_VERSION] == "6.6.0"
    integration = hass.states.get(_system_id(hass, "update", "integration_update"))
    assert integration.state == STATE_ON and integration.attributes[ATTR_LATEST_VERSION] == "99.0.0"
    assert integration.attributes[ATTR_INSTALLED_VERSION] == "0.10.0"

    # The checks off (no `latest` block): the newest is unknown, not "up to date".
    del system["latest"]
    publish(hass, "system", system)
    await hass.async_block_till_done()
    assert hass.states.get(_system_id(hass, "update", "firmware_update")).state == STATE_UNKNOWN
    assert hass.states.get(_system_id(hass, "update", "integration_update")).state == STATE_UNKNOWN


async def test_clock_drift(hass: HomeAssistant, setup) -> None:
    """The console's clocks against a time server (the `clock` block)."""
    system = fixture("system.json")
    system["clock"] = {"checked": 1790990000, "network_drift_s": -3, "user_drift_s": 125, "server": "pool.ntp.org"}
    publish(hass, "system", system)
    await hass.async_block_till_done()
    network = hass.states.get(_system_id(hass, "sensor", "clock_network_drift"))
    assert network.state == "-3" and network.attributes["unit_of_measurement"] == "s"
    assert hass.states.get(_system_id(hass, "sensor", "clock_user_drift")).state == "125"

    # Not measured yet (null): unknown, not zero.
    system["clock"] = {"checked": None, "network_drift_s": None, "user_drift_s": None, "server": None}
    publish(hass, "system", system)
    await hass.async_block_till_done()
    assert hass.states.get(_system_id(hass, "sensor", "clock_network_drift")).state == STATE_UNKNOWN
