"""The integration before Boréale ("playguard"): its entries taken over."""

from __future__ import annotations

import json

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.boreale.const import (
    CONF_CONSOLE_ID,
    CONF_IMPORTED,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_TREE,
    DOMAIN,
    LEGACY_DOMAIN,
)

from .conftest import BASE, CONSOLE_ID, fixture, publish


@pytest.fixture
def legacy(hass: HomeAssistant) -> MockConfigEntry:
    """A console set up with the integration before Boréale (an entry from
    before its migration to 1.3), its device and some of its entities."""
    entry = MockConfigEntry(
        domain=LEGACY_DOMAIN,
        title="Salon",
        unique_id=CONSOLE_ID,
        data={CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"},
        options={CONF_TAKE_OVER: True, "game_sensors": True},
        minor_version=1,
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(LEGACY_DOMAIN, CONSOLE_ID)}, name="Salon"
    )
    registry = er.async_get(hass)
    for platform, key in (
        ("number", "limit_mon"),
        ("switch", "unlocked"),  # retired in 1.3
        ("sensor", "game_0100000000010000"),  # no sensor per game since 1.2
    ):
        registry.async_get_or_create(
            platform, LEGACY_DOMAIN, f"{CONSOLE_ID}_{key}", config_entry=entry, device_id=device.id
        )
    return entry


def _discovery(doc: dict) -> MqttServiceInfo:
    return MqttServiceInfo(
        topic=f"{BASE}/state", payload=json.dumps(doc), qos=0, retain=True,
        subscribed_topic="playguard/+/state", timestamp=0,
    )  # fmt: skip


async def test_taken_over(hass: HomeAssistant, mqtt_mock, legacy: MockConfigEntry, state: dict) -> None:
    """The console found again: its entry is taken over without asking, with
    its device and its entities (their ids kept), then the old one goes."""
    before = er.async_get(hass).async_get_entity_id("number", LEGACY_DOMAIN, f"{CONSOLE_ID}_limit_mon")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_discovery(fixture("state.json"))
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.title == "Salon" and entry.unique_id == CONSOLE_ID
    assert entry.data == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard", CONF_TREE: 1}
    assert CONF_IMPORTED not in entry.data
    assert entry.options == {CONF_TAKE_OVER: True}  # the option of 1.1 gone
    assert hass.config_entries.async_get_entry(legacy.entry_id) is None

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    assert device is not None and device.config_entry_id == entry.entry_id
    registry = er.async_get(hass)
    limit_id = registry.async_get_entity_id("number", DOMAIN, f"{CONSOLE_ID}_limit_mon")
    assert limit_id is not None and limit_id == before
    limit = registry.async_get(limit_id)
    assert limit is not None and limit.platform == DOMAIN and limit.config_entry_id == entry.entry_id
    assert limit.device_id == device.id and limit.unique_id == f"{CONSOLE_ID}_limit_mon"
    assert registry.async_get_entity_id("switch", DOMAIN, f"{CONSOLE_ID}_unlocked") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{CONSOLE_ID}_game_0100000000010000") is None
    assert not er.async_entries_for_config_entry(registry, legacy.entry_id)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "taken_over")
    assert issue is not None and issue.translation_key == "taken_over"  # the old integration is gone

    # The entity it took over is the one the integration fills.
    publish(hass, "state", state, retain=True)
    await hass.async_block_till_done()
    assert hass.states.get(limit_id).state == "120"


class _LegacyFlow(config_entries.ConfigFlow):
    """The old integration's flow: what ignoring a console needs."""

    VERSION = 1


async def test_taken_over_from_the_installed_one(
    hass: HomeAssistant, mqtt_mock, legacy: MockConfigEntry, state: dict
) -> None:
    """The old integration still installed and running the console: unloaded
    first, its console then ignored there (it does not offer it again), and
    the repair says to remove it."""
    unloaded: list[str] = []

    async def _unload(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
        unloaded.append(entry.entry_id)
        return True

    mock_integration(
        hass,
        MockModule(LEGACY_DOMAIN, async_setup_entry=lambda *_: _true(), async_unload_entry=_unload),
        built_in=False,
    )
    mock_platform(hass, f"{LEGACY_DOMAIN}.config_flow", None)
    with mock_config_flow(LEGACY_DOMAIN, _LegacyFlow):
        assert await hass.config_entries.async_setup(legacy.entry_id)
        assert legacy.state is config_entries.ConfigEntryState.LOADED
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_discovery(state)
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert unloaded == [legacy.entry_id]
    [ignored] = hass.config_entries.async_entries(LEGACY_DOMAIN, include_ignore=True)
    assert ignored.source == config_entries.SOURCE_IGNORE and ignored.unique_id == CONSOLE_ID
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "taken_over")
    assert issue is not None and issue.translation_key == "taken_over_installed"


async def _true() -> bool:
    return True


async def test_taken_over_when_added_by_hand(hass: HomeAssistant, mqtt_mock, legacy: MockConfigEntry) -> None:
    """Confirmed from Discovered, or added by hand: the same."""
    state = fixture("state.json")
    flow = hass.config_entries.flow
    result = await flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "manual"
    flow_id = result["flow_id"]
    task = hass.async_create_task(
        flow.async_configure(flow_id, {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"})
    )
    for _ in range(100):
        if any(c.args[0] == f"{BASE}/state" for c in mqtt_mock.async_subscribe.call_args_list):
            break
        await hass.async_block_till_done()
    publish(hass, "state", state, retain=True)
    result = await task
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(legacy.entry_id) is None


async def test_legacy_actions(hass: HomeAssistant, mqtt_mock, setup) -> None:
    """The old actions still answer, each one used naming the new one."""
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), setup.entry_id)
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        LEGACY_DOMAIN, "add_bonus_time", {"device_id": device.id, "minutes": 15}, blocking=True
    )
    assert [c.args for c in mqtt_mock.async_publish.call_args_list] == [(f"{BASE}/add_bonus_time/set", "15", 1, True)]
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "legacy_action_add_bonus_time")
    assert issue is not None and issue.translation_placeholders == {
        "old": "playguard.add_bonus_time",
        "new": "boreale.add_bonus_time",
    }
    response = await hass.services.async_call(
        LEGACY_DOMAIN, "get_play_time", {"device_id": device.id}, blocking=True, return_response=True
    )
    assert response["console"] == "Salon"
