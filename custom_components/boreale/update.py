"""PlayGuard's version on the console against its latest release on GitHub,
with the release notes. Installed on the console itself (PlayGuard offers it
when it checks for updates): nothing to install from here.

Not polled: the release is read when the entity is added, then again with
the console's documents once six hours have passed (a console asleep does
not change its version)."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .entities import dig, for_platform
from .entity import PlayGuardEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
# GitHub's releases: read again after six hours.
CHECK_EVERY = timedelta(hours=6)
RELEASES = "https://api.github.com/repos/JigSawFr/PlayGuard/releases/latest"
TIMEOUT = aiohttp.ClientTimeout(total=20)
SUMMARY_MAX = 255  # Home Assistant's limit for release_summary


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(PlayGuardUpdate(console, d) for d in for_platform(Platform.UPDATE, console.unpublished))


async def async_latest_release(hass: HomeAssistant) -> dict[str, Any] | None:
    """PlayGuard's latest release on GitHub, None when it cannot be read."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(RELEASES, timeout=TIMEOUT, headers={"Accept": "application/vnd.github+json"}) as resp:
            resp.raise_for_status()
            release = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("PlayGuard's latest release could not be read: %r", err)
        return None
    return release if isinstance(release, dict) else None


class PlayGuardUpdate(PlayGuardEntity, UpdateEntity):
    """PlayGuard on the console: its version (the app's, else the agent's)
    and the latest release."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_title = "PlayGuard"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self._release: dict[str, Any] | None = None
        self._checked: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._check()

    @callback
    def _handle_update(self) -> None:
        self._check()
        super()._handle_update()

    @callback
    def _check(self) -> None:
        """Reads the latest release again once it is six hours old."""
        now = dt_util.utcnow()
        if self._checked is not None and now - self._checked < CHECK_EVERY:
            return
        self._checked = now
        self.console.entry.async_create_background_task(
            self.hass, self._async_read(), f"playguard {self.console.console_id} release"
        )

    async def _async_read(self) -> None:
        release = await async_latest_release(self.hass)
        if release is not None:  # else the last one read stays
            self._release = release
            self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        version = (
            dig(self.console.system, ("versions", "app"))
            or dig(self.console.state, ("console", "app_version"))
            or dig(self.console.state, ("console", "agent_version"))
        )
        return version if isinstance(version, str) and version else None

    @property
    def latest_version(self) -> str | None:
        tag = (self._release or {}).get("tag_name")
        # Unknown yet (offline, rate-limited): the installed one, not "update available".
        return tag.removeprefix("v") if isinstance(tag, str) and tag else self.installed_version

    @property
    def release_url(self) -> str | None:
        url = (self._release or {}).get("html_url")
        return url if isinstance(url, str) else None

    @property
    def release_summary(self) -> str | None:
        name = (self._release or {}).get("name")
        return name[:SUMMARY_MAX] if isinstance(name, str) and name else None

    async def async_release_notes(self) -> str | None:
        body = (self._release or {}).get("body")
        return body if isinstance(body, str) and body else None
