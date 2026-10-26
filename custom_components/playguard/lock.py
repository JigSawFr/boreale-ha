"""The lock: parental controls, locked while they are in effect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .entities import dig, for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(ParentalControlsLock(console, d) for d in for_platform(Platform.LOCK, console.unpublished))


class ParentalControlsLock(PlayGuardEntity, LockEntity):
    """Locked while parental controls are set up and not temporarily
    unlocked. Unlocking unlocks them for now with the stored PIN (it needs
    "Orders may change the play timer"); locking turns them back on, always
    allowed."""

    @property
    def is_locked(self) -> bool | None:
        enabled = dig(self.console.state, ("controls", "enabled"))
        unlocked = dig(self.console.state, ("controls", "temp_unlocked"))
        if not isinstance(enabled, bool) or not isinstance(unlocked, bool):
            return None
        return enabled and not unlocked

    async def async_lock(self, **kwargs: Any) -> None:
        await self.async_order("LOCK")

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.async_order("UNLOCK")
