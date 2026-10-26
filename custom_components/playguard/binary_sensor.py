"""Binary sensors: parental controls, the timer, the link."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import EntityDef, dig, for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    classes: dict[str, type[PlayGuardBinarySensor]] = {
        "online": OnlineSensor,
        "limit_reached": BlockedSensor,
        "agent": AgentSensor,
    }
    async_add_entities(
        classes.get(d.key, PlayGuardBinarySensor)(console, d)
        for d in for_platform(Platform.BINARY_SENSOR, console.unpublished)
    )


class PlayGuardBinarySensor(PlayGuardEntity, BinarySensorEntity):
    """A true/false value of the state."""

    _keeps_value = True

    def __init__(self, console: PlayGuardConsole, definition: EntityDef) -> None:
        super().__init__(console, definition)
        if definition.device_class:
            self._attr_device_class = BinarySensorDeviceClass(definition.device_class)

    @property
    def is_on(self) -> bool | None:
        value = self.read()
        return value if isinstance(value, bool) else None


class BlockedSensor(PlayGuardBinarySensor):
    """Games are blocked: the day's limit, or the bedtime alarm's hours (the
    play timer blocks during both). Its reason says which."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reason = dig(self.console.state, ("timer", "blocked_by"))
        return {"reason": reason if reason in ("limit", "bedtime") else None}


class OnlineSensor(PlayGuardBinarySensor):
    """Whether the console is on the broker now (its last will says when not)."""

    @property
    def available(self) -> bool:
        return self.console.online is not None

    @property
    def is_on(self) -> bool | None:
        return self.console.online


class AgentSensor(PlayGuardBinarySensor):
    """Whether the agent runs: not while the console is off the broker (the
    agent sleeps with it), whatever its last state said."""

    @property
    def is_on(self) -> bool | None:
        return False if self.console.online is False else super().is_on
