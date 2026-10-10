"""The restriction level, and the saved profiles."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
        (ProfileSelect if d.key == "profile" else PlayGuardSelect)(console, d) for d in for_platform(Platform.SELECT)
    )


class PlayGuardSelect(PlayGuardEntity, SelectEntity):
    """One of a fixed list."""

    def __init__(self, console, definition) -> None:
        super().__init__(console, definition)
        self._attr_options = list(definition.options or ())

    @property
    def current_option(self) -> str | None:
        value = self.read()
        return value if value in self.options else None

    async def async_select_option(self, option: str) -> None:
        await self.async_order(option)


class ProfileSelect(PlayGuardSelect):
    """Applies a profile saved in PlayGuard. Which one is in effect is not
    known: the limits say it."""

    @property
    def options(self) -> list[str]:
        profiles = (self.console.state or {}).get("profiles")
        return [p for p in profiles if isinstance(p, str)] if isinstance(profiles, list) else []

    @property
    def current_option(self) -> str | None:
        return None
