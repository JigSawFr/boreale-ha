"""Sensors: play time, what is being played, the console."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlayGuardConfigEntry
from .entities import for_platform
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
    }
    async_add_entities(classes.get(d.key, PlayGuardSensor)(console, d) for d in for_platform(Platform.SENSOR))


class PlayGuardSensor(PlayGuardEntity, SensorEntity):
    """A value of the state."""

    def __init__(self, console, definition) -> None:
        super().__init__(console, definition)
        if definition.unit:
            self._attr_native_unit_of_measurement = definition.unit
        if definition.device_class:
            self._attr_device_class = SensorDeviceClass(definition.device_class)
        if definition.state_class:
            self._attr_state_class = SensorStateClass(definition.state_class)

    @property
    def native_value(self) -> Any:
        value = self.read()
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
        return self.console.week is not None

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
