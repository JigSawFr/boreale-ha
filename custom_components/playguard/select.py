"""The restriction level, and the saved profiles."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import EntityDef, for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(
        (ProfileSelect if d.key == "profile" else PlayGuardSelect)(console, d)
        for d in for_platform(Platform.SELECT, console.unpublished)
    )


class PlayGuardSelect(PlayGuardEntity, SelectEntity):
    """One of a fixed list."""

    def __init__(self, console: PlayGuardConsole, definition: EntityDef) -> None:
        super().__init__(console, definition)
        self._attr_options = list(definition.options or ())
        self._option_of = dict(definition.renamed)
        self._value_of = {option: value for value, option in definition.renamed}

    @property
    def current_option(self) -> str | None:
        value = self.read()
        if not isinstance(value, str):
            return None
        option = self._option_of.get(value, value)
        return option if option in self.options else None

    async def async_select_option(self, option: str) -> None:
        await self.async_order(self._value_of.get(option, option))


class ProfileSelect(PlayGuardSelect):
    """Applies a profile saved in PlayGuard; shows the one in effect (the
    saved profile whose limits are the timer's), else none."""

    @property
    def options(self) -> list[str]:
        profiles = (self.console.state or {}).get("profiles")
        return [p for p in profiles if isinstance(p, str)] if isinstance(profiles, list) else []

    @property
    def current_option(self) -> str | None:
        value = self.read()
        return value if isinstance(value, str) and value in self.options else None
