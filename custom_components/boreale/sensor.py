"""Sensors: play time, what is being played, the console, its games."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry, play
from .const import ACTIVITY_OPTIONS, PUBLISH_ACTIVITY
from .coordinator import PlayGuardConsole
from .entities import ACCOUNT_ENTITIES, EntityDef, for_platform
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
        "console_activity": ActivitySensor,
    }
    async_add_entities(
        classes.get(d.key, PlayGuardSensor)(console, d) for d in for_platform(Platform.SENSOR, console.unpublished)
    )
    if PUBLISH_ACTIVITY in console.unpublished:
        return

    # Each account's pair: the ones already in the registry at once, the
    # others as the console speaks of them.
    added: set[str] = set()
    prefix = f"{console.console_id}_account_"

    @callback
    def add_accounts(uids: set[str]) -> None:
        new = sorted(uids - added)
        added.update(new)
        async_add_entities(AccountSensor(console, d, uid) for uid in new for d in ACCOUNT_ENTITIES)

    registry = er.async_get(hass)
    add_accounts(
        {
            e.unique_id.removeprefix(prefix).rsplit("_", 1)[0]
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == Platform.SENSOR and e.unique_id.startswith(prefix)
        }
    )
    add_accounts(_account_ids(console))
    entry.async_on_unload(console.async_add_listener(lambda: add_accounts(_account_ids(console))))


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


class ActivitySensor(PlayGuardSensor):
    """What the console is doing: the state's activity_today.now (PlayGuard
    1.5), else what the state says (a game played, PlayGuard publishing),
    and offline while it is off the broker. Shown then too: that is when it
    is wanted."""

    @property
    def available(self) -> bool:
        return self.console.state is not None

    @property
    def native_value(self) -> str | None:
        if self.console.online is False:
            return "offline"
        state = self.console.state or {}
        today = state.get("activity_today") or {}
        now = today.get("now")
        if now in ACTIVITY_OPTIONS:
            return str(now)
        if "now" in today:  # said, and unknown (play time not published)
            return None
        # An older PlayGuard: a game played, PlayGuard publishing, else the HOME menu.
        if (today.get("now_playing") or {}).get("app_id"):
            return "game"
        return "playguard" if state.get("source") == "app" else "home"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        playing = ((self.console.state or {}).get("activity_today") or {}).get("now_playing") or {}
        app_id = playing.get("app_id")
        name = playing.get("name") or self.console.game_name(app_id) or app_id
        shown = self.native_value in ("game", "homebrew")
        return {"title": name if shown else None, "app_id": app_id if shown else None}


class PlayLogSensor(PlayGuardSensor):
    """Today's play time from the play log, with each game's."""

    # Each game's minutes change as it is played: not worth recording.
    _unrecorded_attributes = frozenset({"games", "accounts"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        activity = self.console.activity or {}
        return {
            "games": play.games(self.console, activity.get("per_app")),
            "homebrew": play.as_minutes(activity.get("homebrew_min")),
            "accounts": play.accounts(self.console, activity.get("per_account")),
        }


class WeekSensor(PlayGuardSensor):
    """The last seven days' play time, with each day's, each game's and each
    account's. The app writes the week table; the agent alone does not, but
    it publishes today's play log and every finished day: the window moves on
    with them, and each day takes the larger count."""

    _unrecorded_attributes = frozenset({"days", "games", "accounts"})

    @property
    def available(self) -> bool:
        return bool(play.window(self.console)) and self.shown

    @property
    def native_value(self) -> int | None:
        return sum(play.week_days(self.console).values()) if play.window(self.console) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        games = {
            self.console.game_name(app_id) or app_id: sum(m) for app_id, m in play.week_games(self.console).items()
        }
        return {
            "days": play.week_days(self.console),
            "games": dict(sorted(games.items(), key=lambda kv: -kv[1])),
            "homebrew": sum(play.week_homebrew(self.console).values()),
            "accounts": play.week_accounts(self.console),
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


def _account_ids(console: PlayGuardConsole) -> set[str]:
    """The accounts the console speaks of (upper case): named, or with play
    time in the play log or the week."""
    uids: set[Any] = set(console.names.get("accounts") or {})
    for doc in [console.activity or {}, *console.finals.values()]:
        uids |= {a.get("uid") for a in doc.get("per_account") or [] if isinstance(a, dict)}
    uids |= {a.get("uid") for a in (console.week or {}).get("accounts") or [] if isinstance(a, dict)}
    return {u.upper() for u in uids if isinstance(u, str) and len(u) == 32}


class AccountSensor(PlayGuardSensor):
    """One account's play time, today or this week, named after the account
    (its nickname on the console, from the names PlayGuard publishes; the
    start of its id until then)."""

    def __init__(self, console: PlayGuardConsole, definition: EntityDef, uid: str) -> None:
        super().__init__(console, definition)
        self.uid = uid
        self._attr_unique_id = f"{console.console_id}_account_{uid}_{definition.key.removeprefix('account_')}"
        self._attr_translation_placeholders = self._placeholders()

    def _placeholders(self) -> dict[str, str]:
        return {"account": self.console.account_name(self.uid) or self.uid[:8]}

    @callback
    def _handle_update(self) -> None:
        placeholders = self._placeholders()
        if placeholders != self._attr_translation_placeholders:  # named once the names arrive
            self._attr_translation_placeholders = placeholders
            self.__dict__.pop("name", None)  # Entity.name is cached; HA's own _attr_ setters clear it so
        super()._handle_update()

    @property
    def available(self) -> bool:
        known = (
            self.console.activity is not None if self.definition.key == "account_today" else play.window(self.console)
        )
        return bool(known) and self.shown

    @property
    def native_value(self) -> int | None:
        if self.definition.key == "account_today":
            rows = (self.console.activity or {}).get("per_account")
            if not isinstance(rows, list):
                return None  # not read
            return sum(
                m
                for r in rows
                if isinstance(r, dict)
                and str(r.get("uid")).upper() == self.uid
                and (m := play.as_minutes(r.get("min"))) is not None
            )
        table = play.table(self.console, "accounts", "uid", "per_account")
        return None if table is None else sum(table.get(self.uid, []))
