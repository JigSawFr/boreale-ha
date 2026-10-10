"""Bedtime: when the alarm sounds, when play is allowed again."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .entities import for_platform
from .entity import PlayGuardEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(PlayGuardTime(console, d) for d in for_platform(Platform.TIME))


class PlayGuardTime(PlayGuardEntity, TimeEntity):
    """A time of day, "HH:MM:SS" in the state, "HH:MM" in the order."""

    @property
    def native_value(self) -> time | None:
        value = self.read()
        if not isinstance(value, str):
            return None
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        await self.async_order(value.strftime("%H:%M"))
