"""Sensors: play time, what is being played, the console, one per game."""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlayGuardConfigEntry
from .const import GAME_SENSORS_ALL, GAME_SENSORS_NONE, RECENT_DAYS
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
    }
    async_add_entities(classes.get(d.key, PlayGuardSensor)(console, d) for d in for_platform(Platform.SENSOR))

    # A sensor per game the option wants, as the games document lists them:
    # added when a game first qualifies. With every game, one is kept when it
    # is no longer listed (its play time stays); otherwise the sensors of the
    # games that no longer qualify go (their statistics stay).
    registry = er.async_get(hass)
    prefix = f"{console.console_id}_game_"
    known: set[str] = set()  # the unique ids' game part (the id in lower case)
    seen: list[dict | None] = [None]  # the games document last looked at

    @callback
    def _update_games() -> None:
        if console.games is seen[0] or (wanted := _wanted_games(console)) is None:
            return
        seen[0] = console.games
        new = [app_id for key, app_id in wanted.items() if key not in known]
        known.update(app_id.lower() for app_id in new)
        if new:
            async_add_entities(GameSensor(console, app_id) for app_id in new)
        if console.game_sensors == GAME_SENSORS_ALL:
            return
        for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
            key = reg.unique_id[len(prefix) :]
            if reg.domain == Platform.SENSOR and reg.unique_id.startswith(prefix) and key not in wanted:
                registry.async_remove(reg.entity_id)
                known.discard(key)

    _update_games()
    entry.async_on_unload(console.async_add_listener(_update_games))


def _wanted_games(console: PlayGuardConsole) -> dict[str, str] | None:
    """The games that get a sensor, {id in lower case: id}; None while there
    is no games document (or one that is not)."""
    games = (console.games or {}).get("games")
    if not isinstance(games, dict):
        return None
    if console.game_sensors == GAME_SENSORS_NONE:
        return {}
    since = 0
    if console.game_sensors != GAME_SENSORS_ALL:
        # Played in the days before the console's list (not before now: a
        # console left asleep keeps its sensors).
        since = (_posix(console.games.get("ts")) or int(time.time())) - RECENT_DAYS * 86400
    return {
        app_id.lower(): app_id
        for app_id, game in games.items()
        if isinstance(game, dict) and _posix(game.get("last_played")) >= since
    }


def _posix(value: Any) -> int:
    """POSIX seconds, 0 unknown."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _timestamp(value: Any) -> datetime | None:
    """POSIX seconds as a date, None unknown."""
    return dt_util.utc_from_timestamp(value) if _posix(value) else None


class PlayGuardSensor(PlayGuardEntity, SensorEntity):
    """A value of the state."""

    _keeps_value = True

    def __init__(self, console, definition) -> None:
        super().__init__(console, definition)
        if definition.unit:
            self._attr_native_unit_of_measurement = definition.unit
        if definition.device_class:
            self._attr_device_class = SensorDeviceClass(definition.device_class)
        if definition.state_class:
            self._attr_state_class = SensorStateClass(definition.state_class)
        if definition.options:
            self._attr_options = list(definition.options)

    @property
    def native_value(self) -> Any:
        value = self.read()
        if self.definition.device_class == SensorDeviceClass.TIMESTAMP:
            return _timestamp(value)
        if self.definition.options and value not in self.definition.options:
            return None  # an option this integration does not know (a newer console)
        return value if isinstance(value, (int, float, str)) and not isinstance(value, bool) else None


def _games(console, per_app: list | None) -> dict[str, int]:
    """{game: minutes}, the most played first."""
    out: dict[str, int] = {}
    for app in sorted(per_app or [], key=lambda a: -(a.get("s") or 0) if isinstance(a, dict) else 0):
        if isinstance(app, dict) and isinstance(app.get("app_id"), str):
            out[console.game_name(app["app_id"]) or app["app_id"]] = app.get("min") or 0
    return out


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
    _unrecorded_attributes = frozenset({"games"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"games": _games(self.console, (self.console.activity or {}).get("per_app"))}


class WeekSensor(PlayGuardSensor):
    """The last seven days' play time (PlayGuard's week table), with each day's."""

    _unrecorded_attributes = frozenset({"days", "games"})

    @property
    def available(self) -> bool:
        return self.console.week is not None and self.shown

    def _days(self) -> dict[str, int]:
        week = self.console.week or {}
        days = week.get("days") or []
        totals = [0] * len(days)
        for game in week.get("games") or []:
            for i, minutes in enumerate((game or {}).get("min") or []):
                if i < len(totals) and isinstance(minutes, int):
                    totals[i] += minutes
        return dict(zip(days, totals, strict=False))

    @property
    def native_value(self) -> int | None:
        return sum(self._days().values()) if self.console.week else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        week = self.console.week or {}
        games = {
            self.console.game_name(g.get("app_id")) or g.get("app_id"): sum(
                m for m in (g.get("min") or []) if isinstance(m, int)
            )
            for g in week.get("games") or []
            if isinstance(g, dict) and g.get("app_id")
        }
        return {"days": self._days(), "games": dict(sorted(games.items(), key=lambda kv: -kv[1]))}


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


class GameSensor(PlayGuardEntity, SensorEntity):
    """One game's play time since it was first played (every account), with
    its launches, when it was first and last played, its version. No state
    class: the game's long-term statistic is the integration's own
    (statistics.py), from the play log's finished days."""

    _keeps_value = True

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "game"

    def __init__(self, console: PlayGuardConsole, app_id: str) -> None:
        super().__init__(console, EntityDef(key=f"game_{app_id.lower()}", platform=Platform.SENSOR, topic="games"))
        self.app_id = app_id
        self._attr_translation_key = "game"
        self._attr_translation_placeholders = {"game": self._game().get("name") or app_id}

    def _game(self) -> dict:
        games = (self.console.games or {}).get("games")
        game = games.get(self.app_id) if isinstance(games, dict) else None
        return game if isinstance(game, dict) else {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._game())

    @property
    def native_value(self) -> int | None:
        value = self._game().get("total_min")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        game = self._game()
        first, last = _timestamp(game.get("first_played")), _timestamp(game.get("last_played"))
        return {
            "app_id": self.app_id,
            "installed": game.get("installed"),
            "version": game.get("version"),
            "launches": game.get("launches"),
            "first_played": first.isoformat() if first else None,
            "last_played": last.isoformat() if last else None,
        }
