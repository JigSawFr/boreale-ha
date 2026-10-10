"""Finding a console: MQTT discovery, by hand, the options."""

from __future__ import annotations

import json

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from custom_components.playguard.const import CONF_CONSOLE_ID, CONF_PREFIX, CONF_TAKE_OVER, DOMAIN

from .conftest import CONSOLE_ID, fixture


def _info(topic: str, payload: str) -> MqttServiceInfo:
    return MqttServiceInfo(
        topic=topic, payload=payload, qos=0, retain=True, subscribed_topic="playguard/+/state", timestamp=0
    )


async def test_discovered(hass: HomeAssistant) -> None:
    info = _info(f"playguard/{CONSOLE_ID}/state", json.dumps(fixture("state.json")))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": "Salon", "console_id": CONSOLE_ID}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Salon"
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "playguard"}
    assert result["options"] == {CONF_TAKE_OVER: True}
    assert result["result"].unique_id == CONSOLE_ID

    # The retained state comes again at every start: already set up.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_ignores_other_messages(hass: HomeAssistant) -> None:
    for topic, payload in (
        ("playguard/NOT-AN-ID/state", json.dumps(fixture("state.json"))),
        (f"playguard/{CONSOLE_ID}/state", ""),  # cleared
        (f"playguard/{CONSOLE_ID}/state", "not json"),
        (f"playguard/{CONSOLE_ID}/state", json.dumps({"a": 1})),  # no schema: not PlayGuard's
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=_info(topic, payload)
        )
        assert result["type"] is FlowResultType.ABORT, topic
        assert result["reason"] == "invalid_discovery_info"


async def test_by_hand(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: "nope", CONF_PREFIX: "playguard"}
    )
    assert result["errors"] == {CONF_CONSOLE_ID: "invalid_console_id"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: "A1B2C3D4", CONF_PREFIX: "bad/+/prefix"}
    )
    assert result["errors"] == {CONF_PREFIX: "invalid_prefix"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONSOLE_ID: " A1B2C3D4 ", CONF_PREFIX: "home/playguard/"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CONSOLE_ID: CONSOLE_ID, CONF_PREFIX: "home/playguard"}


async def test_options(hass: HomeAssistant, setup) -> None:
    result = await hass.config_entries.options.async_init(setup.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_TAKE_OVER: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert setup.options == {CONF_TAKE_OVER: False}
