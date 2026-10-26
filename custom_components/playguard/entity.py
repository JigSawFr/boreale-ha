"""The base of every PlayGuard entity."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .coordinator import PlayGuardConsole
from .entities import EntityDef, dig


class PlayGuardEntity(Entity):
    """An entity reading the console's documents."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # A value (a sensor, an event) rather than a control: it may keep showing
    # what the console last said while the console sleeps.
    _keeps_value = False

    def __init__(self, console: PlayGuardConsole, definition: EntityDef) -> None:
        self.console = console
        self.definition = definition
        self._attr_unique_id = f"{console.console_id}_{definition.key}"
        self._attr_translation_key = definition.key
        self._attr_device_info = console.device_info
        self._attr_entity_registry_enabled_default = definition.enabled
        if definition.category:
            self._attr_entity_category = EntityCategory(definition.category)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.console.async_add_listener(self._handle_update))

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Nothing here depends on the entity id: it may change in place
        (Home Assistant 2026.11 and later; not called before)."""
        super().async_entity_id_changed(old_entity_id)  # type: ignore[misc]  # 2026.11's Entity

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Known once the console's document arrived (retained: at once after
        a restart), while the console is shown (`shown`)."""
        return self.console.document(self.definition.topic) is not None and self.shown

    @property
    def shown(self) -> bool:
        """While the console is on the broker (its last will says when it is
        not), or, for a value, while the entry keeps the last values. A control
        is unavailable then; the actions still send orders (they wait on the
        broker)."""
        return self.console.reachable or (self._keeps_value and self.console.keep_values)

    def read(self) -> Any:
        """This entity's value in its document (not `value`: NumberEntity has one)."""
        doc = self.console.document(self.definition.topic)
        value = dig(doc, self.definition.path)
        if value is None and self.definition.fallback:
            value = dig(doc, self.definition.fallback)
        return value

    async def async_order(self, payload: str) -> None:
        """Sends this entity's order (retained: it waits if the console sleeps)."""
        await self.console.async_order(self.definition.key, self.definition.write, payload)
