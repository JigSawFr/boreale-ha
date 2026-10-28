"""The icon of the game being played, as PlayGuard publishes it (every
installed or played game's, on icon/<APP_ID>)."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import EntityDef, dig, for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(NowPlayingIcon(hass, console, d) for d in for_platform(Platform.IMAGE, console.unpublished))


class NowPlayingIcon(PlayGuardEntity, ImageEntity):
    """The game being played: its icon, a JPEG. None while no game is
    played, or before PlayGuard published its icon."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, console: PlayGuardConsole, definition: EntityDef) -> None:
        PlayGuardEntity.__init__(self, console, definition)
        ImageEntity.__init__(self, hass)
        self._shown: bytes | None = None
        self._attr_image_last_updated: datetime | None = None

    def _icon(self) -> bytes | None:
        app_id = dig(self.console.state, ("activity_today", "now_playing", "app_id"))
        return self.console.icons.get(app_id.upper()) if isinstance(app_id, str) else None

    @callback
    def _handle_update(self) -> None:
        icon = self._icon()
        if icon != self._shown:
            self._shown = icon
            self._attr_image_last_updated = dt_util.utcnow() if icon else None
        super()._handle_update()

    async def async_image(self) -> bytes | None:
        return self._shown
