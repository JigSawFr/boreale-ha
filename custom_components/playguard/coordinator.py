"""The coordinator: one console on the broker, its topics, its last
documents, its orders. Pushed, not polled: the entities listen to it.

Everything arrives retained but the events, so a restart of Home Assistant
gets the last state back at once, and an order sent while the console sleeps
waits on the broker (orders are retained; the console clears them once
handled).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import json
import logging
from typing import Any

from homeassistant.components import mqtt, persistent_notification
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.translation import async_get_translations
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONSOLE_ID,
    CONF_KEEP_VALUES,
    CONF_NOTIFY_REFUSED,
    CONF_PREFIX,
    CONF_TAKE_OVER,
    CONF_UNPUBLISHED,
    DEFAULT_PREFIX,
    DOMAIN,
    EVENT_PLAYGUARD,
    EVENT_TYPES,
    MANUFACTURER,
    MODEL,
    MODEL_NAMES,
    NATIVE_STATES_MAX,
    ORDER_TIMEOUT,
    PUBLISH_HARDWARE,
    PUBLISH_SERIAL,
    REFUSAL_REASONS,
    SCHEMA,
    STATISTICS_DELAY,
    TOPIC_INTEGRATION,
    WRITE_NONE,
    WRITE_TIMER,
)
from .entities import ENTITIES, dig

_LOGGER = logging.getLogger(__name__)

REPORT_MAX = 128 * 1024
# The console's answer to an order.
APPLIED = "command_applied"
REFUSED = "command_rejected"
WAITING = "command_waiting"
# The refusals a setting on the console explains, and whether the state still
# says it: a repair issue tells which setting, until the state shows it changed.
SETTINGS_REFUSING: dict[str, Callable[[dict[str, Any]], bool]] = {
    "read_only": lambda state: bool((state.get("console") or {}).get("read_only")),
    "policy_off": lambda state: (state.get("link") or {}).get("policy") == "off",
    "timer_writes_disabled": lambda state: not (state.get("link") or {}).get("remote_timer_writes"),
}


def _json(payload: str | bytes | bytearray) -> dict[str, Any] | None:
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

        self.state: dict[str, Any] | None = None
        self.system: dict[str, Any] | None = None  # the console itself (versions, storage, power, network)
        self.games: dict[str, Any] | None = None  # the games installed and played, with their totals
        self.online: bool | None = None
        self.activity: dict[str, Any] | None = None
        self.names: dict[str, Any] = {}
        self.week: dict[str, Any] | None = None
        self.finals: dict[str, dict[str, Any]] = {}  # "YYYY-MM-DD" -> a finished day's activity
        self.report: str | None = None
        self.last_event: dict[str, Any] | None = None
        self.last_seen: datetime | None = None  # the last document it published while we listened
        # What PlayGuard does not publish (the state's link.publishes), as the
        # last state said it: kept in the entry, so the entities of what is
        # off are not created again at the next start.
        self.unpublished: frozenset[str] = frozenset(entry.data.get(CONF_UNPUBLISHED, ()))

        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[dict[str, Any]], None]] = []
        # The orders whose action waits for the console's answer: (order, payload, answer).
        self._waiters: list[tuple[str, str, asyncio.Future[dict[str, Any]]]] = []
        self._unsubscribe: list[CALLBACK_TYPE] = []
        self._statistics_timer: CALLBACK_TYPE | None = None
        self._discovery_sent = False
        self._native_states = 0
        self._issue_schema = f"newer_schema_{self.console_id}"
        self._issue_native = f"native_discovery_{self.console_id}"
        self._issue_agent = f"agent_version_{self.console_id}"
        self._notification = f"{DOMAIN}_{self.console_id}_refused"

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
        await self._async_texts()  # loaded for the logbook, which reads them from the cache
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
        for issue_id in (self._issue_schema, self._issue_native, self._issue_agent):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for reason in SETTINGS_REFUSING:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_refused(reason))

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Called after every document; returns the removal."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_add_event_listener(self, listener: Callable[[dict[str, Any]], None]) -> CALLBACK_TYPE:
        """Called with every event the console publishes."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    @callback
    def _changed(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def _seen(self, msg: ReceiveMessage) -> None:
        """The console spoke now: a message published while we listen (a
        retained one handed over at subscription may be hours old)."""
        if not msg.retain:
            self.last_seen = dt_util.utcnow()

    @callback
    def _on_state(self, msg: ReceiveMessage) -> None:
        doc = _json(msg.payload)
        if doc is None:
            return
        self._seen(msg)
        self._check_schema(doc)
        self.state = doc
        self._clear_refusals()
        self._update_device()
        self._take_over()
        self._follow_publishes()
        self._changed()

    @callback
    def _on_system(self, msg: ReceiveMessage) -> None:
        self._seen(msg)
        self.system = _json(msg.payload)
        self._check_agent()
        self._update_device()
        self._changed()

    @callback
    def _on_games(self, msg: ReceiveMessage) -> None:
        self._seen(msg)
        self.games = _json(msg.payload)
        self._changed()

    def document(self, topic: str) -> dict[str, Any] | None:
        """The last document of `topic`: "state", "system" or "games"."""
        return {"system": self.system, "games": self.games}.get(topic, self.state)

    @callback
    def _on_availability(self, msg: ReceiveMessage) -> None:
        if msg.payload not in ("online", "offline"):
            return
        online = msg.payload == "online"
        # Once when it goes, once when it is back: not on every message.
        if not online and self.online is not False:
            _LOGGER.info(
                "%s is offline (asleep, off or out of reach): %s",
                self.name,
                "its entities keep their last values, its orders wait for it"
                if self.keep_values
                else "its entities are unavailable",
            )
        elif online and self.online is False:
            _LOGGER.info("%s is back online", self.name)
        if online:
            self._seen(msg)
        self.online = online
        self._changed()

    @property
    def reachable(self) -> bool:
        """On the broker, as its availability topic says (not known yet: yes)."""
        return self.online is not False

    @property
    def keep_values(self) -> bool:
        """Whether the entities keep their last values while the console is off
        the broker (the entry's option, on by default)."""
        return bool(self.entry.options.get(CONF_KEEP_VALUES, True))

    @callback
    def _on_activity(self, msg: ReceiveMessage) -> None:
        self._seen(msg)
        self.activity = _json(msg.payload)
        self._changed()

    @callback
    def _on_final(self, msg: ReceiveMessage) -> None:
        date = msg.topic.rsplit("/", 1)[-1]
        doc = _json(msg.payload)
        if doc is None:
            self.finals.pop(date, None)  # the console keeps 14 days and clears the older ones
            self._changed()
            return
        self.finals[date] = doc
        self._schedule_statistics()
        self._changed()  # the week moves on with it

    @callback
    def _on_names(self, msg: ReceiveMessage) -> None:
        self._seen(msg)
        self.names = _json(msg.payload) or {}
        self._changed()

    @callback
    def _on_week(self, msg: ReceiveMessage) -> None:
        self._seen(msg)
        self.week = _json(msg.payload)
        self._changed()
        if self.week:
            self._schedule_statistics()  # its finished days, per account

    @callback
    def _on_event(self, msg: ReceiveMessage) -> None:
        doc = _json(msg.payload)
        if doc is None:
            return
        self._seen(msg)
        self.last_event = doc
        self._answer(doc)
        for listener in list(self._event_listeners):
            listener(doc)
        self._fire(doc)

    @callback
    def _fire(self, doc: dict[str, Any]) -> None:
        """The event on Home Assistant's bus, with the console's device (the
        logbook describes it)."""
        if doc.get("event_type") not in EVENT_TYPES:
            return
        device = dr.async_get(self.hass).async_get_device_by_identifier((DOMAIN, self.console_id), self.entry.entry_id)
        app_id = doc.get("app_id")
        data = {
            k: doc.get(k) for k in ("event_type", "entity", "payload", "reason", "rc", "minutes_left", "blocked_by")
        }
        self.hass.bus.async_fire(
            EVENT_PLAYGUARD,
            {
                "device_id": device.id if device else None,
                "console_id": self.console_id,
                **data,
                "app_id": app_id,
                "game": self.game_name(app_id) if isinstance(app_id, str) else None,
            },
        )

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

    def _device_details(self) -> dict[str, str | None]:
        """The console as Nintendo names it, as PlayGuard's discovery does:
        its model and model number (the system document), the system it
        runs as its software ("23.0.1 · Atmosphère 1.10.1"). Unknown while
        PlayGuard does not publish its versions and hardware."""
        model = dig(self.system, ("hardware", "model"))
        name, number = MODEL_NAMES.get(model, (MODEL, None)) if isinstance(model, str) else (MODEL, None)
        firmware = dig(self.system, ("versions", "firmware")) or dig(self.state, ("console", "firmware"))
        atmosphere = dig(self.system, ("versions", "atmosphere")) or dig(self.state, ("console", "atmosphere"))
        system = None
        if isinstance(firmware, str):
            system = f"{firmware} \u00b7 Atmosph\u00e8re {atmosphere}" if isinstance(atmosphere, str) else firmware
        return {"name": self.name, "model": name, "model_id": number, "sw_version": system, "hw_version": None}

    @property
    def device_info(self) -> DeviceInfo:
        """The device all the entities belong to."""
        details = self._device_details()
        return DeviceInfo(
            identifiers={(DOMAIN, self.console_id)},
            name=details["name"],
            manufacturer=MANUFACTURER,
            model=details["model"],
            model_id=details["model_id"],
            sw_version=details["sw_version"],
        )

    @callback
    def _update_device(self) -> None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier((DOMAIN, self.console_id), self.entry.entry_id)
        if device is None:
            return
        details = self._device_details()
        name = details["name"] if device.name_by_user is None else device.name
        wanted = {**details, "name": name, "manufacturer": MANUFACTURER}
        if any(getattr(device, k) != v for k, v in wanted.items()):
            registry.async_update_device(
                device.id,
                name=name,
                manufacturer=MANUFACTURER,
                model=details["model"],
                model_id=details["model_id"],
                sw_version=details["sw_version"],
                hw_version=details["hw_version"],
            )

    # ---- what is published ----

    @callback
    def _follow_publishes(self) -> None:
        """PlayGuard says what it publishes (link.publishes; an older one does
        not: everything). The entities of what it turned off go; what it
        turned back on comes back with a reload of the entry."""
        publishes = dig(self.state, ("link", "publishes"))
        if not isinstance(publishes, dict):
            return
        off = {k for k, v in publishes.items() if v is False}
        if PUBLISH_HARDWARE in off:
            off.add(PUBLISH_SERIAL)  # the serial number goes with the hardware
        unpublished = frozenset(off)
        if unpublished == self.unpublished:
            self._remove_unpublished()
            return
        back = self.unpublished - unpublished
        self.unpublished = unpublished
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_UNPUBLISHED: sorted(unpublished)}
        )
        self._remove_unpublished()
        if back:
            _LOGGER.debug("%s publishes %s again: its entities come back", self.base, ", ".join(sorted(back)))
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    @callback
    def _remove_unpublished(self) -> None:
        """Removes the entities of what PlayGuard does not publish."""
        if not self.unpublished:
            return
        registry = er.async_get(self.hass)
        for definition in ENTITIES:
            if definition.publish not in self.unpublished:
                continue
            unique_id = f"{self.console_id}_{definition.key}"
            entity_id = registry.async_get_entity_id(definition.platform, DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)

    @callback
    def _check_schema(self, doc: dict[str, Any]) -> None:
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
    def _check_agent(self) -> None:
        """PlayGuard offers to update its agent when it starts after an update;
        put off, the console runs an older agent: a repair issue says so."""
        versions = (self.system or {}).get("versions") or {}
        app, agent = versions.get("app"), versions.get("agent")
        if isinstance(app, str) and isinstance(agent, str) and app and agent and app != agent:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_agent,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="agent_version",
                translation_placeholders={"name": self.name, "app": app, "agent": agent},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_agent)

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
        # Unlocking parental controls needs the timer writes too; locking them again never does.
        unlocking = key == "parental_controls" and payload == "UNLOCK"
        for reason, refusing in SETTINGS_REFUSING.items():
            if reason == "timer_writes_disabled" and not (write == WRITE_TIMER or unlocking):
                continue
            if refusing(self.state):
                self._refusal_issue(reason)
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key=reason)

    async def async_send(self, key: str, payload: str) -> None:
        """Publishes an order, retained: it waits on the broker if the console sleeps."""
        await mqtt.async_publish(self.hass, f"{self.base}/{key}/set", payload, qos=1, retain=True)

    async def async_order(self, key: str, write: str, payload: str) -> None:
        """Checks, then sends an order. While the console is on the broker, waits
        for its answer: refused, the action fails, saying why. Applied, waiting
        for PlayGuard, or no answer in time: the action returns (the order
        waits on the broker; a later refusal raises a notification)."""
        self.check_order(key, write, payload)
        if self.online is not True:
            await self.async_send(key, payload)
            return
        waiter = (key, payload.casefold(), self.hass.loop.create_future())
        self._waiters.append(waiter)
        try:
            await self.async_send(key, payload)
            async with asyncio.timeout(ORDER_TIMEOUT):
                doc = await waiter[2]
        except TimeoutError:
            _LOGGER.debug("%s: no answer to %s yet, it waits on the broker", self.base, key)
            return
        finally:
            self._waiters.remove(waiter)
        if doc.get("event_type") == REFUSED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refused",
                translation_placeholders={"name": self.name, "reason": await self._async_reason(doc)},
            )

    @callback
    def _answer(self, doc: dict[str, Any]) -> None:
        """The console's answer to an order: to the action waiting for it, else
        a refusal in a notification (one per console, which an order applied
        takes away). Not for the integration's own order (its discovery)."""
        event_type, key, payload = doc.get("event_type"), doc.get("entity"), doc.get("payload")
        if event_type not in (APPLIED, REFUSED, WAITING) or key == "discovery":
            return
        if event_type == APPLIED:
            persistent_notification.async_dismiss(self.hass, self._notification)
        sent = payload.casefold() if isinstance(payload, str) else None
        for order, value, answer in self._waiters:
            if order == key and value == sent and not answer.done():
                answer.set_result(doc)
                return
        if event_type == REFUSED and doc.get("reason") in SETTINGS_REFUSING:
            self._refusal_issue(str(doc["reason"]))
        if event_type == REFUSED and self.entry.options.get(CONF_NOTIFY_REFUSED, True):
            self.entry.async_create_background_task(
                self.hass, self._async_notify(doc), f"{DOMAIN} {self.console_id} refusal"
            )

    def _issue_refused(self, reason: str) -> str:
        return f"refused_{reason}_{self.console_id}"

    @callback
    def _refusal_issue(self, reason: str) -> None:
        """An order refused because of a setting on the console: a repair
        issue says which, until the state shows it changed."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_refused(reason),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"refused_{reason}",
            translation_placeholders={"name": self.name},
        )

    @callback
    def _clear_refusals(self) -> None:
        for reason, refusing in SETTINGS_REFUSING.items():
            if self.state is not None and not refusing(self.state):
                ir.async_delete_issue(self.hass, DOMAIN, self._issue_refused(reason))

    async def _async_texts(self) -> dict[str, str]:
        """The integration's messages, in Home Assistant's language."""
        return await async_get_translations(self.hass, self.hass.config.language, "exceptions", [DOMAIN])

    async def _async_reason(self, doc: dict[str, Any]) -> str:
        return self.reason_text(doc, await self._async_texts())

    def reason_text(self, doc: dict[str, Any], texts: dict[str, str]) -> str:
        """Why the console refused, in words."""
        reason, rc = doc.get("reason"), doc.get("rc")
        key = f"reason_{reason}" if reason in REFUSAL_REASONS else "reason_other"
        text = texts.get(f"component.{DOMAIN}.exceptions.{key}.message")
        return text.format(reason=reason, rc=rc or "-") if text else str(reason)

    def order_text(self, doc: dict[str, Any]) -> str:
        """An event's order, by its entity's name, with its value (but a press)."""
        payload = doc.get("payload")
        order = self._order_name(str(doc.get("entity")))
        if isinstance(payload, str) and payload and payload.upper() != "PRESS":
            order = f"{order}: {payload}"
        return order

    def _order_name(self, key: str) -> str:
        """An order by its entity's name, else by its key (an action's own order)."""
        registry = er.async_get(self.hass)
        for definition in ENTITIES:
            if definition.key != key:
                continue
            entity_id = registry.async_get_entity_id(definition.platform, DOMAIN, f"{self.console_id}_{key}")
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is not None:
                return state.name
        return key

    async def _async_notify(self, doc: dict[str, Any]) -> None:
        """A refusal no action waited for, as a notification."""
        texts = await self._async_texts()
        prefix = f"component.{DOMAIN}.exceptions"
        values = {"name": self.name, "order": self.order_text(doc), "reason": self.reason_text(doc, texts)}
        title = texts.get(f"{prefix}.refused_title.message", "{name}").format(**values)
        message = texts.get(f"{prefix}.refused_later.message", "{order}: {reason}").format(**values)
        persistent_notification.async_create(self.hass, message, title, self._notification)

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

    def account_name(self, uid: str | None) -> str | None:
        """An account's name (its nickname on the console) from the names document, else None."""
        if not uid:
            return None
        return (self.names.get("accounts") or {}).get(uid.upper())
