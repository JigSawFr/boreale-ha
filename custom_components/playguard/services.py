"""Services: the same scalar orders as the entities, with the same bounds;
and the play time, as a response."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
import probatio

from . import play
from .const import DAYS, DOMAIN, WRITE_FREE, WRITE_TIMER
from .coordinator import PlayGuardConsole

ATTR_DEVICE_ID = "device_id"
ATTR_MINUTES = "minutes"
ATTR_DAY = "day"
ATTR_WEEK = "week"
ATTR_PROFILE = "profile"
ATTR_PERIOD = "period"

_LIMIT = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=1440))

SET_LIMITS_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(ATTR_DEVICE_ID): cv.string,
            probatio.Optional(ATTR_MINUTES): _LIMIT,
            probatio.Optional(ATTR_DAY, default="all"): probatio.In(("all", "today", *DAYS)),
            probatio.Optional(ATTR_WEEK): probatio.All(cv.ensure_list, [_LIMIT], probatio.Length(min=7, max=7)),
        }
    ),
    cv.has_at_least_one_key(ATTR_MINUTES, ATTR_WEEK),
)
BONUS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Required(ATTR_MINUTES): probatio.All(probatio.Coerce(int), probatio.Range(min=5, max=180)),
    }
)
PROFILE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Required(ATTR_PROFILE): probatio.All(cv.string, probatio.Length(min=1, max=32)),
    }
)
DEVICE_SCHEMA = probatio.Schema({probatio.Required(ATTR_DEVICE_ID): cv.string})
PLAY_TIME_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Optional(ATTR_PERIOD, default="today"): probatio.In(("today", "week")),
    }
)

# Service -> (order, write class) for the ones that take no value.
PRESS = {
    "stop_today": ("stop_today", WRITE_TIMER),
    "lock_now": ("lock_now", WRITE_FREE),
    "sync_now": ("sync_now", WRITE_FREE),
    "request_report": ("export_report", WRITE_FREE),
}


def _console(hass: HomeAssistant, device_id: str) -> PlayGuardConsole:
    """The console of a device. Home Assistant refuses, saying why, a device
    that is not a PlayGuard console's or whose entry is not loaded."""
    _device, entry = service.async_get_device_and_config_entry(hass, DOMAIN, device_id)
    console: PlayGuardConsole = entry.runtime_data
    return console


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

    async def get_play_time(call: ServiceCall) -> ServiceResponse:
        console = _console(hass, call.data[ATTR_DEVICE_ID])
        summary = play.week(console) if call.data[ATTR_PERIOD] == "week" else play.today(console)
        return {"console": console.name, **summary}

    hass.services.async_register(DOMAIN, "set_limits", set_limits, schema=SET_LIMITS_SCHEMA)
    hass.services.async_register(DOMAIN, "add_bonus_time", add_bonus_time, schema=BONUS_SCHEMA)
    hass.services.async_register(DOMAIN, "apply_profile", apply_profile, schema=PROFILE_SCHEMA)
    hass.services.async_register(
        DOMAIN, "get_play_time", get_play_time, schema=PLAY_TIME_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    for name in PRESS:
        hass.services.async_register(DOMAIN, name, press, schema=DEVICE_SCHEMA)
