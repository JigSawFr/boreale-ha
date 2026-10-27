"""Constants of the PlayGuard integration.

The wire contract (topics, documents, orders) is PlayGuard's
docs/sync-protocol.md: https://github.com/JigSawFr/PlayGuard
"""

from __future__ import annotations

import re
from typing import Final

DOMAIN: Final = "playguard"

# The documents' schema this integration understands. A newer one raises a
# repair issue; the integration still reads what it knows.
SCHEMA: Final = 1

DEFAULT_PREFIX: Final = "playguard"
CONF_CONSOLE_ID: Final = "console_id"
CONF_PREFIX: Final = "topic_prefix"
# Turn the console's own Home Assistant discovery off (the integration's
# entities replace it).
CONF_TAKE_OVER: Final = "take_over_discovery"
# While the console is off the broker (asleep, off, out of reach), what it last
# said keeps showing: its sensors keep their last values, its controls are
# unavailable.
CONF_KEEP_VALUES: Final = "keep_values_asleep"
# A refusal that comes after the order's action returned (the console was
# asleep, or the order waited for PlayGuard) raises a notification.
CONF_NOTIFY_REFUSED: Final = "notify_refused"
# What PlayGuard last said it does not publish (in the entry's data, kept
# across restarts): those entities are not created.
CONF_UNPUBLISHED: Final = "unpublished"

CONSOLE_ID_RE: Final = re.compile(r"^[0-9a-f]{8}$")

DAYS: Final = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
# 1440 minutes means "no limit" on every topic and order.
NO_LIMIT: Final = 1440

# The restriction level's options. PlayGuard's level "none" is shown as
# "unrestricted", as in its own discovery (where Home Assistant would read
# "None" as unknown); the order still sends "none", which every PlayGuard
# version accepts.
RESTRICTION_OPTIONS: Final = ("unrestricted", "young_child", "child", "teen", "custom")
RESTRICTION_RENAMED: Final = (("none", "unrestricted"),)
# The events PlayGuard sends (sync_engine.c's event_type(), the ones its
# discovery declares).
EVENT_TYPES: Final = (
    "command_applied",
    "command_rejected",
    "command_waiting",
    # What the console does on its own (PlayGuard's sync_watch, from its agent).
    "play_started",
    "play_stopped",
    "time_warning",
    "play_blocked",
)

# How long an order's action waits for the console's answer while it is on
# the broker: refused, the action fails, saying why; no answer by then (or
# waiting for PlayGuard), the order stays on the broker and the action returns.
ORDER_TIMEOUT: Final = 10.0
# Why the console refuses an order (sync_apply.c's sync_reason_name()), each
# with its translation (exceptions.reason_<reason>); any other is shown as is.
REFUSAL_REASONS: Final = (
    "unknown_entity",
    "invalid",
    "out_of_range",
    "policy_off",
    "timer_writes_disabled",
    "read_only",
    "not_confirmed",
    "gated",
    "unlock_failed",
    "not_custom",
    "no_such_profile",
    "no_limit_today",
    "console_locked",
    "unsupported",
    "bedtime_off",
    "pctl_error",
    "busy",
)

# Each of the console's events, also on Home Assistant's event bus (with the
# console's device), for the logbook.
EVENT_PLAYGUARD: Final = "playguard_event"

# Write classes of the entity table (source/sync/sync_entities.c).
WRITE_NONE: Final = "none"
WRITE_FREE: Final = "free"  # an order, refused only in read-only mode or under the "off" policy
WRITE_TIMER: Final = "timer"  # also needs "Orders may change the play timer" on the console

# What an entity shows (PlayGuard's sync.conf publish_* switches, the state's
# link.publishes): the parental controls always, the rest while published.
PUBLISH_CONTROLS: Final = "controls"
PUBLISH_ACTIVITY: Final = "activity"
PUBLISH_GAMES: Final = "games"
PUBLISH_ICONS: Final = "icons"
PUBLISH_CONSOLE: Final = "console"
PUBLISH_NETWORK: Final = "network"
PUBLISH_HARDWARE: Final = "hardware"
PUBLISH_SERIAL: Final = "serial"

# The device is the console as Nintendo names it (PlayGuard's discovery):
# hardware.model -> (model, model number).
MANUFACTURER: Final = "Nintendo"
MODEL: Final = "Nintendo Switch"
MODEL_NAMES: Final = {
    "erista": ("Nintendo Switch", "HAC-001"),
    "mariko": ("Nintendo Switch", "HAC-001(-01)"),
    "lite": ("Nintendo Switch Lite", "HDH-001"),
    "oled": ("Nintendo Switch \u2013 OLED Model", "HEG-001"),
}

# States that may still say the console's own discovery is on after it was
# asked off (one published before the order was handled): more mean the
# same entities twice, and a repair issue.
NATIVE_STATES_MAX: Final = 2

# Finished days are imported as long-term statistics a moment after the last
# one arrives (the broker hands the retained ones over in a burst).
STATISTICS_DELAY: Final = 5.0

# Entities an earlier version had, removed by the migration to 1.3 (the
# lock Parental controls does all three): (platform, key).
RETIRED: Final = (("binary_sensor", "temp_unlocked"), ("switch", "unlocked"), ("button", "lock_now"))

# Where the integration tells the console which version runs (retained, at
# every set-up; cleared when the entry is removed): PlayGuard warns of a
# newer release of the integration.
TOPIC_INTEGRATION: Final = "integration"
