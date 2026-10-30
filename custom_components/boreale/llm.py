"""The intents as tools of Home Assistant's LLM API (Assist), while one of
the consoles' entities is exposed to the assistant."""

from __future__ import annotations

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool, ToolAnnotations

from .const import DOMAIN
from .intent import INTENT_ADD_TIME, INTENT_PLAY_TIME, INTENT_STOP_TODAY

TOOLS = {
    INTENT_PLAY_TIME: ("Switch play time", ToolAnnotations(read_only=True, open_world=False)),
    INTENT_ADD_TIME: ("Give extra play time", ToolAnnotations(destructive=False, open_world=False)),
    INTENT_STOP_TODAY: ("No more play today", ToolAnnotations(destructive=False, idempotent=True, open_world=False)),
}


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext, api_id: str) -> LLMTools | None:
    """The tools, when the assistant sees one of the consoles' entities."""
    if api_id != LLM_API_ASSIST or not llm_context.assistant:
        return None
    registry = er.async_get(hass)
    if not any(
        async_should_expose(hass, llm_context.assistant, entry.entity_id)
        for entry in registry.entities.values()
        if entry.platform == DOMAIN
    ):
        return None
    tools: list[Tool] = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title=TOOLS[handler.intent_type][0],
            integration=DOMAIN,
            annotations=TOOLS[handler.intent_type][1],
        )  # fmt: skip
        for handler in intent.async_get(hass)
        if handler.intent_type in TOOLS
    ]
    return LLMTools(tools=tools)
