"""Sensors: play time, what is being played, the console, its games."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .coordinator import PlayGuardConsole
from .entities import EntityDef, for_platform
from .entity import PlayGuardEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PlayGuardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    console = entry.runtime_data
    classes = {
        "now_playing": NowPlayingSensor,
        "used_screen_time_log": PlayLogSensor,
        "week_play_time": WeekSensor,
        "games_installed": GamesInstalledSensor,
        "last_seen": LastSeenSensor,
        "play_ends": PlayEndsSensor,
    }
    async_add_entities(
        classes.get(d.key, PlayGuardSensor)(console, d) for d in for_platform(Platform.SENSOR, console.unpublished)
    )


def _posix(value: Any) -> int:
    """POSIX seconds, 0 unknown."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _timestamp(value: Any) -> datetime | None:
    """POSIX seconds as a date, None unknown."""
    return dt_util.utc_from_timestamp(value) if _posix(value) else None


class PlayGuardSensor(PlayGuardEntity, SensorEntity):
    """A value of the state."""

    def __init__(self, console: PlayGuardConsole, definition: EntityDef) -> None:
        super().__init__(console, definition)
        if definition.unit:
            self._attr_native_unit_of_measurement = definition.unit
        if definition.device_class:
            self._attr_device_class = SensorDeviceClass(definition.device_class)
        if definition.state_class:
            self._attr_state_class = SensorStateClass(definition.state_class)
        if definition.options:
            self._attr_options = list(definition.options)
        if definition.suggested_unit:
            self._attr_suggested_unit_of_measurement = definition.suggested_unit
        if definition.precision is not None:
            self._attr_suggested_display_precision = definition.precision

    @property
    def native_value(self) -> Any:
        value = self.read()
        if self.definition.device_class == SensorDeviceClass.TIMESTAMP:
            return _timestamp(value)
        if self.definition.options and value not in self.definition.options:
            return None  # an option this integration does not know (a newer console)
        return value if isinstance(value, (int, float, str)) and not isinstance(value, bool) else None


def _games(console: PlayGuardConsole, per_app: list[Any] | None) -> dict[str, int]:
    """{game: minutes}, the most played first."""
    out: dict[str, int] = {}
    for app in sorted(per_app or [], key=lambda a: -(a.get("s") or 0) if isinstance(a, dict) else 0):
        if isinstance(app, dict) and isinstance(app.get("app_id"), str):
            out[console.game_name(app["app_id"]) or app["app_id"]] = app.get("min") or 0
    return out


def _minutes(value: Any) -> int | None:
    """A count of minutes: an int, not a bool."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _date(value: Any) -> date | None:
    """A "YYYY-MM-DD" date, else None."""
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def _accounts(console: PlayGuardConsole, rows: Any) -> dict[str, int] | None:
    """{account: minutes}, the most played first; None when the console did
    not say (the app reads the accounts only when asked to, an older agent never)."""
    if not isinstance(rows, list):
        return None
    out: dict[str, int] = {}
    for row in rows:
        uid = row.get("uid") if isinstance(row, dict) else None
        if not isinstance(uid, str):
            continue
        minutes = row.get("min")
        if isinstance(minutes, list):  # the week: a day each
            minutes = sum(m for m in minutes if isinstance(m, int) and not isinstance(m, bool))
        if isinstance(minutes, int) and not isinstance(minutes, bool):
            name = console.account_name(uid) or uid
            out[name] = out.get(name, 0) + minutes
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


class NowPlayingSensor(PlayGuardSensor):
    """The game being played: its name (from the names PlayGuard publishes), else its id."""

    @property
    def native_value(self) -> str | None:
        playing = ((self.console.state or {}).get("activity_today") or {}).get("now_playing") or {}
        app_id = playing.get("app_id")
        return playing.get("name") or self.console.game_name(app_id) or app_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        playing = ((self.console.state or {}).get("activity_today") or {}).get("now_playing") or {}
        return {"app_id": playing.get("app_id"), "since": playing.get("since")}


class PlayLogSensor(PlayGuardSensor):
    """Today's play time from the play log, with each game's."""

    # Each game's minutes change as it is played: not worth recording.
    _unrecorded_attributes = frozenset({"games", "accounts"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        activity = self.console.activity or {}
        return {
            "games": _games(self.console, activity.get("per_app")),
            "accounts": _accounts(self.console, activity.get("per_account")),
        }


class WeekSensor(PlayGuardSensor):
    """The last seven days' play time, with each day's, each game's and each
    account's. The app writes the week table; the agent alone does not, but
    it publishes today's play log and every finished day: the window moves on
    with them, and each day takes the larger count."""

    _unrecorded_attributes = frozenset({"days", "games", "accounts"})

    @property
    def available(self) -> bool:
        return bool(self._window()) and self.shown

    def _window(self) -> list[str]:
        """The seven days shown: the week table's, or the seven up to today's
        play log when it is later."""
        days = [d for d in (self.console.week or {}).get("days") or [] if isinstance(d, str)]
        today = _date((self.console.activity or {}).get("local_date"))
        if today is not None and (not days or today.isoformat() > days[-1]):
            return [(today - timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
        return days

    def _table(self, rows_key: str, id_key: str, log_key: str) -> dict[str, list[int]] | None:
        """Minutes per day of the window, by game (`app_id`) or by account
        (`uid`): the week table's rows, then the finished days' and today's
        play log, each day the larger count. None when none of them says
        (the accounts, from a PlayGuard whose agent does not read them)."""
        days = self._window()
        at = {day: i for i, day in enumerate(days)}
        table: dict[str, list[int]] = {}
        known = False

        def count(key: Any, day: Any, minutes: Any) -> None:
            if isinstance(key, str) and key and day in at and _minutes(minutes) is not None:
                row = table.setdefault(key, [0] * len(days))
                row[at[day]] = max(row[at[day]], minutes)

        week = self.console.week or {}
        if isinstance(week.get(rows_key), list):
            known = True
            for row in week[rows_key]:
                if isinstance(row, dict):
                    for day, minutes in zip(week.get("days") or [], row.get("min") or [], strict=False):
                        count(row.get(id_key), day, minutes)
        activity = self.console.activity or {}
        logs = [*((doc.get("local_date") or day, doc) for day, doc in self.console.finals.items())]
        logs.append((activity.get("local_date"), activity))
        for day, doc in logs:
            if day in at and isinstance(doc.get(log_key), list):
                known = True
                for item in doc[log_key]:
                    if isinstance(item, dict):
                        count(item.get(id_key), day, item.get("min"))
        return table if known else None

    def _games(self) -> dict[str, list[int]]:
        return self._table("games", "app_id", "per_app") or {}

    def _days(self) -> dict[str, int]:
        days = self._window()
        totals = [sum(day) for day in zip(*self._games().values(), strict=True)] or [0] * len(days)
        return dict(zip(days, totals, strict=False))

    def _accounts(self) -> dict[str, int] | None:
        table = self._table("accounts", "uid", "per_account")
        if table is None:
            return None
        return _accounts(self.console, [{"uid": uid, "min": sum(minutes)} for uid, minutes in table.items()])

    @property
    def native_value(self) -> int | None:
        return sum(self._days().values()) if self._window() else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        games = {self.console.game_name(app_id) or app_id: sum(m) for app_id, m in self._games().items()}
        return {
            "days": self._days(),
            "games": dict(sorted(games.items(), key=lambda kv: -kv[1])),
            "accounts": self._accounts(),
        }


class PlayEndsSensor(PlayGuardSensor):
    """When play has to stop, while a game is played: the end of today's
    limit or bedtime, whichever comes first (`ends_by`: `limit` or
    `bedtime`). Unknown when no game is played (the timer only counts then,
    and PlayGuard in front means nobody plays), when games are already
    blocked, with the play timer off, or with neither a limit nor bedtime. Counted from the state's
    time, so it holds still between two states."""

    def _end(self) -> tuple[datetime, str] | None:
        state = self.console.state or {}
        timer = state.get("timer") or {}
        playing = (state.get("activity_today") or {}).get("now_playing") or {}
        if not playing.get("app_id") or not timer.get("supported") or timer.get("limit_reached"):
            return None
        if timer.get("enabled") is False:  # the play timer off: neither its limit nor its bedtime blocks
            return None
        base = _timestamp(state.get("ts")) or self.console.last_seen
        if base is None:
            return None
        ends: list[tuple[datetime, str]] = []
        limit, remaining = timer.get("limit_today_min"), timer.get("remaining_min")
        if (
            isinstance(limit, int)
            and isinstance(remaining, int)
            and not isinstance(remaining, bool)
            and 0 <= limit < 1440
            and remaining >= 0
        ):
            ends.append((base + timedelta(minutes=remaining), "limit"))
        bedtime = timer.get("bedtime") or {}
        start = dt_util.parse_time(bedtime.get("start") or "") if bedtime.get("enabled") else None
        if start is not None:
            local = dt_util.as_local(base)
            alarm = local.replace(hour=start.hour, minute=start.minute, second=start.second, microsecond=0)
            if alarm <= local:
                alarm += timedelta(days=1)
            ends.append((dt_util.as_utc(alarm), "bedtime"))
        return min(ends) if ends else None

    @property
    def native_value(self) -> datetime | None:
        end = self._end()
        return end[0] if end else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        end = self._end()
        return {"ends_by": end[1] if end else None}


class LastSeenSensor(PlayGuardSensor):
    """When the console last said something: the last document it published
    while Home Assistant listened, else (after a restart) the time of its
    last state. Shown while it sleeps too: that is when it is wanted."""

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def native_value(self) -> datetime | None:
        state_ts = _timestamp((self.console.state or {}).get("ts"))
        seen = self.console.last_seen
        if seen and state_ts:
            return max(seen, state_ts)
        return seen or state_ts


class GamesInstalledSensor(PlayGuardSensor):
    """How many games are installed, with every game the console lists: its
    name, play time, whether it is installed, when it was last played (the
    last played first). A dashboard's list of games, without a sensor each."""

    # Changes with every game played, and long: not worth recording.
    _unrecorded_attributes = frozenset({"games"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        games = (self.console.games or {}).get("games")
        listed = [(k, g) for k, g in games.items() if isinstance(g, dict)] if isinstance(games, dict) else []
        rows = []
        for app_id, game in sorted(listed, key=lambda kv: _posix(kv[1].get("last_played")), reverse=True):
            last = _timestamp(game.get("last_played"))
            minutes = game.get("total_min")
            rows.append(
                {
                    "app_id": app_id,
                    "name": game.get("name") or self.console.game_name(app_id) or app_id,
                    "minutes": minutes if isinstance(minutes, int) and not isinstance(minutes, bool) else None,
                    "installed": game.get("installed"),
                    "last_played": last.isoformat() if last else None,
                }
            )
        return {"games": rows}
