"""Buttons: extra time, no more play today, lock now, sync now, a report."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .entities import for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(PlayGuardButton(console, d) for d in for_platform(Platform.BUTTON))


class PlayGuardButton(PlayGuardEntity, ButtonEntity):
    """A PRESS order."""

    async def async_press(self) -> None:
        await self.async_order("PRESS")
