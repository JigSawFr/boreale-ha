"""The coordinator: one console on the broker, its topics, its last
documents, its orders. Pushed, not polled: the entities listen to it.

Everything arrives retained but the events, so a restart of Home Assistant
gets the last state back at once, and an order sent while the console sleeps
waits on the broker (orders are retained; the console clears them once
handled).
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.loader import async_get_integration

from .const import (
    CONF_CONSOLE_ID,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    DEFAULT_PREFIX,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    NATIVE_STATES_MAX,
    SCHEMA,
    STATISTICS_DELAY,
    TOPIC_INTEGRATION,
    WRITE_NONE,
    WRITE_TIMER,
)

_LOGGER = logging.getLogger(__name__)

REPORT_MAX = 128 * 1024


def _json(payload: str | bytes) -> dict | None:
    """A document, or None (an empty retained message clears the topic)."""
    if not payload:
        return None
    try:
        doc = json.loads(payload)
    except ValueError:
        _LOGGER.debug("Not JSON, ignored: %.120s", payload)
        return None
    return doc if isinstance(doc, dict) else None


class PlayGuardConsole:
    """The console behind one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.console_id: str = entry.data[CONF_CONSOLE_ID]
        self.prefix: str = entry.data.get(CONF_PREFIX, DEFAULT_PREFIX)
        self.base = f"{self.prefix}/{self.console_id}"

        self.state: dict | None = None
        self.system: dict | None = None  # the console itself (versions, storage, power, network)
        self.games: dict | None = None  # the games installed and played, with their totals
        self.online: bool | None = None
        self.activity: dict | None = None
        self.names: dict = {}
        self.week: dict | None = None
        self.finals: dict[str, dict] = {}  # "YYYY-MM-DD" -> a finished day's activity
        self.report: str | None = None
        self.last_event: dict | None = None

        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[dict], None]] = []
        self._unsubscribe: list[CALLBACK_TYPE] = []
        self._statistics_timer: CALLBACK_TYPE | None = None
        self._discovery_sent = False
        self._native_states = 0
        self._issue_schema = f"newer_schema_{self.console_id}"
        self._issue_native = f"native_discovery_{self.console_id}"

    # ---- topics ----

    async def async_start(self) -> None:
        """Subscribes to the console's topics."""
        topics: dict[str, Callable[[ReceiveMessage], None]] = {
            "state": self._on_state,
            "system": self._on_system,
            "games": self._on_games,
            "availability": self._on_availability,
            "activity": self._on_activity,
            "activity/+": self._on_final,
            "names": self._on_names,
            "week": self._on_week,
            "event": self._on_event,
            "report": self._on_report,
        }
        for sub, handler in topics.items():
            self._unsubscribe.append(await mqtt.async_subscribe(self.hass, f"{self.base}/{sub}", handler, qos=1))
        await self.async_publish_version()

    async def async_publish_version(self) -> None:
        """Tells the console which version of the integration (and of Home
        Assistant) runs, retained: it reads it at its next connection too,
        and PlayGuard warns of a newer release. Not worth failing the set-up."""
        integration = await async_get_integration(self.hass, DOMAIN)
        doc = {"schema": SCHEMA, "version": str(integration.version), "homeassistant": HA_VERSION}
        try:
            await mqtt.async_publish(
                self.hass,
                f"{self.base}/{TOPIC_INTEGRATION}",
                json.dumps(doc, separators=(",", ":")),
                qos=1,
                retain=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s: could not tell the console the integration's version: %r", self.base, err)

    async def async_clear_version(self) -> None:
        """The integration is gone: the console no longer warns of its releases."""
        await mqtt.async_publish(self.hass, f"{self.base}/{TOPIC_INTEGRATION}", "", qos=1, retain=True)

    @callback
    def async_stop(self) -> None:
        """Unsubscribes. Its repair issues go with it (back with the next state)."""
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()
        if self._statistics_timer:
            self._statistics_timer()
            self._statistics_timer = None
        for issue_id in (self._issue_schema, self._issue_native):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Called after every document; returns the removal."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_add_event_listener(self, listener: Callable[[dict], None]) -> CALLBACK_TYPE:
        """Called with every event the console publishes."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    @callback
    def _changed(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def _on_state(self, msg: ReceiveMessage) -> None:
        doc = _json(msg.payload)
        if doc is None:
            return
        self._check_schema(doc)
        self.state = doc
        self._update_device()
        self._take_over()
        self._changed()

    @callback
    def _on_system(self, msg: ReceiveMessage) -> None:
        self.system = _json(msg.payload)
        self._changed()

    @callback
    def _on_games(self, msg: ReceiveMessage) -> None:
        self.games = _json(msg.payload)
        self._changed()

    def document(self, topic: str) -> dict | None:
        """The last document of `topic`: "state", "system" or "games"."""
        return {"system": self.system, "games": self.games}.get(topic, self.state)

    @callback
    def _on_availability(self, msg: ReceiveMessage) -> None:
        if msg.payload not in ("online", "offline"):
            return
        online = msg.payload == "online"
        # Once when it goes, once when it is back: not on every message.
        if not online and self.online is not False:
            _LOGGER.info("%s is offline (asleep, off or out of reach): its entities are unavailable", self.name)
        elif online and self.online is False:
            _LOGGER.info("%s is back online", self.name)
        self.online = online
        self._changed()

    @property
    def reachable(self) -> bool:
        """On the broker, as its availability topic says (not known yet: yes)."""
        return self.online is not False

    @callback
    def _on_activity(self, msg: ReceiveMessage) -> None:
        self.activity = _json(msg.payload)
        self._changed()

    @callback
    def _on_final(self, msg: ReceiveMessage) -> None:
        date = msg.topic.rsplit("/", 1)[-1]
        doc = _json(msg.payload)
        if doc is None:
            self.finals.pop(date, None)  # the console keeps 14 days and clears the older ones
            return
        self.finals[date] = doc
        self._schedule_statistics()

    @callback
    def _on_names(self, msg: ReceiveMessage) -> None:
        self.names = _json(msg.payload) or {}
        self._changed()

    @callback
    def _on_week(self, msg: ReceiveMessage) -> None:
        self.week = _json(msg.payload)
        self._changed()

    @callback
    def _on_event(self, msg: ReceiveMessage) -> None:
        doc = _json(msg.payload)
        if doc is None:
            return
        self.last_event = doc
        for listener in list(self._event_listeners):
            listener(doc)

    @callback
    def _on_report(self, msg: ReceiveMessage) -> None:
        text = msg.payload if isinstance(msg.payload, str) else msg.payload.decode(errors="replace")
        self.report = text[:REPORT_MAX] or None

    # ---- the device ----

    @property
    def name(self) -> str:
        """The console's name in PlayGuard, else the entry's title."""
        name = ((self.state or {}).get("console") or {}).get("name")
        return name or self.entry.title

    def _device_details(self) -> tuple[str, str | None, str | None]:
        """The device's name, software and hardware versions, from the state."""
        console = (self.state or {}).get("console") or {}
        return self.name, console.get("app_version") or console.get("agent_version"), console.get("firmware")

    @property
    def device_info(self) -> DeviceInfo:
        """The device all the entities belong to."""
        name, sw_version, hw_version = self._device_details()
        return DeviceInfo(
            identifiers={(DOMAIN, self.console_id)},
            name=name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=sw_version,
            hw_version=hw_version,
        )

    @callback
    def _update_device(self) -> None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier((DOMAIN, self.console_id), self.entry.entry_id)
        if device is None:
            return
        name, sw_version, hw_version = self._device_details()
        changes: dict[str, str | None] = {"sw_version": sw_version, "hw_version": hw_version}
        if device.name_by_user is None and device.name != name:
            changes["name"] = name
        if any(getattr(device, k) != v for k, v in changes.items()):
            registry.async_update_device(device.id, **changes)

    @callback
    def _check_schema(self, doc: dict) -> None:
        schema = doc.get("schema")
        if isinstance(schema, int) and schema > SCHEMA:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_schema,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="newer_schema",
                translation_placeholders={"name": self.name, "schema": str(schema), "known": str(SCHEMA)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_schema)

    @callback
    def _take_over(self) -> None:
        """Turns the console's own discovery off (these entities replace it),
        or back on when the option says so. Still on after it was asked off,
        the same entities are there twice: a repair issue says so."""
        want_native = not self.entry.options.get(CONF_TAKE_OVER, True)
        have_native = bool(((self.state or {}).get("link") or {}).get("ha_discovery"))
        if have_native and not want_native and self._discovery_sent:
            self._native_states += 1
            if self._native_states >= NATIVE_STATES_MAX:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self._issue_native,
                    is_fixable=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="native_discovery",
                    translation_placeholders={"name": self.name},
                    data={"entry_id": self.entry.entry_id},
                )
        else:
            self._native_states = 0
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_native)
        if self._discovery_sent or want_native == have_native:
            return
        self._discovery_sent = True
        payload = "ON" if want_native else "OFF"
        _LOGGER.debug("%s: the console's own discovery %s", self.base, payload)
        self.entry.async_create_background_task(
            self.hass, self.async_send("discovery", payload), f"{DOMAIN} {self.console_id} discovery"
        )

    async def async_turn_native_off(self) -> None:
        """Asks the console again to turn its own discovery off (the repair)."""
        self._native_states = 0
        await self.async_send("discovery", "OFF")

    # ---- orders ----

    def check_order(self, key: str, write: str, payload: str) -> None:
        """Refuses an order the console would refuse anyway, saying why."""
        if write == WRITE_NONE:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="read_only_entity")
        if self.state is None:
            return  # nothing known yet: the console decides (the order waits on the broker)
        if (self.state.get("console") or {}).get("read_only"):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="read_only")
        link = self.state.get("link") or {}
        if link.get("policy") == "off":
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="policy_off")
        locking = key == "unlocked" and payload == "OFF"
        if write == WRITE_TIMER and not link.get("remote_timer_writes") and not locking:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="timer_writes_disabled")

    async def async_send(self, key: str, payload: str) -> None:
        """Publishes an order, retained: it waits on the broker if the console sleeps."""
        await mqtt.async_publish(self.hass, f"{self.base}/{key}/set", payload, qos=1, retain=True)

    async def async_order(self, key: str, write: str, payload: str) -> None:
        """Checks, then sends an order."""
        self.check_order(key, write, payload)
        await self.async_send(key, payload)

    # ---- statistics ----

    @callback
    def _schedule_statistics(self) -> None:
        if self._statistics_timer:
            self._statistics_timer()

        @callback
        def _run(_now: Any) -> None:
            self._statistics_timer = None
            from .statistics import async_import_days  # noqa: PLC0415 (the recorder may not be there)

            self.entry.async_create_background_task(
                self.hass, async_import_days(self.hass, self), f"{DOMAIN} {self.console_id} statistics"
            )

        self._statistics_timer = async_call_later(self.hass, STATISTICS_DELAY, _run)

    # ---- names ----

    def game_name(self, app_id: str | None) -> str | None:
        """A game's name from the names document, else None."""
        if not app_id:
            return None
        return (self.names.get("games") or {}).get(app_id.upper())
