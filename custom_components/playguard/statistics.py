"""Finished days as long-term statistics.

The console publishes each finished day once (`activity/<date>`, retained for
14 days). Each becomes one point per day in the recorder's external
statistics: the day's total, and each game's, in minutes, at the day's local
midnight. Months of history in Home Assistant, with no database of ours.
Importing the same day again replaces it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import PlayGuardConsole

_LOGGER = logging.getLogger(__name__)


def total_id(console_id: str) -> str:
    """The statistic of a console's daily total."""
    return f"{DOMAIN}:{console_id}_play_time"


def game_id(console_id: str, app_id: str) -> str:
    """The statistic of one game's daily time."""
    return f"{DOMAIN}:{console_id}_game_{app_id.lower()}"


def day_start(date: str, time_zone) -> datetime | None:
    """A date's local midnight, in UTC, on a whole hour (statistics are hourly)."""
    try:
        day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=time_zone)
    except ValueError:
        return None
    start = dt_util.as_utc(day)
    return start - timedelta(minutes=start.minute, seconds=start.second, microseconds=start.microsecond)


def _minutes(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


async def async_import_days(hass: HomeAssistant, console: PlayGuardConsole) -> None:
    """Imports every finished day known."""
    if "recorder" not in hass.config.components:
        return
    from homeassistant.components.recorder.models import (  # noqa: PLC0415
        StatisticData,
        StatisticMeanType,
        StatisticMetaData,
    )
    from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
        async_add_external_statistics,
    )

    time_zone = dt_util.get_time_zone(hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
    days: list[tuple[datetime, dict]] = []
    for date, doc in sorted(console.finals.items()):
        start = day_start(date, time_zone)
        if start is not None and doc.get("final", True):
            days.append((start, doc))
    if not days:
        return

    def meta(statistic_id: str, name: str) -> StatisticMetaData:
        return StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class="duration",
            unit_of_measurement=UnitOfTime.MINUTES,
        )

    def point(start: datetime, minutes: float) -> StatisticData:
        return StatisticData(start=start, mean=minutes, min=minutes, max=minutes)

    totals = [point(start, m) for start, doc in days if (m := _minutes(doc.get("total_min"))) is not None]
    if totals:
        async_add_external_statistics(hass, meta(total_id(console.console_id), f"{console.name} play time"), totals)

    # Each game played on one of these days, with 0 on the others.
    games: dict[str, dict[datetime, float]] = {}
    for start, doc in days:
        for app in doc.get("per_app") or []:
            app_id = app.get("app_id") if isinstance(app, dict) else None
            minutes = _minutes(app.get("min")) if isinstance(app, dict) else None
            if isinstance(app_id, str) and app_id.isalnum() and minutes is not None:
                games.setdefault(app_id, {})[start] = minutes
    for app_id, played in games.items():
        name = console.game_name(app_id) or app_id
        rows = [point(start, played.get(start, 0.0)) for start, _ in days]
        async_add_external_statistics(hass, meta(game_id(console.console_id, app_id), f"{console.name} — {name}"), rows)
    _LOGGER.debug("%s: %d day(s), %d game(s) imported as statistics", console.base, len(days), len(games))
