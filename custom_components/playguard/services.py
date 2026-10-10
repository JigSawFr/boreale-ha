"""Services: the same scalar orders as the entities, with the same bounds."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .const import DAYS, DOMAIN, WRITE_FREE, WRITE_TIMER

ATTR_DEVICE_ID = "device_id"
ATTR_MINUTES = "minutes"
ATTR_DAY = "day"
ATTR_WEEK = "week"
ATTR_PROFILE = "profile"

_LIMIT = vol.All(vol.Coerce(int), vol.Range(min=0, max=1440))

SET_LIMITS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Optional(ATTR_MINUTES): _LIMIT,
            vol.Optional(ATTR_DAY, default="all"): vol.In(("all", "today", *DAYS)),
            vol.Optional(ATTR_WEEK): vol.All(cv.ensure_list, [_LIMIT], vol.Length(min=7, max=7)),
        }
    ),
    cv.has_at_least_one_key(ATTR_MINUTES, ATTR_WEEK),
)
BONUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=5, max=180)),
    }
)
PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PROFILE): vol.All(cv.string, vol.Length(min=1, max=32)),
    }
)
DEVICE_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

# Service -> (order, write class) for the ones that take no value.
PRESS = {
    "stop_today": ("stop_today", WRITE_TIMER),
    "lock_now": ("lock_now", WRITE_FREE),
    "sync_now": ("sync_now", WRITE_FREE),
    "request_report": ("export_report", WRITE_FREE),
}


def _console(hass: HomeAssistant, device_id: str):
    """The console of a device."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == DOMAIN and getattr(entry, "runtime_data", None) is not None:
                return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="unknown_device", translation_placeholders={"device_id": device_id}
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Registers the services."""

    async def set_limits(call: ServiceCall) -> None:
        console = _console(hass, call.data[ATTR_DEVICE_ID])
        if ATTR_WEEK in call.data:
            await console.async_order("limits_week", WRITE_TIMER, ",".join(str(m) for m in call.data[ATTR_WEEK]))
            return
        day, minutes = call.data[ATTR_DAY], str(call.data[ATTR_MINUTES])
        key = {"all": "limit_uniform", "today": "max_screentime_today"}.get(day, f"limit_{day}")
        await console.async_order(key, WRITE_TIMER, minutes)

    async def add_bonus_time(call: ServiceCall) -> None:
        console = _console(hass, call.data[ATTR_DEVICE_ID])
        await console.async_order("add_bonus_time", WRITE_TIMER, str(call.data[ATTR_MINUTES]))

    async def apply_profile(call: ServiceCall) -> None:
        console = _console(hass, call.data[ATTR_DEVICE_ID])
        profile = call.data[ATTR_PROFILE]
        known = (console.state or {}).get("profiles")
        if isinstance(known, list) and profile not in known:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_such_profile",
                translation_placeholders={"profile": profile},
            )
        await console.async_order("profile", WRITE_TIMER, profile)

    async def press(call: ServiceCall) -> None:
        console = _console(hass, call.data[ATTR_DEVICE_ID])
        key, write = PRESS[call.service]
        await console.async_order(key, write, "PRESS")

    hass.services.async_register(DOMAIN, "set_limits", set_limits, schema=SET_LIMITS_SCHEMA)
    hass.services.async_register(DOMAIN, "add_bonus_time", add_bonus_time, schema=BONUS_SCHEMA)
    hass.services.async_register(DOMAIN, "apply_profile", apply_profile, schema=PROFILE_SCHEMA)
    for service in PRESS:
        hass.services.async_register(DOMAIN, service, press, schema=DEVICE_SCHEMA)
