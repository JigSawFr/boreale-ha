"""What the console's triggers and conditions target: one of its entities,
picked by its key, wherever the target points (the console's device, its
area, the entity itself)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def console_entities(hass: HomeAssistant, entities: set[str], key: str) -> set[str]:
    """The entities among `entities` that are a console's `key` entity."""
    registry = er.async_get(hass)
    found: set[str] = set()
    for entity_id in entities:
        entry = registry.async_get(entity_id)
        if entry is not None and entry.platform == DOMAIN and entry.unique_id.partition("_")[2] == key:
            found.add(entity_id)
    return found
