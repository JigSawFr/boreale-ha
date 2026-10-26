"""The console's entities: PlayGuard's table (source/sync/sync_entities.c).

Same object ids, names, platforms, write classes and options as the native
MQTT discovery the console publishes, so that taking over from it gives the
same entities (Home Assistant picks their entity ids). tests/test_parity.py
checks this table against the entities.json PlayGuard's host tests export. A
few entities exist only here (`extra`). Units stay PlayGuard's (minutes,
MiB); Home Assistant shows some in a larger one (`suggested_unit`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfInformation, UnitOfTemperature, UnitOfTime

from .const import (
    DAYS,
    PUBLISH_ACTIVITY,
    PUBLISH_CONSOLE,
    PUBLISH_CONTROLS,
    PUBLISH_GAMES,
    PUBLISH_HARDWARE,
    PUBLISH_NETWORK,
    PUBLISH_SERIAL,
    RESTRICTION_OPTIONS,
    RESTRICTION_RENAMED,
    WRITE_FREE,
    WRITE_NONE,
    WRITE_TIMER,
)


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
    suggested_unit: str | None = None  # the unit Home Assistant shows it in
    precision: int | None = None  # the decimals Home Assistant shows
    publish: str = PUBLISH_CONTROLS  # what it shows: there while PlayGuard publishes it (link.publishes)
    extra: bool = False  # this integration's own: not in PlayGuard's table


def _binary(key: str, path: tuple[str, ...], **kw: Any) -> EntityDef:
    return EntityDef(key=key, platform=Platform.BINARY_SENSOR, path=path, **kw)


def _minutes(key: str, path: tuple[str, ...], state_class: SensorStateClass | None = None, **kw: Any) -> EntityDef:
    return EntityDef(
        key=key,
        platform=Platform.SENSOR,
        path=path,
        unit=UnitOfTime.MINUTES,
        device_class="duration",
        state_class=state_class,
        **kw,
    )


def _limit(key: str, path: tuple[str, ...], **kw: Any) -> EntityDef:
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
        **kw,
    )


def _switch(key: str, path: tuple[str, ...], write: str = WRITE_TIMER, **kw: Any) -> EntityDef:
    return EntityDef(key=key, platform=Platform.SWITCH, write=write, path=path, **kw)


def _button(key: str, write: str, **kw: Any) -> EntityDef:
    return EntityDef(key=key, platform=Platform.BUTTON, write=write, **kw)


def _system(
    key: str, path: tuple[str, ...], publish: str, platform: Platform = Platform.SENSOR, **kw: Any
) -> EntityDef:
    """An entity of the system document (the console itself)."""
    return EntityDef(key=key, platform=platform, topic="system", path=path, publish=publish, **kw)


def _space(key: str, path: tuple[str, ...], **kw: Any) -> EntityDef:
    """Free space or a size: MiB, shown in GiB."""
    return _system(
        key,
        path,
        PUBLISH_CONSOLE,
        unit=UnitOfInformation.MEBIBYTES,
        device_class="data_size",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_unit=UnitOfInformation.GIBIBYTES,
        precision=1,
        **kw,
    )


MODELS = ("erista", "mariko", "lite", "oled", "other")
REGIONS = ("jpn", "usa", "eur", "aus", "htk", "chn")


# `enabled=False`: off until turned on on the device page, as in PlayGuard's
# table: the rarely needed (what few dashboards show) and the private (the
# serial number, the Wi-Fi network's name).
ENTITIES: tuple[EntityDef, ...] = (
    # binary sensors
    _binary("parental_controls_enabled", ("controls", "enabled")),
    _binary("pin_set", ("controls", "pin_set"), category="diagnostic"),
    _binary("companion_linked", ("controls", "companion_linked")),
    _binary("timer_enabled", ("timer", "enabled")),
    _binary("limit_reached", ("timer", "limit_reached")),
    _binary("clock_accurate", ("clock_accurate",), category="diagnostic", enabled=False),
    # sensors
    # A day's play time, back to 0 at midnight: a daily total. The play log's
    # is today's play time; the play timer's own count (only while a limit
    # is set) is off.
    _minutes("used_screen_time", ("timer", "used_min"), SensorStateClass.TOTAL_INCREASING, enabled=False),
    _minutes(
        "used_screen_time_log",
        ("activity_today", "used_min"),
        SensorStateClass.TOTAL_INCREASING,
        publish=PUBLISH_ACTIVITY,
    ),
    _minutes("screen_time_remaining", ("timer", "remaining_min"), SensorStateClass.MEASUREMENT),
    _minutes("extended_screen_time", ("timer", "extended_today_min")),
    EntityDef(
        key="now_playing",
        platform=Platform.SENSOR,
        path=("activity_today", "now_playing", "name"),
        fallback=("activity_today", "now_playing", "app_id"),
        publish=PUBLISH_ACTIVITY,
    ),
    EntityDef(
        key="rating_age",
        platform=Platform.SENSOR,
        path=("controls", "rating_age"),
        category="diagnostic",
        enabled=False,
    ),
    EntityDef(
        key="firmware",
        platform=Platform.SENSOR,
        path=("console", "firmware"),
        category="diagnostic",
        publish=PUBLISH_HARDWARE,
    ),
    EntityDef(
        key="atmosphere",
        platform=Platform.SENSOR,
        path=("console", "atmosphere"),
        category="diagnostic",
        publish=PUBLISH_HARDWARE,
    ),
    _minutes("spent_raw", ("timer", "spent_raw_min"), category="diagnostic", enabled=False),
    EntityDef(
        key="last_order",
        platform=Platform.SENSOR,
        path=("link", "last_result"),
        category="diagnostic",
        enabled=False,
    ),
    # limits: the day's and every day's on, each day's off until wanted
    *(_limit(f"limit_{day}", ("timer", "limits", day), enabled=False) for day in DAYS),
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
    _switch("vr_restricted", ("controls", "vr_restricted"), write=WRITE_FREE, category="config"),
    _switch("sns_post_restricted", ("controls", "sns_post_restricted"), write=WRITE_FREE, category="config"),
    _switch(
        "free_communication_restricted",
        ("controls", "free_communication_restricted"),
        write=WRITE_FREE,
        category="config",
    ),
    # the lock: locked while parental controls are in effect (set up, not
    # temporarily unlocked); unlocking needs "Orders may change the play
    # timer", locking again never does
    EntityDef(key="parental_controls", platform=Platform.LOCK, write=WRITE_FREE, path=("controls", "temp_unlocked")),
    # selects (the profiles come from the state's "profiles", the one in
    # effect from the timer's "profile")
    EntityDef(
        key="restriction_level",
        platform=Platform.SELECT,
        write=WRITE_FREE,
        path=("controls", "level"),
        category="config",
        options=RESTRICTION_OPTIONS,
        renamed=RESTRICTION_RENAMED,
    ),
    EntityDef(key="profile", platform=Platform.SELECT, write=WRITE_TIMER, path=("timer", "profile"), category="config"),
    # buttons
    _button("sync_now", WRITE_FREE, category="diagnostic"),
    _button("export_report", WRITE_FREE, category="diagnostic", enabled=False),
    _button("add_bonus_time_15", WRITE_TIMER),
    _button("add_bonus_time_30", WRITE_TIMER),
    _button("add_bonus_time_60", WRITE_TIMER),
    _button("stop_today", WRITE_TIMER),
    _button("remove_limit", WRITE_TIMER),
    # events (the console's "event" topic)
    EntityDef(key="events", platform=Platform.EVENT),
    # the console itself (the system document)
    _system(
        "model",
        ("hardware", "model"),
        PUBLISH_HARDWARE,
        device_class="enum",
        options=MODELS,
        category="diagnostic",
        enabled=False,
    ),
    _system("nickname", ("hardware", "nickname"), PUBLISH_HARDWARE, category="diagnostic", enabled=False),
    _system(
        "region",
        ("hardware", "region"),
        PUBLISH_HARDWARE,
        device_class="enum",
        options=REGIONS,
        category="diagnostic",
        enabled=False,
    ),
    _system("hekate", ("versions", "hekate"), PUBLISH_HARDWARE, category="diagnostic", enabled=False),
    _system(
        "system_storage",
        ("hardware", "system"),
        PUBLISH_HARDWARE,
        device_class="enum",
        options=("sysmmc", "emummc"),
        category="diagnostic",
        enabled=False,
    ),
    _system(
        "prodinfo_blanked",
        ("hardware", "prodinfo_blanked"),
        PUBLISH_HARDWARE,
        Platform.BINARY_SENSOR,
        category="diagnostic",
        enabled=False,
    ),
    # Only with "Publish the serial number" on the console.
    _system("serial", ("hardware", "serial"), PUBLISH_SERIAL, category="diagnostic", enabled=False),
    _space("sd_free", ("storage", "sd", "free_mb")),
    _space("sd_total", ("storage", "sd", "total_mb"), category="diagnostic", enabled=False),
    _space("nand_free", ("storage", "nand", "free_mb")),
    _space("nand_total", ("storage", "nand", "total_mb"), category="diagnostic", enabled=False),
    _system(
        "battery",
        ("power", "battery_pct"),
        PUBLISH_CONSOLE,
        unit=PERCENTAGE,
        device_class="battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _system(
        "charging", ("power", "charging"), PUBLISH_CONSOLE, Platform.BINARY_SENSOR, device_class="battery_charging"
    ),
    _system("docked", ("power", "docked"), PUBLISH_CONSOLE, Platform.BINARY_SENSOR),
    _system(
        "temperature",
        ("power", "temperature_c"),
        PUBLISH_CONSOLE,
        unit=UnitOfTemperature.CELSIUS,
        device_class="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        precision=0,
        category="diagnostic",
        enabled=False,
    ),
    _system(
        "network",
        ("network", "type"),
        PUBLISH_NETWORK,
        device_class="enum",
        options=("none", "wifi", "ethernet"),
        category="diagnostic",
        enabled=False,
    ),
    _system("ip_address", ("network", "ip"), PUBLISH_NETWORK, category="diagnostic", enabled=False),
    _system(
        "wifi_signal",
        ("network", "wifi_bars"),
        PUBLISH_NETWORK,
        state_class=SensorStateClass.MEASUREMENT,
        category="diagnostic",
        enabled=False,
    ),
    _system("ssid", ("network", "ssid"), PUBLISH_NETWORK, category="diagnostic", enabled=False),
    _system("last_boot", ("boot_ts",), PUBLISH_CONSOLE, device_class="timestamp", category="diagnostic", enabled=False),
    # the games (the games document), each game listed on Games installed
    EntityDef(
        key="games_installed",
        platform=Platform.SENSOR,
        topic="games",
        path=("installed",),
        state_class=SensorStateClass.MEASUREMENT,
        publish=PUBLISH_GAMES,
    ),
    _minutes(
        "play_time_total",
        ("total_min",),
        SensorStateClass.TOTAL_INCREASING,
        topic="games",
        suggested_unit=UnitOfTime.HOURS,
        precision=1,
        publish=PUBLISH_GAMES,
    ),
    EntityDef(
        key="accounts",
        platform=Platform.SENSOR,
        topic="games",
        path=("accounts",),
        category="diagnostic",
        enabled=False,
        publish=PUBLISH_GAMES,
    ),
    # this integration's own
    _binary("online", ("availability",), device_class="connectivity", category="diagnostic", extra=True),
    _binary("agent", ("link", "agent"), device_class="running", category="diagnostic", enabled=False, extra=True),
    _minutes(
        "week_play_time",
        ("week",),
        suggested_unit=UnitOfTime.HOURS,
        precision=1,
        publish=PUBLISH_ACTIVITY,
        extra=True,
    ),
    # When play has to stop: the end of today's limit or bedtime, whichever
    # comes first, while a game is played.
    EntityDef(key="play_ends", platform=Platform.SENSOR, device_class="timestamp", extra=True),
    # When the console last said something (any of its documents): it
    # publishes its state every poll_s seconds while awake.
    EntityDef(
        key="last_seen",
        platform=Platform.SENSOR,
        device_class="timestamp",
        category="diagnostic",
        extra=True,
    ),
)

BY_KEY: dict[str, EntityDef] = {e.key: e for e in ENTITIES}


def for_platform(platform: Platform, unpublished: frozenset[str] = frozenset()) -> list[EntityDef]:
    """The entities of one platform, but those of what is not published."""
    return [e for e in ENTITIES if e.platform == platform and e.publish not in unpublished]


def dig(doc: dict[str, Any] | None, path: tuple[str, ...] | None) -> Any:
    """The value at `path` in a document, None when any step is missing."""
    value = doc
    for step in path or ():
        if not isinstance(value, dict):
            return None
        value = value.get(step)
    return value if path else None
