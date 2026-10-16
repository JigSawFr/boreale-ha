"""Diagnostics: what the console last published, its last report included."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PlayGuardConfigEntry

# What may name someone: the console's name (often a child's), the saved
# profiles' names, the accounts' ids. Game names go too (the ids stay).
TO_REDACT = {"name", "profiles", "uid"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PlayGuardConfigEntry) -> dict[str, Any]:
    """The documents as received, less what may name someone. PlayGuard
    never publishes the PIN, the serial number or the broker's credentials;
    the report is the one the console published (Remote access › Publish the
    diagnostic reports)."""
    console = entry.runtime_data
    return async_redact_data(
        {
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "online": console.online,
            "state": console.state,
            "activity": console.activity,
            "week": console.week,
            "names": {
                "games": len((console.names or {}).get("games") or {}),
                "accounts": len((console.names or {}).get("accounts") or {}),
            },
            "finished_days": sorted(console.finals),
            "last_event": console.last_event,
            "report": console.report,
        },
        TO_REDACT,
    )
