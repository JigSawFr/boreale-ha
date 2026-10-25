"""The console's entities: PlayGuard's table (source/sync/sync_entities.c).

Same object ids, names, platforms, write classes and options as the native
MQTT discovery the console publishes, so that taking over from it gives the
same entities (Home Assistant picks their entity ids). tests/test_parity.py
checks this table against the entities.json PlayGuard's host tests export. A
few entities exist only here (`extra`).
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfInformation, UnitOfTemperature, UnitOfTime

from .const import DAYS, RESTRICTION_OPTIONS, RESTRICTION_RENAMED, WRITE_FREE, WRITE_NONE, WRITE_TIMER


@dataclass(frozen=True, kw_only=True)
class EntityDef:
    """One entity of the console."""

    key: str  # object id, and the order's topic level
    platform: Platform
    write: str = WRITE_NONE
    topic: str = "state"  # the document `path` reads: "state", "system" or "games"
    path: tuple[str, ...] | None = None  # where the value is in that document
    fallback: tuple[str, ...] | None = None  # read when `path` gives nothing
    category: str | None = None  # "config" or "diagnostic"
    enabled: bool = True
    unit: str | None = None
    device_class: str | None = None
    state_class: SensorStateClass | None = None
    options: tuple[str, ...] | None = None
    renamed: tuple[tuple[str, str], ...] = ()  # (value in the state and the order, option shown)
    minimum: int | None = None
    maximum: int | None = None
    step: int | None = None
    extra: bool = False  # this integration's own: not in PlayGuard's table


def _binary(key: str, path: tuple[str, ...], **kw) -> EntityDef:
    return EntityDef(key=key, platform=Platform.BINARY_SENSOR, path=path, **kw)


def _minutes(key: str, path: tuple[str, ...], state_class: SensorStateClass | None = None, **kw) -> EntityDef:
    return EntityDef(
        key=key,
        platform=Platform.SENSOR,
        path=path,
        unit=UnitOfTime.MINUTES,
        device_class="duration",
        state_class=state_class,
        **kw,
    )


def _limit(key: str, path: tuple[str, ...]) -> EntityDef:
    return EntityDef(
        key=key,
        platform=Platform.NUMBER,
        write=WRITE_TIMER,
        path=path,
        category="config",
        unit=UnitOfTime.MINUTES,
        device_class="duration",
        minimum=0,
        maximum=1440,
        step=5,
    )


def _switch(key: str, path: tuple[str, ...], write: str = WRITE_TIMER, **kw) -> EntityDef:
    return EntityDef(key=key, platform=Platform.SWITCH, write=write, path=path, **kw)


def _button(key: str, write: str, **kw) -> EntityDef:
    return EntityDef(key=key, platform=Platform.BUTTON, write=write, **kw)


def _system(key: str, path: tuple[str, ...], platform: Platform = Platform.SENSOR, **kw) -> EntityDef:
    """An entity of the system document (the console itself)."""
    return EntityDef(key=key, platform=platform, topic="system", path=path, **kw)


def _space(key: str, path: tuple[str, ...], **kw) -> EntityDef:
    return _system(
        key,
        path,
        unit=UnitOfInformation.MEBIBYTES,
        device_class="data_size",
        state_class=SensorStateClass.MEASUREMENT,
        **kw,
    )


MODELS = ("erista", "mariko", "lite", "oled", "other")
REGIONS = ("jpn", "usa", "eur", "aus", "htk", "chn")


ENTITIES: tuple[EntityDef, ...] = (
    # binary sensors
    _binary("parental_controls_enabled", ("controls", "enabled")),
    _binary("temp_unlocked", ("controls", "temp_unlocked"), device_class="lock"),
    _binary("pin_set", ("controls", "pin_set"), category="diagnostic"),
    _binary("companion_linked", ("controls", "companion_linked")),
    _binary("timer_enabled", ("timer", "enabled")),
    _binary("limit_reached", ("timer", "limit_reached")),
    _binary("clock_accurate", ("clock_accurate",), category="diagnostic"),
    # sensors
    # A day's play time, back to 0 at midnight: a daily total.
    _minutes("used_screen_time", ("timer", "used_min"), SensorStateClass.TOTAL_INCREASING),
    _minutes("used_screen_time_log", ("activity_today", "used_min"), SensorStateClass.TOTAL_INCREASING),
    _minutes("screen_time_remaining", ("timer", "remaining_min"), SensorStateClass.MEASUREMENT),
    _minutes("extended_screen_time", ("timer", "extended_today_min")),
    EntityDef(
        key="now_playing",
        platform=Platform.SENSOR,
        path=("activity_today", "now_playing", "name"),
        fallback=("activity_today", "now_playing", "app_id"),
    ),
    EntityDef(key="rating_age", platform=Platform.SENSOR, path=("controls", "rating_age"), category="diagnostic"),
    EntityDef(key="firmware", platform=Platform.SENSOR, path=("console", "firmware"), category="diagnostic"),
    EntityDef(key="atmosphere", platform=Platform.SENSOR, path=("console", "atmosphere"), category="diagnostic"),
    _minutes("spent_raw", ("timer", "spent_raw_min"), category="diagnostic", enabled=False),
    EntityDef(key="last_order", platform=Platform.SENSOR, path=("link", "last_result"), category="diagnostic"),
    # limits
    *(_limit(f"limit_{day}", ("timer", "limits", day)) for day in DAYS),
    _limit("limit_uniform", ("timer", "uniform_min")),
    _limit("max_screentime_today", ("timer", "limit_today_min")),
    # bedtime
    EntityDef(
        key="bedtime_alarm",
        platform=Platform.TIME,
        write=WRITE_TIMER,
        path=("timer", "bedtime", "start"),
        category="config",
    ),
    EntityDef(
        key="bedtime_end_time",
        platform=Platform.TIME,
        write=WRITE_TIMER,
        path=("timer", "bedtime", "end"),
        category="config",
    ),
    _switch("bedtime_enabled", ("timer", "bedtime", "enabled"), category="config"),
    # switches
    _switch("console_lock", ("timer", "console_locked")),
    _switch("play_timer_alarm", ("timer", "alarm_on"), category="config"),
    _switch("unlocked", ("controls", "temp_unlocked")),
    _switch("vr_restricted", ("controls", "vr_restricted"), write=WRITE_FREE, category="config"),
    _switch("sns_post_restricted", ("controls", "sns_post_restricted"), write=WRITE_FREE, category="config"),
    _switch(
        "free_communication_restricted",
        ("controls", "free_communication_restricted"),
        write=WRITE_FREE,
        category="config",
    ),
    # selects (the profiles come from the state's "profiles")
    EntityDef(
        key="restriction_level",
        platform=Platform.SELECT,
        write=WRITE_FREE,
        path=("controls", "level"),
        category="config",
        options=RESTRICTION_OPTIONS,
        renamed=RESTRICTION_RENAMED,
    ),
    EntityDef(key="profile", platform=Platform.SELECT, write=WRITE_TIMER, category="config"),
    # buttons
    _button("sync_now", WRITE_FREE, category="diagnostic"),
    _button("lock_now", WRITE_FREE),
    _button("export_report", WRITE_FREE, category="diagnostic"),
    _button("add_bonus_time_15", WRITE_TIMER),
    _button("add_bonus_time_30", WRITE_TIMER),
    _button("add_bonus_time_60", WRITE_TIMER),
    _button("stop_today", WRITE_TIMER),
    _button("remove_limit", WRITE_TIMER),
    # events (the console's "event" topic)
    EntityDef(key="events", platform=Platform.EVENT),
    # the console itself (the system document)
    _system("model", ("hardware", "model"), device_class="enum", options=MODELS, category="diagnostic"),
    _system("nickname", ("hardware", "nickname"), category="diagnostic"),
    _system("region", ("hardware", "region"), device_class="enum", options=REGIONS, category="diagnostic"),
    _system("hekate", ("versions", "hekate"), category="diagnostic"),
    _system(
        "system_storage",
        ("hardware", "system"),
        device_class="enum",
        options=("sysmmc", "emummc"),
        category="diagnostic",
    ),
    _system("prodinfo_blanked", ("hardware", "prodinfo_blanked"), Platform.BINARY_SENSOR, category="diagnostic"),
    # Only with "Publish the serial number" on the console.
    _system("serial", ("hardware", "serial"), category="diagnostic", enabled=False),
    _space("sd_free", ("storage", "sd", "free_mb")),
    _space("sd_total", ("storage", "sd", "total_mb"), category="diagnostic"),
    _space("nand_free", ("storage", "nand", "free_mb")),
    _space("nand_total", ("storage", "nand", "total_mb"), category="diagnostic"),
    _system(
        "battery",
        ("power", "battery_pct"),
        unit=PERCENTAGE,
        device_class="battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _system("charging", ("power", "charging"), Platform.BINARY_SENSOR, device_class="battery_charging"),
    _system("docked", ("power", "docked"), Platform.BINARY_SENSOR),
    _system(
        "temperature",
        ("power", "temperature_c"),
        unit=UnitOfTemperature.CELSIUS,
        device_class="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        category="diagnostic",
    ),
    _system(
        "network",
        ("network", "type"),
        device_class="enum",
        options=("none", "wifi", "ethernet"),
        category="diagnostic",
    ),
    _system("ip_address", ("network", "ip"), category="diagnostic"),
    _system("wifi_signal", ("network", "wifi_bars"), state_class=SensorStateClass.MEASUREMENT, category="diagnostic"),
    _system("ssid", ("network", "ssid"), category="diagnostic", enabled=False),
    _system("last_boot", ("boot_ts",), device_class="timestamp", category="diagnostic"),
    # the games (the games document); one sensor per game besides (sensor.py)
    EntityDef(
        key="games_installed",
        platform=Platform.SENSOR,
        topic="games",
        path=("installed",),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _minutes("play_time_total", ("total_min",), SensorStateClass.TOTAL_INCREASING, topic="games"),
    EntityDef(key="accounts", platform=Platform.SENSOR, topic="games", path=("accounts",), category="diagnostic"),
    # this integration's own
    _binary("online", ("availability",), device_class="connectivity", category="diagnostic", extra=True),
    _binary("agent", ("link", "agent"), device_class="running", category="diagnostic", enabled=False, extra=True),
    _minutes("week_play_time", ("week",), extra=True),
)

BY_KEY: dict[str, EntityDef] = {e.key: e for e in ENTITIES}

# Entities made as the console lists what they are for: their translation
# key, and platform. One sensor per game (sensor.py).
DYNAMIC: dict[str, Platform] = {"game": Platform.SENSOR}


def for_platform(platform: Platform) -> list[EntityDef]:
    """The entities of one platform."""
    return [e for e in ENTITIES if e.platform == platform]


def dig(doc: dict | None, path: tuple[str, ...] | None):
    """The value at `path` in a document, None when any step is missing."""
    value = doc
    for step in path or ():
        if not isinstance(value, dict):
            return None
        value = value.get(step)
    return value if path else None
