"""The icon of the app in front, as PlayGuard publishes it (every installed or
played game's, and the agent's for a homebrew, on icon/<APP_ID>), or
Boréale's own while its applet is in front."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import EntityDef, for_platform
from .entity import PlayGuardEntity
from .sensor import current_app

PARALLEL_UPDATES = 0

APPLET_ICON = Path(__file__).parent / "brand" / "icon.png"


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(NowPlayingIcon(hass, console, d) for d in for_platform(Platform.IMAGE, console.unpublished))


class NowPlayingIcon(PlayGuardEntity, ImageEntity):
    """The app in front: its icon, a JPEG; Boréale's own, a PNG, in its
    applet. None while no app is in front, or before its icon was published
    (a system program has none)."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, console: PlayGuardConsole, definition: EntityDef) -> None:
        PlayGuardEntity.__init__(self, console, definition)
        ImageEntity.__init__(self, hass)
        self._shown: bytes | None = None
        self._applet: bytes | None = None
        self._attr_image_last_updated: datetime | None = None

    async def async_added_to_hass(self) -> None:
        self._applet = await self.hass.async_add_executor_job(APPLET_ICON.read_bytes)
        await super().async_added_to_hass()

    def _icon(self) -> bytes | None:
        app = current_app(self.console.state, self.console.game_name)
        if app is None:
            return None
        if app["type"] == "applet":
            return self._applet
        return self.console.icons.get(app["app_id"].upper())

    @property
    def content_type(self) -> str:
        return "image/png" if self._shown is not None and self._shown == self._applet else "image/jpeg"

    @callback
    def _handle_update(self) -> None:
        icon = self._icon()
        if icon != self._shown:
            self._shown = icon
            self._attr_image_last_updated = dt_util.utcnow() if icon else None
        super()._handle_update()

    async def async_image(self) -> bytes | None:
        return self._shown
