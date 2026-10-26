"""The console's events: an order applied, refused, or waiting for PlayGuard;
and what the console does on its own (a game started or stopped, a few
minutes left, games blocked)."""

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
    """One event per order the console handled, and per thing it did on its
    own (the `event` topic, not retained)."""

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
        attributes = {k: doc.get(k) for k in ("entity", "payload", "reason", "rc", "source", "ts")}
        if event_type.startswith("play_") or event_type == "time_warning":
            app_id = doc.get("app_id")
            attributes |= {
                "app_id": app_id,
                "game": self.console.game_name(app_id) if isinstance(app_id, str) else None,
                "minutes_left": doc.get("minutes_left"),
                "blocked_by": doc.get("blocked_by"),
            }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
