"""A Lantern bridge: found by its address, polled for its status and figures."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.boreale.bridge import EVERY, parse_metrics
from custom_components.boreale.const import CONF_BRIDGE_ID, CONF_KIND, CONF_URL, DOMAIN, KIND_BRIDGE
from custom_components.boreale.diagnostics import async_get_config_entry_diagnostics

URL = "http://192.168.1.20:8080"
BRIDGE = "0c9c2a8e-5d3a-4c7e-8b0a-6f1d2e3c4b5a"
HEALTHZ = {"status": "ok", "version": "0.1.0", "uid": BRIDGE}
METRICS = """# HELP lantern_bridge_titles_served Titles the library offers.
# TYPE lantern_bridge_titles_served gauge
lantern_bridge_titles_served 12
lantern_bridge_files{state="hashed"} 30
lantern_bridge_files{state="pending"} 3
lantern_bridge_transfers_active 1
lantern_bridge_errors_total 4
lantern_bridge_source_up{source="games"} 1
"""
INTEGRATION = Path(__file__).parent.parent / "custom_components" / "boreale"


def _bridge(aioclient_mock: AiohttpClientMocker, *, healthz=HEALTHZ, status=200, metrics: str | None = METRICS) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/healthz", json=healthz, status=status)
    aioclient_mock.get(f"{URL}/metrics", text=metrics or "", status=200 if metrics is not None else 404)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Lantern bridge",
        unique_id=f"bridge_{BRIDGE}",
        data={CONF_KIND: KIND_BRIDGE, CONF_URL: URL, CONF_BRIDGE_ID: BRIDGE},
        minor_version=3,
    )


async def _set_up(hass: HomeAssistant, mqtt_mock) -> MockConfigEntry:
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, platform: str, key: str):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"bridge_{BRIDGE}_bridge_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


def test_the_metrics_are_read_by_name_and_state() -> None:
    figures = parse_metrics(METRICS + 'lantern_bridge_source_files{source="a",state="pending"} 2\nnot a sample\n')
    assert figures["titles_served"] == 12 and figures["files_pending"] == 3 and figures["files_hashed"] == 30
    assert figures["source_files_pending"] == 2 and figures["errors_total"] == 4
    assert parse_metrics("lantern_bridge_x nope\n") == {}


async def _flow(hass: HomeAssistant, url: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "bridge"})
    assert result["step_id"] == "bridge"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: url})


async def test_added_by_its_address(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    _bridge(aioclient_mock)
    result = await _flow(hass, "192.168.1.20:8080/")  # no scheme and a slash: both are mended
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_KIND: KIND_BRIDGE, CONF_URL: URL, CONF_BRIDGE_ID: BRIDGE}
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "titles").state == "12.0"


async def test_an_address_that_does_not_answer_or_is_no_bridge(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/healthz", status=404)
    assert (await _flow(hass, URL))["errors"] == {CONF_URL: "cannot_connect"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/healthz", json={"status": "ok"})  # a far answer: no id
    assert (await _flow(hass, URL))["errors"] == {CONF_URL: "not_a_bridge"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/healthz", text="<html>")
    assert (await _flow(hass, URL))["errors"] == {CONF_URL: "cannot_connect"}


async def test_the_same_bridge_is_not_added_twice_but_follows_its_address(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    _bridge(aioclient_mock)
    entry = await _set_up(hass, mqtt_mock)
    aioclient_mock.get("http://10.0.0.5:8080/healthz", json=HEALTHZ)
    result = await _flow(hass, "http://10.0.0.5:8080")
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert entry.data[CONF_URL] == "http://10.0.0.5:8080"


async def test_reconfigured_at_another_address_only_for_the_same_bridge(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    _bridge(aioclient_mock)
    entry = await _set_up(hass, mqtt_mock)
    aioclient_mock.get("http://10.0.0.6:8080/healthz", json={**HEALTHZ, "uid": "other"})
    aioclient_mock.get("http://10.0.0.7:8080/healthz", json=HEALTHZ)
    aioclient_mock.get("http://10.0.0.7:8080/metrics", text=METRICS)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_bridge"
    for url, error in (("http://10.0.0.6:8080", "other_bridge"), ("http://10.0.0.9:8080", "cannot_connect")):
        if error == "cannot_connect":
            aioclient_mock.get(f"{url}/healthz", status=500)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: url})
        assert result["errors"] == {CONF_URL: error}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: "http://10.0.0.7:8080"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == "http://10.0.0.7:8080"


async def test_its_status_and_figures(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    _bridge(aioclient_mock)
    await _set_up(hass, mqtt_mock)
    assert _state(hass, "sensor", "status").state == "ok" and _state(hass, "sensor", "version").state == "0.1.0"
    assert _state(hass, "sensor", "files_pending").state == "3.0" and _state(hass, "sensor", "errors").state == "4.0"
    assert _state(hass, "binary_sensor", "reachable").state == "on"


async def test_without_metrics_only_the_status_and_the_version_come(
    hass: HomeAssistant, mqtt_mock, aioclient_mock
) -> None:
    _bridge(aioclient_mock, metrics=None)
    await _set_up(hass, mqtt_mock)
    assert _state(hass, "sensor", "status").state == "ok"
    assert _state(hass, "sensor", "titles").state == "unavailable"


async def test_a_failing_bridge_and_one_that_goes_away(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    _bridge(aioclient_mock, healthz={**HEALTHZ, "status": "fail"}, status=503)
    entry = await _set_up(hass, mqtt_mock)
    assert _state(hass, "sensor", "status").state == "fail"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/healthz", exc=TimeoutError)
    async_fire_time_changed(hass, dt_util.utcnow() + EVERY * 2)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", "reachable").state == "off"
    assert _state(hass, "sensor", "status").state == "unavailable"
    assert entry.state is ConfigEntryState.LOADED


async def test_a_bridge_not_there_yet_is_retried(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/healthz", exc=TimeoutError)
    entry = await _set_up(hass, mqtt_mock)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unloaded_and_removed_like_any_entry(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    _bridge(aioclient_mock)
    entry = await _set_up(hass, mqtt_mock)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_remove(entry.entry_id) == {"require_restart": False}


async def test_diagnostics_do_not_give_the_address(hass: HomeAssistant, mqtt_mock, aioclient_mock) -> None:
    _bridge(aioclient_mock)
    entry = await _set_up(hass, mqtt_mock)
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert report["status"] == "ok" and report["figures"]["titles_served"] == 12
    assert URL not in json.dumps(report) and BRIDGE not in json.dumps(report)


def test_every_bridge_entity_is_named_and_has_its_icon() -> None:
    names = json.loads((INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))["entity"]
    for platform, keys in (
        ("sensor", ["status", "version", "titles", "files_pending", "transfers", "errors"]),
        ("binary_sensor", ["reachable"]),
    ):
        for key in keys:
            assert f"bridge_{key}" in names[platform] and f"bridge_{key}" in icons[platform], key
