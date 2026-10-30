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
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
import probatio

from .const import (
    BOREALE_PREFIX,
    CONF_CONSOLE_ID,
    CONF_KEEP_VALUES,
    CONF_NOTIFY_REFUSED,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_TREE,
    CONSOLE_ID_RE,
    DEFAULT_PREFIX,
    DOMAIN,
    MODULE,
    tree_prefix,
    tree_topic,
)

# How long a flow waits for the console's state on the broker. Retained, it
# comes at once when the console ever published, even asleep.
STATE_TIMEOUT = 10.0
# How long adding a console by hand listens for the consoles' states, retained
# under a prefix of one level or two, on either tree, before it lists them.
SCAN_TIMEOUT = 3.0
SCAN_TOPICS = ("+/+/state", "+/+/+/state", "+/+/+/+/state")
CONF_CONSOLE = "console"
MANUAL = "manual"  # the list's last choice: another console, by its id

RECONFIGURE_SCHEMA = probatio.Schema({probatio.Required(CONF_PREFIX): str})
OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TAKE_OVER, default=True): bool,
        probatio.Required(CONF_KEEP_VALUES, default=True): bool,
        probatio.Required(CONF_NOTIFY_REFUSED, default=True): bool,
    }
)


def _valid_prefix(prefix: str, console_id: str) -> bool:
    try:
        valid_publish_topic(f"{prefix}/{console_id}/state")
    except probatio.Invalid:
        return False
    return True


def _state(payload: str | bytes | bytearray) -> dict[str, Any] | None:
    """A PlayGuard state document, else None."""
    try:
        doc = json.loads(payload) if payload else None
    except ValueError:
        return None
    return doc if isinstance(doc, dict) and "schema" in doc else None


def _where(topic: str) -> tuple[str, str, int] | None:
    """A state topic's (prefix, console id, tree), else None:
    `<prefix>/<id>/state` (tree 1) or `<prefix>/<id>/playguard/state` (tree 2)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[-1] != "state":
        return None
    tree = 2 if len(parts) >= 4 and parts[-2] == MODULE and CONSOLE_ID_RE.match(parts[-3]) else 1
    parts = parts[: -1 - (tree - 1)]
    if not CONSOLE_ID_RE.match(parts[-1]):
        return None
    return "/".join(parts[:-1]), parts[-1], tree


def _posix(value: Any) -> int | None:
    """A state's `ts` (the POSIX time it was built), else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _moved_back(entry: ConfigEntry | None, prefix: str, tree: int, doc: dict[str, Any]) -> bool:
    """Whether a known console's entry follows it to `prefix`: only for a
    state newer than the last one its coordinator read. A state left
    retained under the console's former prefix is older, and an entry not
    loaded yet waits for the console's next state (every poll interval).
    An entry on tree 1 follows the console to tree 2 by itself."""
    if entry is None:
        return False
    known, known_tree = entry.data.get(CONF_PREFIX, DEFAULT_PREFIX), entry.data.get(CONF_TREE, 1)
    if (known, known_tree) == (prefix, tree) or (known_tree, tree) == (1, 2) and tree_prefix(known) == prefix:
        return False
    if entry.state is not ConfigEntryState.LOADED or (console := getattr(entry, "runtime_data", None)) is None:
        return False
    found, last = _posix(doc.get("ts")), _posix((console.state or {}).get("ts"))
    return found is not None and last is not None and last < found


async def _async_wait_for_state(
    hass: HomeAssistant, prefix: str, console_id: str
) -> tuple[dict[str, Any], str, int] | None:
    """The console's state on the broker under this prefix, on tree 1, or on
    tree 2 where that prefix goes (the old default "playguard" to
    "boreale"): (state, prefix, tree), or None."""
    received: asyncio.Future[tuple[dict[str, Any], str, int]] = hass.loop.create_future()

    @callback
    def _on_state(msg: ReceiveMessage) -> None:
        if (doc := _state(msg.payload)) is not None and (where := _where(msg.topic)) and not received.done():
            received.set_result((doc, where[0], where[2]))

    unsubscribe = [
        await mqtt.async_subscribe(hass, tree_topic(at, console_id, tree, "state"), _on_state, qos=1)
        for at, tree in ((prefix, 1), (tree_prefix(prefix), 2))
    ]
    try:
        async with asyncio.timeout(STATE_TIMEOUT):
            return await received
    except TimeoutError:
        return None
    finally:
        for remove in unsubscribe:
            remove()


async def _async_scan(hass: HomeAssistant) -> dict[str, tuple[str, str, int, int]]:
    """The consoles whose state is on the broker: {id: (prefix, name, ts, tree)},
    the newest state when one is under two prefixes (a console moved)."""
    found: dict[str, tuple[str, str, int, int]] = {}

    @callback
    def _on_state(msg: ReceiveMessage) -> None:
        if (where := _where(msg.topic)) is None or (doc := _state(msg.payload)) is None:
            return
        prefix, console_id, tree = where
        ts = _posix(doc.get("ts")) or 0
        if console_id not in found or found[console_id][2] < ts:
            found[console_id] = (prefix, (doc.get("console") or {}).get("name") or "Nintendo Switch", ts, tree)

    unsubscribe = [await mqtt.async_subscribe(hass, topic, _on_state, qos=0) for topic in SCAN_TOPICS]
    try:
        await asyncio.sleep(SCAN_TIMEOUT)
    finally:
        for remove in unsubscribe:
            remove()
    return found


class PlayGuardConfigFlow(ConfigFlow, domain=DOMAIN):
    """A console per entry, its id as the unique id."""

    VERSION = 1
    # 2: no sensor per game, nor its option (the migration in __init__.py).
    MINOR_VERSION = 3

    def __init__(self) -> None:
        self._console_id = ""
        self._prefix = DEFAULT_PREFIX
        self._tree = 1
        self._name = ""
        self._found: dict[str, tuple[str, str, int, int]] = {}

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> ConfigFlowResult:
        """A console published its state (`playguard/<id>/state`, or
        `boreale/<id>/playguard/state` on Boréale's tree; retained: at every
        start of Home Assistant too)."""
        where = _where(discovery_info.topic)
        if where is None or (doc := _state(discovery_info.payload)) is None:
            return self.async_abort(reason="invalid_discovery_info")
        self._prefix, self._console_id, self._tree = where
        entry = await self.async_set_unique_id(self._console_id)
        # Already set up: the entry follows the console back to this prefix
        # (and reloads) only when the state is newer than its own.
        moved = _moved_back(entry, self._prefix, self._tree, doc)
        self._abort_if_unique_id_configured(
            updates={CONF_PREFIX: self._prefix, CONF_TREE: self._tree} if moved else None
        )
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
        """The consoles on the broker not set up yet, to pick one; another one,
        or none found: by its id."""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_ready")
        if user_input is not None:
            if (console_id := user_input[CONF_CONSOLE]) not in self._found:
                return await self.async_step_manual()
            # A discovery of the same console may be waiting: this one goes on.
            await self.async_set_unique_id(console_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._console_id = console_id
            self._prefix, self._name, _, self._tree = self._found[console_id]
            return self._create()
        configured = self._async_current_ids(include_ignore=False)
        self._found = {k: v for k, v in (await _async_scan(self.hass)).items() if k not in configured}
        if not self._found:
            return await self.async_step_manual()
        options = [
            SelectOptionDict(
                value=k, label=f"{name} ({k})" + ("" if prefix in (DEFAULT_PREFIX, BOREALE_PREFIX) else f", {prefix}")
            )
            for k, (prefix, name, _, _) in sorted(self._found.items(), key=lambda kv: (kv[1][1], kv[0]))
        ]
        options.append(SelectOptionDict(value=MANUAL, label="Another console, by its id"))
        selector = SelectSelector(
            SelectSelectorConfig(options=options, translation_key=CONF_CONSOLE, mode=SelectSelectorMode.LIST)
        )
        return self.async_show_form(
            step_id="user", data_schema=probatio.Schema({probatio.Required(CONF_CONSOLE): selector})
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """A console by its id (Console › Remote access › Console id), once its
        state is seen on the broker."""
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
                if (found := await _async_wait_for_state(self.hass, prefix, console_id)) is None:
                    errors["base"] = "no_state"
                else:
                    doc, self._prefix, self._tree = found
                    self._console_id = console_id
                    self._name = (doc.get("console") or {}).get("name") or "Nintendo Switch"
                    return self._create()
        return self.async_show_form(
            step_id="manual",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_CONSOLE_ID): str,
                    probatio.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
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
            elif (found := await _async_wait_for_state(self.hass, prefix, console_id)) is None:
                errors["base"] = "no_state"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PREFIX: found[1], CONF_TREE: found[2]}
                )
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
            data={CONF_CONSOLE_ID: self._console_id, CONF_PREFIX: self._prefix, CONF_TREE: self._tree},
            options={CONF_TAKE_OVER: True},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PlayGuardOptionsFlow()


class PlayGuardOptionsFlow(OptionsFlowWithReload):
    """Whether the console's own discovery stays off, whether the sensors
    keep their last values while the console sleeps, whether a late
    refusal raises a notification, which games get a sensor (the entry
    reloads when one changes)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, self.config_entry.options),
        )
