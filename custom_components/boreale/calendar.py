"""A calendar of play sessions: when each game was played, from the
recorder's history of *Now playing* while the console was online."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .const import DOMAIN
from .entities import for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0

# What *Now playing* reads when no game is played, or nothing is known.
NOT_PLAYING = frozenset({STATE_UNKNOWN, STATE_UNAVAILABLE, "", "None"})
# How far ahead the session going on ends, until the next state says more.
ONGOING = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    async_add_entities(PlaySessions(console, d) for d in for_platform(Platform.CALENDAR, console.unpublished))


def sessions(
    history: dict[str, list[State]], playing_id: str, online_id: str | None, until: datetime
) -> list[CalendarEvent]:
    """The sessions in a history: a game shown in *Now playing* while
    *Online* is on (asleep, the console plays nothing: the play log stops
    too), one event per stretch, the last one up to `until` if not over."""
    changes = sorted(
        ((s.last_changed, entity_id, s.state) for entity_id in (playing_id, online_id) if entity_id
         for s in history.get(entity_id, [])),
        key=lambda change: change[0],
    )  # fmt: skip
    game: str | None = None
    online = online_id is None or not history.get(online_id)  # no history of it: taken as online
    out: list[CalendarEvent] = []
    open_at: tuple[datetime, str] | None = None
    for when, entity_id, state in [*changes, (until, None, None)]:
        if entity_id == playing_id:
            game = None if state in NOT_PLAYING else state
        elif entity_id == online_id:
            online = state == "on"
        now = game if online else None
        if open_at and (entity_id is None or open_at[1] != now):
            if when > open_at[0]:
                out.append(CalendarEvent(start=open_at[0], end=when, summary=open_at[1]))
            open_at = None
        if now and entity_id and not open_at:
            open_at = (when, now)
    return out


class PlaySessions(PlayGuardEntity, CalendarEntity):
    """The console's play sessions, game by game."""

    def _ids(self) -> tuple[str | None, str | None]:
        registry = er.async_get(self.hass)
        cid = self.console.console_id
        return (
            registry.async_get_entity_id("sensor", DOMAIN, f"{cid}_now_playing"),
            registry.async_get_entity_id("binary_sensor", DOMAIN, f"{cid}_online"),
        )

    @property
    def available(self) -> bool:
        return self.shown

    @property
    def event(self) -> CalendarEvent | None:
        """The session going on, from the console's state: the game played
        now, since when it got the focus."""
        playing = ((self.console.state or {}).get("activity_today") or {}).get("now_playing") or {}
        app_id = playing.get("app_id")
        if not app_id or self.console.online is False:
            return None
        now = dt_util.utcnow()
        since = playing.get("since")
        start = dt_util.utc_from_timestamp(since) if isinstance(since, int) and 0 < since < now.timestamp() else now
        name = playing.get("name") or self.console.game_name(app_id) or app_id
        # Not over: its end a little ahead, moved on by every state (the
        # console sends one each poll_s while awake), so that it reads on.
        return CalendarEvent(start=start, end=now + ONGOING, summary=name)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        playing_id, online_id = self._ids()
        if playing_id is None or "recorder" not in hass.config.components:
            return []
        from homeassistant.components.recorder import history  # noqa: PLC0415
        from homeassistant.helpers.recorder import get_instance  # noqa: PLC0415

        ids = [i for i in (playing_id, online_id) if i]
        found: dict[str, list[Any]] = await get_instance(hass).async_add_executor_job(
            lambda: history.get_significant_states(
                hass, start_date, end_date, ids, significant_changes_only=False, no_attributes=True
            )
        )
        until = min(end_date, dt_util.utcnow())
        return [
            e
            for e in sessions(found, playing_id, online_id, until)
            if e.end_datetime_local > start_date and e.start_datetime_local < end_date
        ]
