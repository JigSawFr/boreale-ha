"""Play time, from the console's documents: today's play log, the finished
days and the week table. Shared by the sensors, the actions and the intents."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .coordinator import PlayGuardConsole


def games(console: PlayGuardConsole, per_app: list[Any] | None) -> dict[str, int]:
    """{game: minutes}, the most played first."""
    out: dict[str, int] = {}
    for app in sorted(per_app or [], key=lambda a: -(a.get("s") or 0) if isinstance(a, dict) else 0):
        if isinstance(app, dict) and isinstance(app.get("app_id"), str):
            out[console.game_name(app["app_id"]) or app["app_id"]] = app.get("min") or 0
    return out


def as_minutes(value: Any) -> int | None:
    """A count of minutes: an int, not a bool."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_date(value: Any) -> date | None:
    """A "YYYY-MM-DD" date, else None."""
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def accounts(console: PlayGuardConsole, rows: Any) -> dict[str, int] | None:
    """{account: minutes}, the most played first; None when the console did
    not say (the app reads the accounts only when asked to, an older agent never)."""
    if not isinstance(rows, list):
        return None
    out: dict[str, int] = {}
    for row in rows:
        uid = row.get("uid") if isinstance(row, dict) else None
        if not isinstance(uid, str):
            continue
        minutes = row.get("min")
        if isinstance(minutes, list):  # the week: a day each
            minutes = sum(m for m in minutes if isinstance(m, int) and not isinstance(m, bool))
        if isinstance(minutes, int) and not isinstance(minutes, bool):
            name = console.account_name(uid) or uid
            out[name] = out.get(name, 0) + minutes
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def window(console: PlayGuardConsole) -> list[str]:
    """The week's seven days: the week table's, or the seven up to today's
    play log when it is later."""
    days = [d for d in (console.week or {}).get("days") or [] if isinstance(d, str)]
    today = parse_date((console.activity or {}).get("local_date"))
    if today is not None and (not days or today.isoformat() > days[-1]):
        return [(today - timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    return days


def table(console: PlayGuardConsole, rows_key: str, id_key: str, log_key: str) -> dict[str, list[int]] | None:
    """Minutes per day of the week, by game (`app_id`) or by account (`uid`,
    upper case): the week table's rows, then the finished days' and today's
    play log, each day the larger count. None when none of them says (the
    accounts, from a PlayGuard whose agent does not read them)."""
    days = window(console)
    at = {day: i for i, day in enumerate(days)}
    out: dict[str, list[int]] = {}
    known = False

    def count(key: Any, day: Any, minutes: Any) -> None:
        if isinstance(key, str) and key and day in at and as_minutes(minutes) is not None:
            row = out.setdefault(key.upper() if id_key == "uid" else key, [0] * len(days))
            row[at[day]] = max(row[at[day]], minutes)

    week = console.week or {}
    if isinstance(week.get(rows_key), list):
        known = True
        for row in week[rows_key]:
            if isinstance(row, dict):
                for day, minutes in zip(week.get("days") or [], row.get("min") or [], strict=False):
                    count(row.get(id_key), day, minutes)
    activity = console.activity or {}
    logs = [*((doc.get("local_date") or day, doc) for day, doc in console.finals.items())]
    logs.append((activity.get("local_date"), activity))
    for day, doc in logs:
        if day in at and isinstance(doc.get(log_key), list):
            known = True
            for item in doc[log_key]:
                if isinstance(item, dict):
                    count(item.get(id_key), day, item.get("min"))
    return out if known else None


def week_games(console: PlayGuardConsole) -> dict[str, list[int]]:
    """Each game's minutes per day of the week, by application id."""
    return table(console, "games", "app_id", "per_app") or {}


def week_days(console: PlayGuardConsole) -> dict[str, int]:
    """Each day's minutes of the week."""
    days = window(console)
    totals = [sum(day) for day in zip(*week_games(console).values(), strict=True)] or [0] * len(days)
    return dict(zip(days, totals, strict=False))


def week_accounts(console: PlayGuardConsole) -> dict[str, int] | None:
    """Each account's minutes of the week, by name; None when the console does not say."""
    rows = table(console, "accounts", "uid", "per_account")
    if rows is None:
        return None
    return accounts(console, [{"uid": uid, "min": sum(m)} for uid, m in rows.items()])


def _named(console: PlayGuardConsole, app_id: str) -> dict[str, Any]:
    return {"app_id": app_id, "name": console.game_name(app_id) or app_id}


def today(console: PlayGuardConsole) -> dict[str, Any]:
    """Today on the console, as the actions and the assistants answer it: the
    play time, each game's and each account's, the game played, the limit and
    what is left of it, bedtime, whether games are blocked."""
    state = console.state or {}
    activity = console.activity or {}
    timer = state.get("timer") or {}
    rows = [a for a in activity.get("per_app") or [] if isinstance(a, dict) and isinstance(a.get("app_id"), str)]
    rows.sort(key=lambda a: -(as_minutes(a.get("min")) or 0))
    playing = (state.get("activity_today") or {}).get("now_playing") or {}
    limit = as_minutes(timer.get("limit_today_min"))
    bedtime = timer.get("bedtime") or {}
    return {
        "date": activity.get("local_date") or state.get("local_date"),
        "minutes": as_minutes(activity.get("total_min")),
        "games": [{**_named(console, a["app_id"]), "minutes": as_minutes(a.get("min")) or 0} for a in rows],
        "accounts": accounts(console, activity.get("per_account")),
        "now_playing": _named(console, playing["app_id"]) if isinstance(playing.get("app_id"), str) else None,
        # 1440 minutes: no limit
        "limit_minutes": limit if limit is not None and limit < 1440 else None,
        "remaining_minutes": as_minutes(timer.get("remaining_min")),
        "extra_minutes": as_minutes(timer.get("extended_today_min")),
        "blocked": bool(timer.get("limit_reached")),
        "blocked_by": timer.get("blocked_by"),
        "bedtime": {"start": bedtime.get("start"), "end": bedtime.get("end")} if bedtime.get("enabled") else None,
        "parental_controls": {
            "enabled": (state.get("controls") or {}).get("enabled"),
            "unlocked": (state.get("controls") or {}).get("temp_unlocked"),
        },
    }


def week(console: PlayGuardConsole) -> dict[str, Any]:
    """The last seven days: each day's play time, each game's (with its day by
    day) and each account's."""
    days = week_days(console)
    rows = sorted(week_games(console).items(), key=lambda kv: -sum(kv[1]))
    return {
        "days": [{"date": day, "minutes": m} for day, m in days.items()],
        "minutes": sum(days.values()),
        "games": [{**_named(console, app_id), "minutes": sum(m), "per_day": m} for app_id, m in rows],
        "accounts": week_accounts(console),
    }
