"""Finished days as long-term statistics."""

from __future__ import annotations

from datetime import timedelta
from functools import partial

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.playguard.const import DOMAIN
from custom_components.playguard.statistics import day_start, game_id, total_id

from .conftest import CONSOLE_ID, publish


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock: Recorder, enable_custom_integrations: None) -> None:
    """The recorder first: it must start before Home Assistant does."""


def _day(date: str, total: int, games: dict[str, int]) -> dict:
    return {
        "schema": 1,
        "source": "app",
        "ts": 1,
        "local_date": date,
        "final": True,
        "total_s": total * 60,
        "total_min": total,
        "per_app": [{"app_id": a, "s": m * 60, "min": m} for a, m in games.items()],
        "per_account": None,
    }


async def test_finished_days(hass: HomeAssistant, mqtt_mock, entry) -> None:
    await hass.config.async_set_time_zone("Europe/Paris")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    publish(hass, "names", {"schema": 1, "ts": 1, "games": {"0100000000010000": "Super Mario Odyssey"}}, retain=True)
    publish(hass, "activity/2026-10-04", _day("2026-10-04", 90, {"0100000000010000": 60, "01000A10041EA000": 30}), True)
    publish(hass, "activity/2026-10-03", _day("2026-10-03", 45, {"0100000000010000": 45}), True)
    publish(hass, "activity/2026-09-01", "", True)  # cleared by the console: nothing
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    tz = dt_util.get_time_zone("Europe/Paris")
    start = day_start("2026-10-03", tz)
    assert start.isoformat() == "2026-10-02T22:00:00+00:00"  # Paris midnight, summer time

    total, mario, kart = (
        total_id(CONSOLE_ID),
        game_id(CONSOLE_ID, "0100000000010000"),
        game_id(CONSOLE_ID, "01000A10041EA000"),
    )
    stats = await hass.async_add_executor_job(
        statistics_during_period, hass, start, None, {total, mario, kart}, "hour", None, {"mean"}
    )
    assert [r["mean"] for r in stats[total]] == [45.0, 90.0]
    assert [r["mean"] for r in stats[mario]] == [45.0, 60.0]
    assert [r["mean"] for r in stats[kart]] == [0.0, 30.0]  # not played on the 3rd
    metadata = await hass.async_add_executor_job(partial(get_metadata, hass, statistic_ids={total}))
    assert metadata[total][1]["unit_of_measurement"] == "min"


async def test_odd_days(hass: HomeAssistant, mqtt_mock, entry) -> None:
    """A topic that is not a date, a day not finished, entries that are not a game."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    publish(hass, "activity/not-a-date", _day("2026-10-01", 10, {}), True)
    publish(hass, "activity/2026-10-02", {**_day("2026-10-02", 20, {}), "final": False}, True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert not await hass.async_add_executor_job(partial(get_metadata, hass, statistic_source=DOMAIN))

    odd = {**_day("2026-10-04", 0, {}), "total_min": None}
    odd["per_app"] = ["junk", {"app_id": "not-hex!", "min": 5}, {"app_id": "0100000000010000", "min": "x"}]
    odd["per_app"].append({"app_id": "0100000000010000", "min": 5})
    publish(hass, "activity/2026-10-04", odd, True)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    metadata = await hass.async_add_executor_job(partial(get_metadata, hass, statistic_source=DOMAIN))
    assert set(metadata) == {game_id(CONSOLE_ID, "0100000000010000")}  # no total: it had none
