"""A Lantern bridge: its state, pushed over MQTT.

The bridge (https://github.com/JigSawFr/lantern-bridge) publishes under
`<prefix>/<bridge id>`: `state`, a retained JSON document with a `schema`
(this reads schema 1, and skips a newer one), and `availability` (`online` or
`offline`, its last will), and `event`, one journal line as it happens (not
retained). `order/rescan` makes it read its sources again.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.button import ButtonEntity
from homeassistant.components.event import EventEntity
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_BRIDGE_ID, CONF_BRIDGE_PREFIX, DEFAULT_BRIDGE_PREFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

type BridgeConfigEntry = ConfigEntry[BridgeHub]

SCHEMA = 1
STATUSES = ["ok", "warn", "fail"]
GONE_AFTER = 600  # seconds without the bridge before a repair says so (a restart is not worth one)
RESCAN = "rescan"  # the kind of the repair that asks the bridge to read its sources again


def parse_state(payload: str | bytes | bytearray) -> dict[str, Any] | None:
    """A bridge's state document of a schema this reads, else None."""
    try:
        doc = json.loads(payload) if payload else None
    except ValueError:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("schema"), int) or isinstance(doc["schema"], bool):
        return None
    return doc if 1 <= doc["schema"] <= SCHEMA else None


def bridge_of(topic: str, payload: str | bytes | bytearray) -> tuple[str, str, str] | None:
    """(prefix, bridge id, name) of a bridge's `<prefix>/<id>/state` message, else None."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[-1] != "state" or (doc := parse_state(payload)) is None:
        return None
    who = doc.get("bridge")
    uid = who.get("uid") if isinstance(who, dict) else None
    if not isinstance(uid, str) or parts[-2] != uid:
        return None
    name = who.get("name") if isinstance(who, dict) else None
    if not isinstance(name, str) or not name:
        name = "Lantern bridge"
    return "/".join(parts[:-2]), uid, name


def newer_schema(payload: str | bytes | bytearray) -> int | None:
    """The schema of a state document this version does not read yet, else None."""
    try:
        doc = json.loads(payload) if payload else None
    except ValueError:
        return None
    schema = doc.get("schema") if isinstance(doc, dict) else None
    return schema if isinstance(schema, int) and not isinstance(schema, bool) and schema > SCHEMA else None


class BridgeHub:
    """One bridge on the broker: its last state and whether it is there."""

    def __init__(self, hass: HomeAssistant, entry: BridgeConfigEntry) -> None:
        self.hass = hass
        self.bridge_id: str = entry.data[CONF_BRIDGE_ID]
        self.prefix: str = entry.data.get(CONF_BRIDGE_PREFIX, DEFAULT_BRIDGE_PREFIX)
        self.title = entry.title
        self.base = f"{self.prefix}/{self.bridge_id}"
        self.state: dict[str, Any] | None = None
        self.online: bool | None = None  # None: no availability seen yet
        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._unsub: list[CALLBACK_TYPE] = []
        self.entry_id = entry.entry_id
        self._derived: set[str] = set()  # the repairs that follow the state (a source down, the disk)
        self._gone: CALLBACK_TYPE | None = None
        self._issue_gone = f"bridge_gone_{self.bridge_id}"
        self._issue_schema = f"bridge_schema_{self.bridge_id}"

    @property
    def device_info(self) -> DeviceInfo:
        who = (self.state or {}).get("bridge") or {}
        return DeviceInfo(
            identifiers={(DOMAIN, f"bridge_{self.bridge_id}")},
            manufacturer="JigSawFr",
            model="Lantern bridge",
            name=who.get("name") or self.title,
            sw_version=who.get("version"),
        )

    async def async_start(self) -> None:
        self._unsub = [
            await mqtt.async_subscribe(self.hass, f"{self.base}/state", self._on_state, 1),
            await mqtt.async_subscribe(self.hass, f"{self.base}/availability", self._on_availability, 1),
            await mqtt.async_subscribe(self.hass, f"{self.base}/event", self._on_event, 1),
        ]

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub = []
        if self._gone is not None:
            self._gone()
            self._gone = None
        for issue in (*self._derived, self._issue_gone, self._issue_schema):
            ir.async_delete_issue(self.hass, DOMAIN, issue)  # nothing to repair once the entry is gone
        self._derived = set()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_add_event_listener(self, listener: Callable[[str, dict[str, Any]], None]) -> CALLBACK_TYPE:
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    @callback
    def _on_event(self, message: ReceiveMessage) -> None:
        """A journal line: schema 1 and a known shape, else skipped (a newer schema is not guessed at)."""
        try:
            doc = json.loads(message.payload)
        except ValueError:
            return
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("kind"), str):
            return
        data = {k: doc[k] for k in ("subject", "detail", "ts") if isinstance(doc.get(k), (str, int))}
        for listener in list(self._event_listeners):
            listener(doc["kind"], data)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @property
    def name(self) -> str:
        return ((self.state or {}).get("bridge") or {}).get("name") or self.title

    @callback
    def _on_state(self, message: ReceiveMessage) -> None:
        if (doc := parse_state(message.payload)) is None:
            _LOGGER.debug("%s: a state this version does not read was skipped", self.base)
            if (newer := newer_schema(message.payload)) is not None:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self._issue_schema,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="bridge_newer_schema",
                    translation_placeholders={"name": self.name, "schema": str(newer), "known": str(SCHEMA)},
                )
            return
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_schema)
        self.state = doc
        self._repair()
        self._notify()

    @callback
    def _repair(self) -> None:
        """The repairs that follow the state: one per source that does not answer, one for the disk."""
        wanted: dict[
            str, tuple[str, ir.IssueSeverity, bool, dict[str, str], dict[str, str | int | float | None] | None]
        ] = {}
        for source in self.read("sources") or []:
            if isinstance(source, dict) and source.get("up") is False and isinstance(source.get("id"), str):
                wanted[f"bridge_source_{self.bridge_id}_{source['id']}"] = (
                    "bridge_source_down",
                    ir.IssueSeverity.WARNING,
                    True,
                    {"name": self.name, "source": source["id"]},
                    {"entry_id": self.entry_id, "kind": RESCAN},
                )
        for check in self.read("checks") or []:
            if isinstance(check, dict) and check.get("name") == "disk" and check.get("status") in ("warn", "fail"):
                wanted[f"bridge_disk_{self.bridge_id}"] = (
                    "bridge_disk",
                    ir.IssueSeverity.ERROR if check["status"] == "fail" else ir.IssueSeverity.WARNING,
                    False,
                    {"name": self.name},
                    None,
                )
        for issue, (key, severity, fixable, placeholders, data) in wanted.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue,
                is_fixable=fixable,
                severity=severity,
                translation_key=key,
                translation_placeholders=placeholders,
                data=data,
            )
        for gone in self._derived - wanted.keys():
            ir.async_delete_issue(self.hass, DOMAIN, gone)
        self._derived = set(wanted)

    @callback
    def _raise_gone(self, _now: object) -> None:
        self._gone = None
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_gone,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="bridge_gone",
            translation_placeholders={"name": self.name},
        )

    @callback
    def _on_availability(self, message: ReceiveMessage) -> None:
        online = str(message.payload) == "online"
        if online != self.online:
            (_LOGGER.info if online else _LOGGER.warning)(
                "%s: the bridge is %s", self.base, "back" if online else "gone"
            )
        self.online = online
        if online:
            if self._gone is not None:
                self._gone()
                self._gone = None
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_gone)
        elif self._gone is None:
            self._gone = async_call_later(self.hass, GONE_AFTER, self._raise_gone)
        self._notify()

    async def async_rescan(self) -> None:
        await mqtt.async_publish(self.hass, f"{self.base}/order/rescan", "", 0, False)

    def read(self, *path: str) -> Any:
        value: Any = self.state
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        return value


async def async_setup_entry(hass: HomeAssistant, entry: BridgeConfigEntry) -> BridgeHub:
    hub = BridgeHub(hass, entry)
    entry.runtime_data = hub
    return hub


class BridgeEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: BridgeHub, key: str) -> None:
        self.hub = hub
        self._attr_unique_id = f"bridge_{hub.bridge_id}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        return self.hub.device_info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.hub.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Known once the bridge's state arrived (retained), while it is not gone (its last will)."""
        return self.hub.state is not None and self.hub.online is not False


class BridgeStatus(BridgeEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_status")

    @property
    def native_value(self) -> str | None:
        status = self.hub.read("status")
        return status if status in STATUSES else None


class BridgeVersion(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_version")

    @property
    def native_value(self) -> str | None:
        version = self.hub.read("bridge", "version")
        return version if isinstance(version, str) else None


class BridgeFigure(BridgeEntity, SensorEntity):
    """A counter of the state document."""

    def __init__(self, hub: BridgeHub, key: str, path: tuple[str, ...], state_class: SensorStateClass) -> None:
        super().__init__(hub, key)
        self._path = path
        self._attr_state_class = state_class

    @property
    def native_value(self) -> float | None:
        value = self.hub.read(*self._path)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class BridgeSourcesDown(BridgeEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_sources_down")

    @property
    def native_value(self) -> int | None:
        sources = self.hub.read("sources")
        if not isinstance(sources, list):
            return None
        return sum(1 for s in sources if isinstance(s, dict) and not s.get("up"))


class BridgeProblems(BridgeEntity, SensorEntity):
    """How many of the bridge's checks are not good (the bridge counts them; an older one has no count)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_problems")

    @property
    def native_value(self) -> int | None:
        value = self.hub.read("problems")
        return value if isinstance(value, int) and not isinstance(value, bool) else None


#: What the bridge's journal says happened (lantern-bridge, admin/__init__.py `_JOURNAL`).
JOURNAL_KINDS = (
    "started",
    "scan",
    "source_down",
    "source_up",
    "update",
    "settings",
    "paired",
    "pairing_refused",
    "revoked",
    "restored",
)


class BridgeJournal(BridgeEntity, EventEntity):
    """One event per line of the bridge's journal, for automations (a source down, a device paired…)."""

    _attr_event_types = list(JOURNAL_KINDS)

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_journal")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.async_add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, kind: str, data: dict[str, Any]) -> None:
        if kind in JOURNAL_KINDS:  # a kind a newer bridge adds is not a type this knows
            self._trigger_event(kind, data)
            self.async_write_ha_state()


class BridgeReachable(BridgeEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_reachable")

    @property
    def available(self) -> bool:
        return True  # it says the other entities are not

    @property
    def is_on(self) -> bool:
        return self.hub.online is True


class BridgeRescan(BridgeEntity, ButtonEntity):
    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_rescan")

    @property
    def available(self) -> bool:
        return self.hub.online is not False  # an order waits for nobody: it is not retained

    async def async_press(self) -> None:
        await self.hub.async_rescan()


RELEASE_PAGE = "https://github.com/JigSawFr/lantern-bridge/releases/tag/"


class BridgeUpdate(BridgeEntity, UpdateEntity):
    """The bridge's version and, when its own check found one, the newer release. Nothing is installed from here."""

    _attr_title = "Lantern bridge"

    def __init__(self, hub: BridgeHub) -> None:
        super().__init__(hub, "bridge_update")

    @property
    def installed_version(self) -> str | None:
        version = self.hub.read("bridge", "version")
        return version if isinstance(version, str) and version else None

    @property
    def latest_version(self) -> str | None:
        latest = self.hub.read("update", "latest")
        newer = self.hub.read("update", "available") is True and isinstance(latest, str) and latest
        # No check yet, check off, or up to date: the installed one, not "update available".
        return latest.removeprefix("v") if newer else self.installed_version

    @property
    def release_url(self) -> str | None:
        latest = self.hub.read("update", "latest")
        newer = self.hub.read("update", "available") is True and isinstance(latest, str) and latest
        return RELEASE_PAGE + latest if newer else None


FIGURES = (
    ("bridge_titles", ("library", "titles"), SensorStateClass.MEASUREMENT),
    ("bridge_files_pending", ("files", "pending"), SensorStateClass.MEASUREMENT),
    ("bridge_transfers", ("traffic", "transfers"), SensorStateClass.MEASUREMENT),
    ("bridge_errors", ("traffic", "errors"), SensorStateClass.TOTAL_INCREASING),
)


def async_add_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    hub = entry.runtime_data
    async_add_entities(
        [BridgeStatus(hub), BridgeVersion(hub), BridgeSourcesDown(hub), BridgeProblems(hub)]
        + [BridgeFigure(hub, key, path, state_class) for key, path, state_class in FIGURES]
    )


def async_add_binary_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeReachable(entry.runtime_data)])


def async_add_updates(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeUpdate(entry.runtime_data)])


def async_add_buttons(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeRescan(entry.runtime_data)])


def async_add_events(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeJournal(entry.runtime_data)])
