"""A Lantern bridge: its state, pushed over MQTT.

The bridge (https://github.com/JigSawFr/lantern-bridge) publishes under
`<prefix>/<bridge id>`: `state`, a retained JSON document with a `schema`
(this reads schema 1, and skips a newer one), and `availability` (`online` or
`offline`, its last will). `order/rescan` makes it read its sources again.
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
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_BRIDGE_ID, CONF_BRIDGE_PREFIX, DEFAULT_BRIDGE_PREFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

type BridgeConfigEntry = ConfigEntry[BridgeHub]

SCHEMA = 1
STATUSES = ["ok", "warn", "fail"]


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
        self._unsub: list[CALLBACK_TYPE] = []

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
        ]

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub = []

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def _on_state(self, message: ReceiveMessage) -> None:
        if (doc := parse_state(message.payload)) is None:
            _LOGGER.debug("%s: a state this version does not read was skipped", self.base)
            return
        self.state = doc
        self._notify()

    @callback
    def _on_availability(self, message: ReceiveMessage) -> None:
        online = str(message.payload) == "online"
        if online != self.online:
            (_LOGGER.info if online else _LOGGER.warning)(
                "%s: the bridge is %s", self.base, "back" if online else "gone"
            )
        self.online = online
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


FIGURES = (
    ("bridge_titles", ("library", "titles"), SensorStateClass.MEASUREMENT),
    ("bridge_files_pending", ("files", "pending"), SensorStateClass.MEASUREMENT),
    ("bridge_transfers", ("traffic", "transfers"), SensorStateClass.MEASUREMENT),
    ("bridge_errors", ("traffic", "errors"), SensorStateClass.TOTAL_INCREASING),
)


def async_add_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    hub = entry.runtime_data
    async_add_entities(
        [BridgeStatus(hub), BridgeVersion(hub), BridgeSourcesDown(hub)]
        + [BridgeFigure(hub, key, path, state_class) for key, path, state_class in FIGURES]
    )


def async_add_binary_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeReachable(entry.runtime_data)])


def async_add_buttons(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeRescan(entry.runtime_data)])
