"""The console's events in the logbook: "Salon started Mario Kart 8 Deluxe",
"Salon refused Limit Monday: 5000: value out of range"."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook.const import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.translation import async_get_cached_translations

from .const import DOMAIN, EVENT_PLAYGUARD
from .coordinator import PlayGuardConsole


def _console(hass: HomeAssistant, console_id: Any) -> PlayGuardConsole | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED and entry.runtime_data.console_id == console_id:
            console: PlayGuardConsole = entry.runtime_data
            return console
    return None


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describes the console's events."""

    @callback
    def describe(event: Event) -> dict[str, str]:
        data = dict(event.data)
        event_type = str(data.get("event_type"))
        console = _console(hass, data.get("console_id"))
        texts = async_get_cached_translations(hass, hass.config.language, "exceptions", DOMAIN)
        key = f"{event_type}_{data.get('blocked_by')}" if event_type == "play_blocked" else event_type
        text = texts.get(f"component.{DOMAIN}.exceptions.logbook_{key}.message")
        values = {
            "game": data.get("game") or data.get("app_id") or "?",
            "minutes": data.get("minutes_left"),
            "order": console.order_text(data) if console else str(data.get("entity")),
            "reason": console.reason_text(data, texts) if console else str(data.get("reason")),
        }
        return {
            LOGBOOK_ENTRY_NAME: console.name if console else "PlayGuard",
            LOGBOOK_ENTRY_MESSAGE: text.format(**values) if text else event_type,
        }

    async_describe_event(DOMAIN, EVENT_PLAYGUARD, describe)
