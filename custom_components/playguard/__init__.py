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
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONSOLE_ID, DOMAIN, RETIRED
from .coordinator import PlayGuardConsole
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.UPDATE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PlayGuardConfigEntry = ConfigEntry[PlayGuardConsole]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The services, once for every console."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> bool:
    """1.1 to 1.2: no sensor per game any more, nor its option. Each game stays
    on Games installed (its games attribute) and in the statistics.
    1.2 to 1.3: the lock Parental controls replaces the switch Unlocked, the
    button Turn parental controls back on and the binary sensor Temporarily
    unlocked. (An entry from a newer integration, Home Assistant refuses
    before asking.)"""
    registry = er.async_get(hass)
    console_id = entry.data[CONF_CONSOLE_ID]
    retired = {f"{console_id}_{key}": platform for platform, key in RETIRED}
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        game = entry.minor_version < 2 and reg.unique_id.startswith(f"{console_id}_game_")
        if (game and reg.domain == Platform.SENSOR) or retired.get(reg.unique_id) == reg.domain:
            registry.async_remove(reg.entity_id)
    options = {k: v for k, v in entry.options.items() if k != "game_sensors"}
    hass.config_entries.async_update_entry(entry, options=options, minor_version=3)
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
