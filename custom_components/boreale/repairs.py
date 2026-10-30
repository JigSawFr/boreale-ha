"""Repairs: the console's own Home Assistant device is back, its entities twice."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


class NativeDiscoveryRepair(ConfirmRepairFlow):
    """Asks the console again to turn its own discovery off."""

    def __init__(self, entry_id: str | None) -> None:
        self._entry_id = entry_id

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        if user_input is not None and self._entry_id:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is not None and entry.state is ConfigEntryState.LOADED:
                await entry.runtime_data.async_turn_native_off()
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    """The only fixable issue: the console's own discovery."""
    return NativeDiscoveryRepair((data or {}).get("entry_id"))
