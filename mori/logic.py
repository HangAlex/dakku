"""Days, streaks and totals: the same rules as the Genkan homepage and the Dakku app.

A day counts once you reach the daily goal. Missing a weekday breaks the streak;
weekends never do (studying on one still adds a day). Today can't break it yet.
Every 7 days in a row earns a streak freeze (you can hold 2): a missed weekday uses one
up instead of breaking the streak, though it doesn't add a day either.
Days are counted in your home time zone, so travelling doesn't scramble them.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Every finished session hatches a duck, and each kind wears its own outfit. All of them are yours
# from the start. (The field is still called "species" from when Dakku grew trees.) The first ten are
# Dakku's own; the rest are the painted ones in the duck list (art/ducks.json), which scripts/duck.py
# publishes with their pictures in web/ducks/ducks.json. That's read again whenever it changes, so a
# new duck works without a restart.
BUILT_IN = ("shiro", "sailor", "neko", "super", "ninja", "kitsune", "yukata", "samurai", "king", "astro")
NAMES = {"shiro": "little white duck", "sailor": "sailor duck", "neko": "kitty duck", "super": "super duck",
         "ninja": "ninja duck", "kitsune": "fox duck", "yukata": "festival duck", "samurai": "samurai duck",
         "king": "king duck", "astro": "astronaut duck"}
OLD_SPECIES = {"matsu": "shiro", "take": "sailor", "sakura": "neko", "momiji": "super", "icho": "ninja",
               "sugi": "kitsune", "ume": "yukata"}  # the trees from before, and the duck each became
KIND_RE = re.compile(r"^[a-z][a-z0-9]{1,23}$")
_published = {"path": None, "stamp": None, "kinds": {}}


def use_ducks(path):
    """Where the published duck list is (web/ducks/ducks.json)."""
    _published.update(path=Path(path), stamp=None, kinds={})


def _kinds():
    path = _published["path"]
    if path is None:
        return {}
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return {}
    if stamp != _published["stamp"]:
        try:
            found = json.loads(path.read_text(encoding="utf-8")).get("kinds") or {}
        except (OSError, ValueError):
            found = {}
        _published.update(stamp=stamp, kinds={k: v for k, v in found.items() if KIND_RE.match(k) and isinstance(v, dict)})
    return _published["kinds"]


def species():
    """Every kind of duck: Dakku's own ten, then the painted ones, in the duck list's order."""
    return BUILT_IN + tuple(k for k in _kinds() if k not in BUILT_IN and k not in OLD_SPECIES)


def noun(value):
    """What a notification calls a duck: "ninja duck", "Sonic duck"."""
    if value in NAMES:
        return NAMES[value]
    name = (_kinds().get(value) or {}).get("name")
    return f"{name} duck" if name else "duck"


def kind(value):
    """A duck kind from anything a device might send, including the old tree names."""
    return value if value in species() else OLD_SPECIES.get(value, "")


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo("UTC")


def day_of(ms, tz):
    return datetime.fromtimestamp(ms / 1000, tz).date()


def minutes_by_day(sessions, tz):
    totals = {}
    for s in sessions:
        if s.get("deleted") or s.get("status") == "withered":
            continue
        day = day_of(s["start"], tz)
        totals[day] = totals.get(day, 0) + s["minutes"]
    return totals


FREEZE_EVERY = 7  # days in a row that earn a streak freeze
FREEZE_MAX = 2    # freezes held at once


def run(by_day, goal, today):
    """The streak under the weekday rule, with freezes: the current and best streak, the freezes
    held now, and the weekdays a freeze covered."""
    out = {"current": 0, "best": 0, "freezes": 0, "frozen": []}
    if not by_day:
        return out
    first = min(min(by_day), today)
    streak = freezes = 0
    d = first
    while d <= today:
        if by_day.get(d, 0) >= goal:
            streak += 1
            out["best"] = max(out["best"], streak)
            if streak % FREEZE_EVERY == 0:
                freezes = min(FREEZE_MAX, freezes + 1)
        elif d != today and d.weekday() < 5:
            if freezes:
                freezes -= 1
                out["frozen"].append(d)
            else:
                streak = 0
        d += timedelta(days=1)
    out.update(current=streak, freezes=freezes)
    return out


def streaks(by_day, goal, today):
    """(current, best)."""
    r = run(by_day, goal, today)
    return r["current"], r["best"]


def summary(sessions, goal, tz, now_ms):
    by_day = minutes_by_day(sessions, tz)
    today = day_of(now_ms, tz)
    r = run(by_day, goal, today)
    monday = today - timedelta(days=today.weekday())
    week = sum(m for d, m in by_day.items() if monday <= d <= today)
    return {"today": by_day.get(today, 0), "goal": goal, "streak": r["current"], "best": r["best"], "freezes": r["freezes"],
            "week": week, "weekday": today.weekday() < 5, "date": today.isoformat()}


def week(sessions, tz, now_ms):
    """This week so far, from Monday: minutes studied, ducks hatched, and the best day."""
    today = day_of(now_ms, tz)
    monday = today - timedelta(days=today.weekday())
    by_day, ducks = {}, 0
    for s in sessions:
        if s.get("deleted") or s.get("status") == "withered":
            continue
        d = day_of(s["start"], tz)
        if monday <= d <= today:
            by_day[d] = by_day.get(d, 0) + s["minutes"]
            ducks += 1
    best = max(by_day, key=lambda d: (by_day[d], d)) if by_day else None
    return {"minutes": sum(by_day.values()), "ducks": ducks, "days": len(by_day), "best": best,
            "bestMinutes": by_day.get(best, 0)}


def fmt_minutes(m):
    return f"{m} min" if m < 60 else f"{m // 60}h" + (f" {m % 60}m" if m % 60 else "")
