"""The console's events: an order applied, refused, or waiting for PlayGuard."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .const import EVENT_TYPES
from .entities import for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(PlayGuardEvent(console, d) for d in for_platform(Platform.EVENT, console.unpublished))


class PlayGuardEvent(PlayGuardEntity, EventEntity):
    """One event per order the console handled (the `event` topic, not retained)."""

    _attr_event_types = list(EVENT_TYPES)
    _keeps_value = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.console.async_add_event_listener(self._handle_event))

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """The event listener does not depend on the entity id either."""
        super().async_entity_id_changed(old_entity_id)

    @property
    def available(self) -> bool:
        return self.shown

    @callback
    def _handle_event(self, doc: dict[str, Any]) -> None:
        event_type = doc.get("event_type")
        if event_type not in EVENT_TYPES:
            return
        self._trigger_event(
            event_type,
            {k: doc.get(k) for k in ("entity", "payload", "reason", "rc", "source", "ts")},
        )
        self.async_write_ha_state()
