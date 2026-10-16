"""The play-time limits (minutes; 1440 = no limit)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
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
    async_add_entities(PlayGuardNumber(console, d) for d in for_platform(Platform.NUMBER))


class PlayGuardNumber(PlayGuardEntity, NumberEntity):
    """A limit, set by an order."""

    _attr_mode = NumberMode.BOX

    def __init__(self, console, definition) -> None:
        super().__init__(console, definition)
        self._attr_native_min_value = definition.minimum
        self._attr_native_max_value = definition.maximum
        self._attr_native_step = definition.step
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_class = NumberDeviceClass(definition.device_class)

    @property
    def native_value(self) -> int | None:
        value = self.read()
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.async_order(str(int(round(value))))
