"""PlayGuard: a Nintendo Switch's parental controls, through MQTT.

PlayGuard (https://github.com/JigSawFr/PlayGuard) publishes the console's
state, play time and events on an MQTT broker and takes orders from it. This
integration finds the consoles on the broker by itself, replaces the
console's own Home Assistant discovery with the same entities, adds game names,
the week's play time and long-term statistics, and offers services.
"""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PlayGuardConsole
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PlayGuardConfigEntry = ConfigEntry[PlayGuardConsole]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The services, once for every console."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> bool:
    """One console."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="mqtt_not_ready")
    console = PlayGuardConsole(hass, entry)
    entry.runtime_data = console
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Undone on unload, and when a subscription fails half way.
    entry.async_on_unload(console.async_stop)
    # After the platforms: the retained documents arrive at once.
    await console.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> None:
    """The console's own discovery comes back when the integration goes, and
    the console forgets the integration's version."""
    if not mqtt.mqtt_config_entry_enabled(hass):
        return
    console = PlayGuardConsole(hass, entry)
    try:
        await console.async_send("discovery", "ON")
        await console.async_clear_version()
    except (HomeAssistantError, KeyError) as err:  # KeyError: MQTT never set up
        _LOGGER.warning("%s: the console's own discovery could not be turned back on: %r", console.base, err)
