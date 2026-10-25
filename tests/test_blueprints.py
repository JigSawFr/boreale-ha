"""The blueprints (blueprints/automation/playguard): each one set up as an
automation from its file, then run against the console, its notification
caught on its way to the phone."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import quote

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.blueprint.models import DomainBlueprints
from homeassistant.components.device_automation import action as device_action
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er, template
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
import yaml

from custom_components.playguard.const import DOMAIN

from .conftest import BASE, CONSOLE_ID, fixture, publish

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINTS = ROOT / "blueprints"
FILES = sorted((BLUEPRINTS / "automation" / "playguard").glob("*.yaml"))
READMES = [(ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "README.fr.md")]


@pytest.fixture(autouse=True)
def blueprint_folder():
    """The automations' blueprints are the repository's."""
    folder = property(lambda self: BLUEPRINTS / self.domain)
    with patch.object(DomainBlueprints, "blueprint_folder", folder):
        yield


@pytest.fixture(autouse=True)
async def automations_off(hass: HomeAssistant):
    """The automations turned off at the end: their time triggers' timers go."""
    yield
    if hass.services.has_service("automation", "turn_off"):
        await hass.services.async_call("automation", "turn_off", {"entity_id": "all"}, blocking=True)


@pytest.fixture
def phone(hass: HomeAssistant) -> str:
    """A phone with the Home Assistant app: its device's id."""
    entry = MockConfigEntry(domain="mobile_app", data={"webhook_id": "phone"})
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("mobile_app", "phone")}
    )
    return device.id


@pytest.fixture
def notified():
    """What the phone is sent: each notification's title, message and data.
    The Home Assistant app's own action (mobile_app's) needs more than the
    tests install: its check, and its sending, are done here."""
    sent: list[dict[str, Any]] = []

    async def _validate(hass: HomeAssistant, config: dict) -> dict:
        assert config["domain"] == "mobile_app" and config["type"] == "notify"
        assert set(config) <= {"device_id", "domain", "type", "message", "title", "data"}
        assert dr.async_get(hass).async_get(config["device_id"])
        templates = {"message": cv.template, "title": cv.template, "data": cv.template_complex}
        return {key: templates[key](value) if key in templates else value for key, value in config.items()}

    async def _send(hass: HomeAssistant, config: dict, variables: dict, context) -> None:
        sent.append({key: template.render_complex(config.get(key), variables) for key in ("title", "message", "data")})

    with (
        patch.object(device_action, "async_validate_action_config", _validate),
        patch.object(device_action, "async_call_action_from_config", _send),
    ):
        yield sent


def _id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{CONSOLE_ID}_{key}")
    assert entity_id, key
    return entity_id


def _orders(mqtt_mock, order: str) -> list[str]:
    return [c.args[1] for c in mqtt_mock.async_publish.call_args_list if c.args[0] == f"{BASE}/{order}/set"]


async def _automation(hass: HomeAssistant, blueprint: str, inputs: dict[str, Any], alias: str = "test") -> None:
    config = {"alias": alias, "use_blueprint": {"path": f"playguard/{blueprint}", "input": inputs}}
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    assert hass.states.get(f"automation.{alias}").state == STATE_ON


async def _soon(done) -> None:
    """Lets the loop run until `done()`: an automation waiting on a trigger
    keeps hass.async_block_till_done() waiting with it."""
    for _ in range(200):
        if done():
            return
        await asyncio.sleep(0)
    raise AssertionError("not done")


def _local(freezer: FrozenDateTimeFactory, hass: HomeAssistant, when: str) -> datetime:
    """Moves to `when` (a local time on Sunday 25 October 2026), and says so."""
    moment = datetime.fromisoformat(f"2026-10-25T{when}").replace(tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(moment)
    async_fire_time_changed(hass, moment)
    return moment


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_blueprint_file(path: Path) -> None:
    """Its source is its own file on main, and both READMEs link to it."""
    data = load_yaml_dict(path)
    url = f"https://github.com/JigSawFr/playguard-ha/blob/main/blueprints/automation/playguard/{path.name}"
    assert data["blueprint"]["source_url"] == url
    assert data["blueprint"]["domain"] == "automation"
    for readme in READMES:
        assert f"/redirect/blueprint_import/?blueprint_url={quote(url, safe='')})" in readme


@pytest.mark.parametrize("readme", READMES, ids=("en", "fr"))
async def test_dashboard_example(hass: HomeAssistant, setup, readme: str) -> None:
    """The README's dashboard: its entities are the console's, its list renders."""
    block = readme[readme.index("type: vertical-stack") :]
    block = block[: block.index("```")].replace("living_room", "salon").replace("a1b2c3d4", CONSOLE_ID)
    dashboard = yaml.safe_load(block)
    publish(hass, "games", fixture("games.json"))
    await hass.async_block_till_done()

    def walk(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [v for k, v in node.items() if k == "entity_id" or k == "entity"] + [
                i for v in node.values() for i in walk(v)
            ]
        return [i for v in node for i in walk(v)] if isinstance(node, list) else []

    ids = walk(dashboard)
    assert len(ids) == 7
    for entity_id in ids:
        assert hass.states.get(entity_id), entity_id
    [graph] = [c for c in dashboard["cards"] if c["type"] == "statistics-graph"]
    assert graph["entities"] == [f"playguard:{CONSOLE_ID}_play_time"]
    [markdown] = [c for c in dashboard["cards"] if c["type"] == "markdown"]
    text = template.Template(markdown["content"], hass).async_render(parse_result=False)
    assert text.split("\n") == [
        "- **Super Mario Odyssey** 20 h 34",
        "- **Mario Kart 8 Deluxe** 16 h 20",
        "- **Xenoblade Chronicles 2** 3 h 06",
    ]


async def test_time_is_up(hass: HomeAssistant, setup, mqtt_mock, state, phone, notified) -> None:
    await _automation(
        hass, "time_is_up.yaml", {"time_is_up": _id(hass, "binary_sensor", "limit_reached"), "phone": phone}
    )
    state["timer"]["limit_reached"] = True
    publish(hass, "state", state)
    await _soon(lambda: notified)

    # The phone is told, with a button for 15 minutes more.
    assert len(notified) == 1
    sent = notified[0]
    assert sent["title"] == "Salon"
    assert sent["message"] == "Time is up: today's limit is reached."
    assert sent["data"]["tag"].startswith("playguard_time_is_up_")
    [button] = sent["data"]["actions"]
    assert button["title"] == "+15 min" and button["action"].startswith("PLAYGUARD_MORE_")
    assert _orders(mqtt_mock, "add_bonus_time") == []

    # Another notification's button does nothing; this one's gives the time.
    hass.bus.async_fire("mobile_app_notification_action", {"action": "PLAYGUARD_MORE_other"})
    for _ in range(20):
        await asyncio.sleep(0)
    assert _orders(mqtt_mock, "add_bonus_time") == []
    hass.bus.async_fire("mobile_app_notification_action", {"action": button["action"]})
    await hass.async_block_till_done()
    assert _orders(mqtt_mock, "add_bonus_time") == ["15"]


async def test_extra_time(hass: HomeAssistant, setup, mqtt_mock) -> None:
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"chores": {}, "homework": {}}})
    console = er.async_get(hass).async_get(_id(hass, "binary_sensor", "limit_reached")).device_id
    chores = {"trigger": "state", "entity_id": "input_boolean.chores", "to": "on"}
    homework = {"trigger": "state", "entity_id": "input_boolean.homework", "to": "on"}
    off = {"action": "input_boolean.turn_off", "target": {"entity_id": "input_boolean.chores"}}
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "chores",
                    "use_blueprint": {
                        "path": "playguard/extra_time.yaml",
                        "input": {"console": console, "when": [chores], "then": [off]},
                    },
                },
                {
                    "alias": "homework",
                    "use_blueprint": {
                        "path": "playguard/extra_time.yaml",
                        "input": {"console": console, "when": [homework], "minutes": 15},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.chores"}, blocking=True)
    await hass.async_block_till_done()
    assert _orders(mqtt_mock, "add_bonus_time") == ["30"]
    assert hass.states.get("input_boolean.chores").state == STATE_OFF  # then: turned off again

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.homework"}, blocking=True)
    await hass.async_block_till_done()
    assert _orders(mqtt_mock, "add_bonus_time") == ["30", "15"]
    assert hass.states.get("input_boolean.homework").state == STATE_ON  # nothing after


async def test_bedtime_reminder(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, state, phone, notified
) -> None:
    # Bedtime at 21:30 (the state's), a game played.
    _local(freezer, hass, "21:00:00")
    inputs = {
        "bedtime": _id(hass, "time", "bedtime_alarm"),
        "now_playing": _id(hass, "sensor", "now_playing"),
        "phone": phone,
    }
    await _automation(hass, "bedtime_reminder.yaml", inputs)
    _local(freezer, hass, "21:14:00")
    await hass.async_block_till_done()
    assert notified == []
    _local(freezer, hass, "21:15:00")
    await hass.async_block_till_done()
    assert notified == [
        {"title": "Salon", "message": "Bedtime in 15 minutes: Super Mario Odyssey is still on.", "data": None}
    ]

    # Once a day.
    _local(freezer, hass, "21:20:00")
    await hass.async_block_till_done()
    assert len(notified) == 1


async def test_bedtime_reminder_nobody_playing(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, state, phone, notified
) -> None:
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    _local(freezer, hass, "21:00:00")
    bedtime, now_playing = _id(hass, "time", "bedtime_alarm"), _id(hass, "sensor", "now_playing")
    await _automation(hass, "bedtime_reminder.yaml", {"bedtime": bedtime, "now_playing": now_playing, "phone": phone})
    _local(freezer, hass, "21:15:00")
    await hass.async_block_till_done()
    assert notified == []


async def test_bedtime_reminder_every_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, state, phone, notified
) -> None:
    state["activity_today"]["now_playing"] = None
    publish(hass, "state", state)
    _local(freezer, hass, "20:50:00")
    inputs = {
        "bedtime": _id(hass, "time", "bedtime_alarm"),
        "now_playing": _id(hass, "sensor", "now_playing"),
        "phone": phone,
        "before": 30,
        "only_playing": False,
    }
    await _automation(hass, "bedtime_reminder.yaml", inputs)
    await hass.async_block_till_done()
    assert notified == []
    _local(freezer, hass, "21:00:00")
    await hass.async_block_till_done()
    assert [n["message"] for n in notified] == ["Bedtime in 30 minutes."]


async def test_weekly_summary(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, phone, notified) -> None:
    week = {
        "schema": 1,
        "ts": 1,
        "days": ["2026-10-19", "2026-10-20"],
        "games": [{"app_id": "0100000000010000", "min": [30, 60]}, {"app_id": "01000A10041EA000", "min": [0, 15]}],
    }
    publish(hass, "week", week)
    _local(freezer, hass, "18:00:00")
    await _automation(hass, "weekly_summary.yaml", {"week": _id(hass, "sensor", "week_play_time"), "phone": phone})
    _local(freezer, hass, "19:00:00")  # a Sunday, the default
    await hass.async_block_till_done()
    assert notified == [
        {
            "title": "Salon",
            "message": "Play this week: 1 h 45. Most played: Super Mario Odyssey 1 h 30, Mario Kart 8 Deluxe 15 min.",
            "data": None,
        }
    ]


async def test_weekly_summary_other_days(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup, phone, notified
) -> None:
    _local(freezer, hass, "08:00:00")
    inputs = {"week": _id(hass, "sensor", "week_play_time"), "phone": phone, "days": ["sat"], "at": "09:00:00"}
    await _automation(hass, "weekly_summary.yaml", inputs)
    _local(freezer, hass, "09:00:00")
    await hass.async_block_till_done()
    assert notified == []  # Sunday
