"""Switches: bedtime, blocking all games, the alarm, the restrictions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities(PlayGuardSwitch(console, d) for d in for_platform(Platform.SWITCH))


class PlayGuardSwitch(PlayGuardEntity, SwitchEntity):
    """ON / OFF orders; the state says what the console did."""

    @property
    def is_on(self) -> bool | None:
        value = self.read()
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_order("ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_order("OFF")
