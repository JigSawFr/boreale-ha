"""Intents, for Assist and for the assistants that use Home Assistant's LLM
API: today's play time on a console, extra time, no more play today. Their
sentences are the user's (custom_sentences); an LLM assistant calls them as
tools (llm.py)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.translation import async_get_translations
import probatio

from . import play
from .const import DOMAIN, WRITE_TIMER
from .coordinator import PlayGuardConsole

INTENT_PLAY_TIME = "PlayGuardPlayTime"
INTENT_ADD_TIME = "PlayGuardAddTime"
INTENT_STOP_TODAY = "PlayGuardStopToday"

SLOT_NAME = "name"
SLOT_MINUTES = "minutes"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Registers the intents (once, for every console)."""
    intent.async_register(hass, PlayTimeIntent())
    intent.async_register(hass, AddTimeIntent())
    intent.async_register(hass, StopTodayIntent())


def _consoles(hass: HomeAssistant) -> list[PlayGuardConsole]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


async def _texts(hass: HomeAssistant, language: str) -> dict[str, str]:
    return await async_get_translations(hass, language, "exceptions", [DOMAIN])


def _say(texts: dict[str, str], key: str, **values: Any) -> str:
    text = texts.get(f"component.{DOMAIN}.exceptions.intent_{key}.message", key)
    return text.format(**values)


class PlayGuardIntent(intent.IntentHandler):
    """An intent about one console: by its name, or the only one."""

    platforms = None

    @property
    def slot_schema(self) -> dict[Any, Any] | None:
        return {probatio.Optional(SLOT_NAME): cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        texts = await _texts(hass, intent_obj.language)
        slots = self.async_validate_slots(intent_obj.slots)
        consoles = _consoles(hass)
        wanted = (slots.get(SLOT_NAME) or {}).get("value")
        if wanted:
            consoles = [c for c in consoles if c.name.casefold() == str(wanted).strip().casefold()]
            if not consoles:
                raise intent.IntentHandleError(_say(texts, "no_console", name=wanted))
        elif len(consoles) > 1:
            raise intent.IntentHandleError(_say(texts, "which", names=", ".join(c.name for c in consoles)))
        if not consoles:
            raise intent.IntentHandleError(_say(texts, "no_console", name=""))
        response = intent_obj.create_response()
        try:
            speech, data = await self._async_run(consoles[0], slots, texts)
        except HomeAssistantError as err:  # refused, here or by the console
            raise intent.IntentHandleError(str(err)) from err
        response.async_set_speech(speech)
        response.async_set_speech_slots(data)
        return response

    async def _async_run(
        self, console: PlayGuardConsole, slots: dict[str, Any], texts: dict[str, str]
    ) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError


class PlayTimeIntent(PlayGuardIntent):
    intent_type = INTENT_PLAY_TIME
    description = (
        "Tells how long the children played today on a Nintendo Switch with PlayGuard: the play time, "
        "the game being played, the day's limit and the minutes left, whether games are blocked."
    )

    async def _async_run(
        self, console: PlayGuardConsole, slots: dict[str, Any], texts: dict[str, str]
    ) -> tuple[str, dict[str, Any]]:
        today = play.today(console)
        said = [_say(texts, "played", name=console.name, minutes=today["minutes"] or 0)]
        if today["now_playing"]:
            said.append(_say(texts, "playing", game=today["now_playing"]["name"]))
        if today["blocked"]:
            said.append(_say(texts, "blocked"))
        elif today["limit_minutes"] is None:
            said.append(_say(texts, "no_limit"))
        elif today["remaining_minutes"] is not None:
            said.append(_say(texts, "left", minutes=today["remaining_minutes"]))
        return " ".join(said), {"console": console.name, **today}


class AddTimeIntent(PlayGuardIntent):
    intent_type = INTENT_ADD_TIME
    description = "Gives extra play time today on a Nintendo Switch with PlayGuard (5 to 180 minutes)."

    @property
    def slot_schema(self) -> dict[Any, Any] | None:
        return {
            probatio.Optional(SLOT_NAME): cv.string,
            probatio.Required(SLOT_MINUTES): probatio.All(probatio.Coerce(int), probatio.Range(min=5, max=180)),
        }

    async def _async_run(
        self, console: PlayGuardConsole, slots: dict[str, Any], texts: dict[str, str]
    ) -> tuple[str, dict[str, Any]]:
        minutes = slots[SLOT_MINUTES]["value"]
        await console.async_order("add_bonus_time", WRITE_TIMER, str(minutes))
        return _say(texts, "added", name=console.name, minutes=minutes), {"console": console.name, "minutes": minutes}


class StopTodayIntent(PlayGuardIntent):
    intent_type = INTENT_STOP_TODAY
    description = (
        "Stops play for the rest of today on a Nintendo Switch with PlayGuard (the usual limit is back tomorrow)."
    )

    async def _async_run(
        self, console: PlayGuardConsole, slots: dict[str, Any], texts: dict[str, str]
    ) -> tuple[str, dict[str, Any]]:
        await console.async_order("stop_today", WRITE_TIMER, "PRESS")
        return _say(texts, "stopped", name=console.name), {"console": console.name}
