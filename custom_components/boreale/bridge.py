"""A Lantern bridge: its health and its figures, read over HTTP.

`/healthz` gives the status, and the bridge's version and id to the local
network. `/metrics` (Prometheus text, off unless the bridge's settings turn it
on) gives the counters; without it the status and the version still come.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import CONF_BRIDGE_ID, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type BridgeConfigEntry = ConfigEntry[BridgeCoordinator]

TIMEOUT = aiohttp.ClientTimeout(total=10)
EVERY = timedelta(seconds=60)
STATUSES = ["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class BridgeData:
    status: str
    version: str | None
    figures: dict[str, float] = field(default_factory=dict)  # empty while the bridge's metrics are off


def parse_metrics(text: str) -> dict[str, float]:
    """The samples of the bridge's Prometheus text, by name without the prefix: summed over the sources, and a
    `state` label added to the name (`files{state="pending"}` is `files_pending`)."""
    figures: dict[str, float] = {}
    for line in text.splitlines():
        if not line.startswith("lantern_bridge_"):
            continue
        if "{" in line:
            head, _, rest = line.partition("{")
            labels, _, tail = rest.rpartition("}")
        else:
            head, _, tail = line.partition(" ")
            labels = ""
        name = head[len("lantern_bridge_") :]
        if 'state="' in labels:
            name += "_" + labels.split('state="', 1)[1].split('"', 1)[0]
        try:
            figures[name] = figures.get(name, 0.0) + float(tail.strip())
        except ValueError:
            continue
    return figures


async def async_probe(hass: HomeAssistant, url: str) -> dict[str, Any] | None:
    """The bridge's `/healthz` document, else None (not a bridge, or not there)."""
    try:
        async with async_get_clientsession(hass).get(f"{url}/healthz", timeout=TIMEOUT) as response:
            if response.status not in (200, 503):
                return None
            doc = await response.json(content_type=None)
    except aiohttp.ClientError, TimeoutError, ValueError:
        return None
    return doc if isinstance(doc, dict) and doc.get("status") in STATUSES else None


class BridgeCoordinator(DataUpdateCoordinator[BridgeData]):
    def __init__(self, hass: HomeAssistant, entry: BridgeConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=entry.title, update_interval=EVERY)
        self.url: str = entry.data[CONF_URL]
        self.bridge_id: str = entry.data[CONF_BRIDGE_ID]
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, f"bridge_{self.bridge_id}")},
            manufacturer="JigSawFr",
            model="Lantern bridge",
            name=entry.title,
            configuration_url=self.url,
        )

    async def _async_update_data(self) -> BridgeData:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(f"{self.url}/healthz", timeout=TIMEOUT) as response:
                doc = await response.json(content_type=None)
            if not isinstance(doc, dict) or doc.get("status") not in STATUSES:
                raise ValueError("not a status")
            figures: dict[str, float] = {}
            async with session.get(f"{self.url}/metrics", timeout=TIMEOUT) as metrics:
                if metrics.status == 200:
                    figures = parse_metrics(await metrics.text())
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="bridge_unreachable",
                translation_placeholders={"url": self.url},
            ) from err
        version = doc.get("version")
        return BridgeData(doc["status"], version if isinstance(version, str) else None, figures)


async def async_setup_entry(hass: HomeAssistant, entry: BridgeConfigEntry) -> bool:
    coordinator = BridgeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    return True


# (key, figure, unit-less state class) of the counters the bridge's metrics give.
FIGURES = (
    ("bridge_titles", "titles_served", SensorStateClass.MEASUREMENT),
    ("bridge_files_pending", "files_pending", SensorStateClass.MEASUREMENT),
    ("bridge_transfers", "transfers_active", SensorStateClass.MEASUREMENT),
    ("bridge_errors", "errors_total", SensorStateClass.TOTAL_INCREASING),
)


class BridgeEntity(CoordinatorEntity[BridgeCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BridgeCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"bridge_{coordinator.bridge_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = coordinator.device_info


class BridgeStatus(BridgeEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, coordinator: BridgeCoordinator) -> None:
        super().__init__(coordinator, "bridge_status")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status


class BridgeVersion(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BridgeCoordinator) -> None:
        super().__init__(coordinator, "bridge_version")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.version


class BridgeFigure(BridgeEntity, SensorEntity):
    """One counter of the metrics: unavailable while the bridge does not give them."""

    def __init__(self, coordinator: BridgeCoordinator, key: str, figure: str, state_class: SensorStateClass) -> None:
        super().__init__(coordinator, key)
        self._figure = figure
        self._attr_state_class = state_class

    @property
    def available(self) -> bool:
        return super().available and self._figure in self.coordinator.data.figures

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.figures.get(self._figure)


class BridgeReachable(BridgeEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BridgeCoordinator) -> None:
        super().__init__(coordinator, "bridge_reachable")

    @property
    def available(self) -> bool:
        return True  # it says the other entities are not

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


def async_add_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [BridgeStatus(coordinator), BridgeVersion(coordinator)]
        + [BridgeFigure(coordinator, key, figure, state_class) for key, figure, state_class in FIGURES]
    )


def async_add_binary_sensors(entry: BridgeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([BridgeReachable(entry.runtime_data)])
