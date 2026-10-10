"""Binary sensors: parental controls, the timer, the link."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    async_add_entities(
        (OnlineSensor if d.key == "online" else PlayGuardBinarySensor)(console, d)
        for d in for_platform(Platform.BINARY_SENSOR)
    )


class PlayGuardBinarySensor(PlayGuardEntity, BinarySensorEntity):
    """A true/false value of the state."""

    def __init__(self, console, definition) -> None:
        super().__init__(console, definition)
        if definition.device_class:
            self._attr_device_class = BinarySensorDeviceClass(definition.device_class)

    @property
    def is_on(self) -> bool | None:
        value = self.read()
        return value if isinstance(value, bool) else None


class OnlineSensor(PlayGuardBinarySensor):
    """Whether the console is on the broker now (its last will says when not)."""

    @property
    def available(self) -> bool:
        return self.console.online is not None

    @property
    def is_on(self) -> bool | None:
        return self.console.online
