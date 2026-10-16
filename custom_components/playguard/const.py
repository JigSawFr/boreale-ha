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
EVENT_TYPES: Final = ("command_applied", "command_rejected", "command_waiting")

# Write classes of the entity table (source/sync/sync_entities.c).
WRITE_NONE: Final = "none"
WRITE_FREE: Final = "free"  # an order, refused only in read-only mode or under the "off" policy
WRITE_TIMER: Final = "timer"  # also needs "Orders may change the play timer" on the console

MANUFACTURER: Final = "PlayGuard"
MODEL: Final = "Nintendo Switch"

# States that may still say the console's own discovery is on after it was
# asked off (one published before the order was handled): more mean the
# same entities twice, and a repair issue.
NATIVE_STATES_MAX: Final = 2

# Finished days are imported as long-term statistics a moment after the last
# one arrives (the broker hands the retained ones over in a burst).
STATISTICS_DELAY: Final = 5.0

# Where the integration tells the console which version runs (retained, at
# every set-up; cleared when the entry is removed): PlayGuard warns of a
# newer release of the integration.
TOPIC_INTEGRATION: Final = "integration"
