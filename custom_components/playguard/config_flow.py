"""Finding the consoles: by MQTT discovery, or by hand."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import voluptuous as vol

from .const import CONF_CONSOLE_ID, CONF_PREFIX, CONF_TAKE_OVER, CONSOLE_ID_RE, DEFAULT_PREFIX, DOMAIN


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
        try:
            doc = json.loads(discovery_info.payload) if discovery_info.payload else None
        except ValueError:
            doc = None
        if not isinstance(doc, dict) or "schema" not in doc:
            return self.async_abort(reason="invalid_discovery_info")
        self._prefix, self._console_id = parts[0], parts[1]
        await self.async_set_unique_id(self._console_id)
        # Already set up: nothing to reload (its subscriptions get the same state).
        self._abort_if_unique_id_configured(reload_on_update=False)
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
        """A console by its id (Preferences › Remote access › Console id)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            console_id = user_input[CONF_CONSOLE_ID].strip().lower()
            prefix = user_input[CONF_PREFIX].strip().strip("/")
            if not CONSOLE_ID_RE.match(console_id):
                errors[CONF_CONSOLE_ID] = "invalid_console_id"
            else:
                try:
                    valid_publish_topic(f"{prefix}/{console_id}/state")
                except vol.Invalid:
                    errors[CONF_PREFIX] = "invalid_prefix"
            if not errors:
                self._console_id, self._prefix = console_id, prefix
                self._name = "Nintendo Switch"
                await self.async_set_unique_id(console_id)
                self._abort_if_unique_id_configured()
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
    """Whether the console's own discovery stays off (the entry reloads when
    it changes)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TAKE_OVER, default=self.config_entry.options.get(CONF_TAKE_OVER, True)): bool,
                }
            ),
        )
