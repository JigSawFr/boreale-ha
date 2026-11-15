"""PlayShelf's entities: what the PlayShelf homebrew says through the agent.

PlayShelf publishes its `state` (boreale/<id>/playshelf/state, schema 1) and
takes orders (`<entity>/set`) while it is open and the PlayGuard agent holds
the console's broker connection; the agent lists it in `capabilities` while
its session is open. The entities are created once the console announces the
module, on the console's device (one device a console), and are unavailable
while the module is not announced or the console is out of reach: PlayShelf
closed, or no agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfInformation
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import dig

PAUSE_ORDER = "pause_downloads/set"


@dataclass(frozen=True, kw_only=True)
class ShelfDef:
    """One entity of the PlayShelf module."""

    key: str  # object id, and the unique id's end
    platform: Platform
    path: tuple[str, ...] | None = None  # where the value is in the state
    unit: str | None = None
    device_class: str | None = None
    state_class: SensorStateClass | None = None
    suggested_unit: str | None = None


SHELF_ENTITIES: tuple[ShelfDef, ...] = (
    ShelfDef(
        key="shelf_pending",
        platform=Platform.SENSOR,
        path=("downloads", "pending"),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ShelfDef(
        key="shelf_progress",
        platform=Platform.SENSOR,
        path=("downloads", "progress"),
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ShelfDef(key="shelf_last_installed", platform=Platform.SENSOR, path=("last_installed",)),
    ShelfDef(
        key="shelf_free",
        platform=Platform.SENSOR,
        path=("storage", "free"),
        unit=UnitOfInformation.BYTES,
        device_class="data_size",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit=UnitOfInformation.GIBIBYTES,
    ),
    ShelfDef(key="shelf_downloading", platform=Platform.BINARY_SENSOR, path=("downloads", "running")),
    ShelfDef(key="shelf_failed", platform=Platform.BINARY_SENSOR, path=("downloads", "failed")),
    ShelfDef(key="shelf_pause", platform=Platform.BUTTON),
)


class ShelfEntity(Entity):
    """An entity reading PlayShelf's `state`."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, console: PlayGuardConsole, definition: ShelfDef) -> None:
        self.console = console
        self.definition = definition
        self._attr_unique_id = f"{console.console_id}_{definition.key}"
        self._attr_translation_key = definition.key
        self._attr_device_info = console.device_info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.console.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """The module announced, its state known, the console shown."""
        return (
            self.console.has_playshelf
            and self.console.playshelf is not None
            and (self.console.reachable or self.console.keep_values)
        )

    def read(self) -> Any:
        return dig(self.console.playshelf, self.definition.path)


class ShelfSensor(ShelfEntity, SensorEntity):
    """A value of PlayShelf's state."""

    def __init__(self, console: PlayGuardConsole, definition: ShelfDef) -> None:
        super().__init__(console, definition)
        if definition.unit:
            self._attr_native_unit_of_measurement = definition.unit
        if definition.device_class:
            self._attr_device_class = SensorDeviceClass(definition.device_class)
        if definition.state_class:
            self._attr_state_class = definition.state_class
        if definition.suggested_unit:
            self._attr_suggested_unit_of_measurement = definition.suggested_unit

    @property
    def native_value(self) -> Any:
        """A number for the counts, the percents and the room; text for the last game. Anything else: unknown."""
        value = self.read()
        if self.definition.key == "shelf_last_installed":
            return value if isinstance(value, str) and value else None
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class ShelfBinarySensor(ShelfEntity, BinarySensorEntity):
    """On while at least one download runs, or one failed."""

    def __init__(self, console: PlayGuardConsole, definition: ShelfDef) -> None:
        super().__init__(console, definition)
        self._attr_device_class = (
            BinarySensorDeviceClass.RUNNING
            if definition.key == "shelf_downloading"
            else BinarySensorDeviceClass.PROBLEM
        )

    @property
    def is_on(self) -> bool | None:
        count = self.read()
        if isinstance(count, bool) or not isinstance(count, int):
            return None
        return count > 0


class ShelfPauseButton(ShelfEntity, ButtonEntity):
    """Pauses PlayShelf's downloads. Not kept on the broker: pressed while
    PlayShelf is closed, it does nothing, rather than pausing a later session."""

    async def async_press(self) -> None:
        await self.console.async_playshelf_order(PAUSE_ORDER, "PRESS")


@callback
def async_add(
    entry: PlayGuardConfigEntry, platform: Platform, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the PlayShelf entities of `platform`: at once those the registry
    knows (they are unavailable until the module is announced, not lost), the
    others when the console announces the module."""
    console = entry.runtime_data
    definitions = [d for d in SHELF_ENTITIES if d.platform == platform]
    added: set[str] = set()

    def build(definition: ShelfDef) -> ShelfEntity:
        match platform:
            case Platform.SENSOR:
                return ShelfSensor(console, definition)
            case Platform.BINARY_SENSOR:
                return ShelfBinarySensor(console, definition)
            case _:
                return ShelfPauseButton(console, definition)

    @callback
    def add(known: set[str] | None = None) -> None:
        if known is None and not console.has_playshelf:
            return
        new = [d for d in definitions if d.key not in added and (known is None or d.key in known)]
        added.update(d.key for d in new)
        async_add_entities(build(d) for d in new)

    prefix = f"{console.console_id}_"
    registry = er.async_get(console.hass)
    add(
        {
            e.unique_id.removeprefix(prefix)
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == platform and e.unique_id.startswith(prefix)
        }
    )
    add()
    entry.async_on_unload(console.async_add_listener(add))
