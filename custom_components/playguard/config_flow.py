"""Finding the consoles: by MQTT discovery, or by hand."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage, valid_publish_topic
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import voluptuous as vol

from .const import CONF_CONSOLE_ID, CONF_KEEP_VALUES, CONF_PREFIX, CONF_TAKE_OVER, CONSOLE_ID_RE, DEFAULT_PREFIX, DOMAIN

# How long a flow waits for the console's state on the broker. Retained, it
# comes at once when the console ever published, even asleep.
STATE_TIMEOUT = 10.0

RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_PREFIX): str})
OPTIONS_SCHEMA = vol.Schema(
    {vol.Required(CONF_TAKE_OVER, default=True): bool, vol.Required(CONF_KEEP_VALUES, default=True): bool}
)


def _valid_prefix(prefix: str, console_id: str) -> bool:
    try:
        valid_publish_topic(f"{prefix}/{console_id}/state")
    except vol.Invalid:
        return False
    return True


def _state(payload: str | bytes) -> dict | None:
    """A PlayGuard state document, else None."""
    try:
        doc = json.loads(payload) if payload else None
    except ValueError:
        return None
    return doc if isinstance(doc, dict) and "schema" in doc else None


def _posix(value: Any) -> int | None:
    """A state's `ts` (the POSIX time it was built), else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _moved_back(entry: ConfigEntry | None, prefix: str, doc: dict) -> bool:
    """Whether a known console's entry follows it to `prefix`: only for a
    state newer than the last one its coordinator read. A state left
    retained under the console's former prefix is older, and an entry not
    loaded yet waits for the console's next state (every poll interval)."""
    if entry is None or entry.data.get(CONF_PREFIX, DEFAULT_PREFIX) == prefix:
        return False
    if entry.state is not ConfigEntryState.LOADED or (console := getattr(entry, "runtime_data", None)) is None:
        return False
    found, last = _posix(doc.get("ts")), _posix((console.state or {}).get("ts"))
    return found is not None and last is not None and last < found


async def _async_wait_for_state(hass: HomeAssistant, prefix: str, console_id: str) -> dict | None:
    """The console's state on the broker under this prefix, or None."""
    received: asyncio.Future[dict] = hass.loop.create_future()

    @callback
    def _on_state(msg: ReceiveMessage) -> None:
        if (doc := _state(msg.payload)) is not None and not received.done():
            received.set_result(doc)

    unsubscribe = await mqtt.async_subscribe(hass, f"{prefix}/{console_id}/state", _on_state, qos=1)
    try:
        async with asyncio.timeout(STATE_TIMEOUT):
            return await received
    except TimeoutError:
        return None
    finally:
        unsubscribe()


class PlayGuardConfigFlow(ConfigFlow, domain=DOMAIN):
    """A console per entry, its id as the unique id."""

    VERSION = 1

    def __init__(self) -> None:
        self._console_id = ""
        self._prefix = DEFAULT_PREFIX
        self._name = ""

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> ConfigFlowResult:
        """A console published its state (`playguard/<id>/state`, retained: at
        every start of Home Assistant too)."""
        parts = discovery_info.topic.split("/")
        if len(parts) != 3 or parts[2] != "state" or not CONSOLE_ID_RE.match(parts[1]):
            return self.async_abort(reason="invalid_discovery_info")
        if (doc := _state(discovery_info.payload)) is None:
            return self.async_abort(reason="invalid_discovery_info")
        self._prefix, self._console_id = parts[0], parts[1]
        entry = await self.async_set_unique_id(self._console_id)
        # Already set up: the entry follows the console back to this prefix
        # (and reloads) only when the state is newer than its own.
        moved = _moved_back(entry, self._prefix, doc)
        self._abort_if_unique_id_configured(updates={CONF_PREFIX: self._prefix} if moved else None)
        self._name = ((doc.get("console") or {}).get("name")) or "Nintendo Switch"
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add the console found?"""
        if user_input is not None:
            return self._create()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._name, "console_id": self._console_id},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """A console by its id (Preferences › Remote access › Console id),
        once its state is seen on the broker."""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_ready")
        errors: dict[str, str] = {}
        if user_input is not None:
            console_id = user_input[CONF_CONSOLE_ID].strip().lower()
            prefix = user_input[CONF_PREFIX].strip().strip("/")
            if not CONSOLE_ID_RE.match(console_id):
                errors[CONF_CONSOLE_ID] = "invalid_console_id"
            elif not _valid_prefix(prefix, console_id):
                errors[CONF_PREFIX] = "invalid_prefix"
            if not errors:
                # A discovery of the same console may be waiting: this one goes on.
                await self.async_set_unique_id(console_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                if (doc := await _async_wait_for_state(self.hass, prefix, console_id)) is None:
                    errors["base"] = "no_state"
                else:
                    self._console_id, self._prefix = console_id, prefix
                    self._name = (doc.get("console") or {}).get("name") or "Nintendo Switch"
                    return self._create()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONSOLE_ID): str,
                    vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Another topic prefix (sync.conf's topic_prefix on the console)."""
        entry = self._get_reconfigure_entry()
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_ready")
        errors: dict[str, str] = {}
        if user_input is not None:
            prefix = user_input[CONF_PREFIX].strip().strip("/")
            console_id = entry.data[CONF_CONSOLE_ID]
            if not _valid_prefix(prefix, console_id):
                errors[CONF_PREFIX] = "invalid_prefix"
            elif await _async_wait_for_state(self.hass, prefix, console_id) is None:
                errors["base"] = "no_state"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_PREFIX: prefix})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, {CONF_PREFIX: entry.data.get(CONF_PREFIX, DEFAULT_PREFIX)}
            ),
            description_placeholders={"name": entry.title},
            errors=errors,
        )

    def _create(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._name or "Nintendo Switch",
            data={CONF_CONSOLE_ID: self._console_id, CONF_PREFIX: self._prefix},
            options={CONF_TAKE_OVER: True},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PlayGuardOptionsFlow()


class PlayGuardOptionsFlow(OptionsFlowWithReload):
    """Whether the console's own discovery stays off, and whether the sensors
    keep their last values while the console sleeps (the entry reloads when
    one changes)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, self.config_entry.options),
        )
