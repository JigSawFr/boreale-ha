"""Boréale: the Boréale homebrews in Home Assistant, through MQTT (for now
PlayGuard, a Nintendo Switch's parental controls).

PlayGuard (https://github.com/JigSawFr/PlayGuard) publishes the console's
state, play time and events on an MQTT broker and takes orders from it. This
integration finds the consoles on the broker by itself, replaces the
console's own Home Assistant discovery with the same entities, adds game names,
the week's play time and long-term statistics, and offers services. It was
the integration "playguard" before Boréale: its entries are taken over.
"""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import CONF_CONSOLE_ID, CONF_IMPORTED, DOMAIN, LEGACY_DOMAIN, RETIRED
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
    _retire(hass, entry, entry.minor_version)
    hass.config_entries.async_update_entry(entry, minor_version=3)
    return True


def _retire(hass: HomeAssistant, entry: PlayGuardConfigEntry, minor_version: int) -> None:
    """What an entry of `minor_version` had and no longer has (see above)."""
    registry = er.async_get(hass)
    console_id = entry.data[CONF_CONSOLE_ID]
    retired = {f"{console_id}_{key}": platform for platform, key in RETIRED}
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        game = minor_version < 2 and reg.unique_id.startswith(f"{console_id}_game_")
        if (game and reg.domain == Platform.SENSOR) or retired.get(reg.unique_id) == reg.domain:
            registry.async_remove(reg.entity_id)
    if "game_sensors" in entry.options:
        options = {k: v for k, v in entry.options.items() if k != "game_sensors"}
        hass.config_entries.async_update_entry(entry, options=options)


async def _async_take_over(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> None:
    """An entry imported from the integration before Boréale ("playguard"):
    its device and entities move to this one, entity ids, history, names,
    areas and dashboards included; the long-term statistics keep their ids
    (STATISTICS_SOURCE). The old entry is then removed, and ignored there,
    so the old integration, if still installed, does not offer the console
    again."""
    data = {k: v for k, v in entry.data.items() if k != CONF_IMPORTED}
    old = hass.config_entries.async_get_entry(entry.data[CONF_IMPORTED])
    if old is not None and old.domain == LEGACY_DOMAIN:
        if old.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(old.entry_id)
        console_id = data[CONF_CONSOLE_ID]
        devices = dr.async_get(hass)
        device = devices.async_get_device_by_identifier((LEGACY_DOMAIN, console_id), old.entry_id)
        # The entities first: a device moved to another entry takes away
        # the entities still on the entry it leaves.
        entities = er.async_get(hass)
        for reg in er.async_entries_for_config_entry(entities, old.entry_id):
            try:
                entities.async_update_entity_platform(
                    reg.entity_id,
                    DOMAIN,
                    new_config_entry_id=entry.entry_id,
                    new_device_id=device.id if device is not None else None,
                )
            except ValueError as err:  # still loaded: the old entry would not unload
                _LOGGER.warning("%s: %s stays with %s: %s", entry.title, reg.entity_id, LEGACY_DOMAIN, err)
        if device is not None:
            devices.async_update_device(
                device.id, new_config_entry_id=entry.entry_id, new_identifiers={(DOMAIN, console_id)}
            )
        _retire(hass, entry, old.minor_version)
        await hass.config_entries.async_remove(old.entry_id)
        _LOGGER.info("%s: taken over from the integration %s", entry.title, LEGACY_DOMAIN)
        try:
            await async_get_integration(hass, LEGACY_DOMAIN)
        except IntegrationNotFound:
            installed = False
        else:
            installed = True
            await hass.config_entries.flow.async_init(
                LEGACY_DOMAIN,
                context={"source": SOURCE_IGNORE},
                data={"unique_id": entry.unique_id, "title": entry.title},
            )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "taken_over",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="taken_over_installed" if installed else "taken_over",
            translation_placeholders={"legacy": LEGACY_DOMAIN},
        )
    hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> bool:
    """One console."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="mqtt_not_ready")
    if CONF_IMPORTED in entry.data:
        await _async_take_over(hass, entry)
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
