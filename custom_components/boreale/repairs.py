"""Repairs that can be fixed from here: the console's own Home Assistant device is back, its entities twice;
a Lantern bridge cannot read one of its sources (ask it to read them again)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .bridge import RESCAN, BridgeHub


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


class BridgeRescanRepair(ConfirmRepairFlow):
    """Asks the bridge to read its sources again."""

    def __init__(self, entry_id: str | None) -> None:
        self._entry_id = entry_id

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        if user_input is not None and self._entry_id:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if (
                entry is not None
                and entry.state is ConfigEntryState.LOADED
                and isinstance(entry.runtime_data, BridgeHub)
            ):
                await entry.runtime_data.async_rescan()
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    """The fixable issues: the console's own discovery, and a bridge's source that does not answer."""
    if (data or {}).get("kind") == RESCAN:
        return BridgeRescanRepair(data.get("entry_id") if data else None)
    return NativeDiscoveryRepair((data or {}).get("entry_id"))
