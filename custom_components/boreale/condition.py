"""The console's conditions: a game is played, the day's limit is reached,
parental controls are on (not unlocked for now)."""

from __future__ import annotations

from typing import override

from homeassistant.components.lock.const import LockState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, EntityConditionBase

from .automation import console_entities


class ConsoleCondition(EntityConditionBase):
    """One of the console's entities in a given state."""

    _key: str
    _states: frozenset[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        return console_entities(self._hass, super().entity_filter(entities), self._key)

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        return entity_state.state in self._states


class PlayingCondition(ConsoleCondition):
    """A game is played: Now playing names one (unknown when none is)."""

    _domain_specs = {"sensor": DomainSpec()}
    _key = "now_playing"

    @override
    def _should_include(self, _state: State) -> bool:
        return _state.state != STATE_UNAVAILABLE

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        return entity_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)


class LimitReachedCondition(ConsoleCondition):
    _domain_specs = {"binary_sensor": DomainSpec()}
    _key = "limit_reached"
    _states = frozenset({STATE_ON})


class ControlsOnCondition(ConsoleCondition):
    _domain_specs = {"lock": DomainSpec()}
    _key = "parental_controls"
    _states = frozenset({LockState.LOCKED})


CONDITIONS: dict[str, type[Condition]] = {
    "is_playing": PlayingCondition,
    "limit_reached": LimitReachedCondition,
    "parental_controls_on": ControlsOnCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """The console's conditions."""
    return CONDITIONS
