"""The console's answer to an order: the action waits for it, a refusal that
comes later is a notification."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from unittest.mock import patch

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.playguard.const import CONF_NOTIFY_REFUSED, CONF_TAKE_OVER, DOMAIN

from .conftest import CONSOLE_ID, publish

NOTIFICATION = f"{DOMAIN}_{CONSOLE_ID}_refused"


@pytest.fixture
def wait():
    """The action waits for the answer (long enough for any test)."""
    with patch("custom_components.playguard.coordinator.ORDER_TIMEOUT", 30):
        yield


def _event(event_type: str, entity: str, payload: str, reason: str | None = None, rc: str | None = None) -> dict:
    return {"schema": 1, "source": "agent", "ts": 1, "event_type": event_type, "entity": entity,
            "payload": payload, "reason": reason, "rc": rc}  # fmt: skip


def _device_id(hass: HomeAssistant) -> str:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, CONSOLE_ID), entry.entry_id)
    assert device
    return device.id


def _id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


def _notification(hass: HomeAssistant) -> dict[str, Any] | None:
    return persistent_notification._async_get_or_create_notifications(hass).get(NOTIFICATION)


async def _answered(hass: HomeAssistant, call: Coroutine[Any, Any, Any], *answers: dict) -> None:
    """Runs an action, the console answering once its order is out."""
    task = asyncio.ensure_future(call)
    console = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    async with asyncio.timeout(5):
        while not console._waiters:  # it waits for the answer
            await asyncio.sleep(0)
        for answer in answers:
            publish(hass, "event", answer)
        await task


async def test_applied(hass: HomeAssistant, setup, wait) -> None:
    call = hass.services.async_call(
        DOMAIN, "add_bonus_time", {"device_id": _device_id(hass), "minutes": 15}, blocking=True
    )
    # Another order's answer, then another value's, then its own.
    await _answered(
        hass,
        call,
        _event("command_applied", "limit_mon", "15"),
        _event("command_rejected", "add_bonus_time", "30", "busy"),
        _event("command_applied", "add_bonus_time", "15"),
    )
    await hass.async_block_till_done()
    # The refusal of the other value, which no action waited for, was a
    # notification; its own order applied took it away.
    assert _notification(hass) is None


async def test_refused(hass: HomeAssistant, setup, wait) -> None:
    call = hass.services.async_call(
        "number", "set_value", {"entity_id": _id(hass, "number", "limit_mon"), "value": 90}, blocking=True
    )
    with pytest.raises(HomeAssistantError) as err:
        await _answered(hass, call, _event("command_rejected", "limit_mon", "90", "pctl_error", "0x1188E"))
    assert err.value.translation_key == "refused"
    assert err.value.translation_placeholders == {
        "name": "Salon",
        "reason": "the console refused (result code 0x1188E)",
    }
    await hass.async_block_till_done()
    assert _notification(hass) is None  # said by the action


async def test_refused_later(hass: HomeAssistant, setup, wait) -> None:
    """Waiting for PlayGuard: the action returns; refused then, a notification,
    which an order applied takes away."""
    call = hass.services.async_call("button", "press", {"entity_id": _id(hass, "button", "sync_now")}, blocking=True)
    await _answered(hass, call, _event("command_waiting", "sync_now", "PRESS", "waiting_for_confirmation"))
    publish(hass, "event", _event("command_rejected", "sync_now", "PRESS", "not_confirmed"))
    await hass.async_block_till_done()
    notification = _notification(hass)
    assert notification["title"] == "Salon refused an order"
    name = hass.states.get(_id(hass, "button", "sync_now")).name
    assert notification["message"] == f"{name}: not confirmed on the console, or the PIN was not entered."

    publish(hass, "event", _event("command_rejected", "lock_now", "PRESS", "something_new"))
    await hass.async_block_till_done()
    assert _notification(hass)["message"].endswith(": something_new.")  # a reason it does not know, as is

    # The integration's own order is not the user's.
    publish(hass, "event", _event("command_applied", "discovery", "OFF"))
    await hass.async_block_till_done()
    assert _notification(hass) is not None
    publish(hass, "event", _event("command_applied", "vr_restricted", "ON"))
    await hass.async_block_till_done()
    assert _notification(hass) is None


async def test_no_answer(hass: HomeAssistant, setup, mqtt_mock) -> None:
    """No answer in time: the action returns, the order waits on the broker."""
    with patch("custom_components.playguard.coordinator.ORDER_TIMEOUT", 0.01):
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": _device_id(hass)}, blocking=True)
    assert setup.runtime_data._waiters == []


async def test_asleep(hass: HomeAssistant, setup, wait) -> None:
    """The console off the broker: nothing to wait for."""
    publish(hass, "availability", "offline")
    await hass.async_block_till_done()
    async with asyncio.timeout(5):
        await hass.services.async_call(DOMAIN, "sync_now", {"device_id": _device_id(hass)}, blocking=True)


async def test_no_notification(hass: HomeAssistant, setup) -> None:
    hass.config_entries.async_update_entry(setup, options={CONF_TAKE_OVER: True, CONF_NOTIFY_REFUSED: False})
    await hass.async_block_till_done()
    publish(hass, "event", _event("command_rejected", "sync_now", "PRESS", "busy"))
    await hass.async_block_till_done()
    assert _notification(hass) is None
