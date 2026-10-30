"""The console's triggers: a game started or stopped, a few minutes left,
games blocked, an order refused (its Events entity, by event type)."""

from __future__ import annotations

from typing import override

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    NotTriggeredReasonReporter,
    StatelessEntityTriggerBase,
    Trigger,
    TriggerConfig,
)
import probatio

from .automation import console_entities

CONF_BLOCKED_BY = "blocked_by"
BLOCKED_BY = ("limit", "bedtime")


class ConsoleEventTrigger(StatelessEntityTriggerBase):
    """One of the console's events, on its Events entity."""

    _domain_specs = {"event": DomainSpec()}
    _event_type: str

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        return console_entities(self._hass, super().entity_filter(entities), "events")

    @override
    def is_valid_state(self, state: State, report_not_triggered: NotTriggeredReasonReporter) -> bool:
        return state.attributes.get("event_type") == self._event_type


def _event_trigger(event_type: str) -> type[ConsoleEventTrigger]:
    class _Trigger(ConsoleEventTrigger):
        _event_type = event_type

    return _Trigger


class GamesBlockedTrigger(ConsoleEventTrigger):
    """Games blocked, by the day's limit, by bedtime, or either."""

    _event_type = "play_blocked"
    _schema = ENTITY_STATE_TRIGGER_SCHEMA.extend(
        {
            probatio.Required(CONF_OPTIONS, default={}): {
                probatio.Optional(CONF_BLOCKED_BY, default=list(BLOCKED_BY)): probatio.All(
                    probatio.EnsureList(), probatio.Length(min=1), [probatio.In(BLOCKED_BY)]
                ),
            },
        }
    )

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        super().__init__(hass, config)
        self._blocked_by = set(self._options[CONF_BLOCKED_BY])

    @override
    def is_valid_state(self, state: State, report_not_triggered: NotTriggeredReasonReporter) -> bool:
        return (
            super().is_valid_state(state, report_not_triggered)
            and state.attributes.get("blocked_by") in self._blocked_by
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "game_started": _event_trigger("play_started"),
    "game_stopped": _event_trigger("play_stopped"),
    "time_running_out": _event_trigger("time_warning"),
    "games_blocked": GamesBlockedTrigger,
    "order_refused": _event_trigger("command_rejected"),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """The console's triggers."""
    return TRIGGERS
