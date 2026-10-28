"""Days, streaks and totals: the same rules as the Genkan homepage and the Dakku app.

A day counts once you reach the daily goal. Missing a weekday breaks the streak;
weekends never do (studying on one still adds a day). Today can't break it yet.
Every 7 days in a row earns a streak freeze (you can hold 2): a missed weekday uses one
up instead of breaking the streak, though it doesn't add a day either.
Days are counted in your home time zone, so traveling doesn't scramble them.
"""
import json
import re
from datetime import date, datetime, timedelta
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


# ── the duck shop: grain for focus, and ducks to spend it on ─────────────────
# Everyone but you earns their ducks (you can turn that off in Settings). The plain ducks come with
# hours studied; the rest are bought with grain (🌾), earned for every duck hatched with the timer.
# A minute of focus is worth more the longer the session: a warm-up pays half, and a long, unbroken
# stretch pays up to 1.75 a minute. Studying together pays a tenth more, and each day the daily goal
# is reached pays a bonus. Cold eggs, and time logged by hand or imported, pay nothing.
GRAIN_RATES = ((90, 1.75), (50, 1.5), (25, 1.25), (10, 1.0), (0, 0.5))  # (from this many minutes, grain a minute)
GRAIN_CAP = 180         # minutes a session can earn for (a 4-hour stopwatch earns like 3 hours)
GRAIN_TOGETHER = 1.1    # a session studied together
GRAIN_GOAL_DAY = 20     # each day the daily goal is reached
UNEARNED = ("manual", "import", "genkan")  # sources that don't earn (a session logged by hand is `manual` too)
# A long-term collection: at about an hour a day (some 110 grain with the goal bonus) a duck from the shop
# takes nine or ten days, so the whole shop takes about a year, and the plain ducks keep coming over months.
HOUR_DUCKS = {"shiro": 0, "sailor": 2, "neko": 5, "ninja": 10, "kitsune": 20, "yukata": 35, "samurai": 50,
              "nurse": 75, "astro": 100, "king": 150}  # the plain ducks: hours studied to unlock each (Shiro is everyone's)
PRICE = 1000            # a duck in the shop: every one the same
HOLIDAY = {"witch": "halloween", "harvest": "thanksgiving", "santa": "christmas"}  # the holiday ducks: free in their holiday, and only then
# The themes, ponds and pond decorations are in the shop too ("theme:sumi", "pond:night", "decor:koi"):
# Ai and the classic pond are everyone's, and the holidays' themes and ponds are free while they're on.
EVENTS = ("halloween", "thanksgiving", "christmas", "lunar")
EVENT_MONTHS = {"halloween": 10, "thanksgiving": 11, "christmas": 12}
LUNAR_NEW_YEAR = {2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3), 2031: (1, 23), 2032: (2, 11),
                  2033: (1, 31), 2034: (2, 19), 2035: (2, 8), 2036: (1, 28), 2037: (2, 15), 2038: (2, 4), 2039: (1, 24), 2040: (2, 12)}
FREE_ITEMS = ("theme:ai", "pond:classic", "pond:seasonal")  # (the seasonal pond follows the seasons, free)
# the season each month is in, as the seasonal pond follows them: a season's own pond is free to pick
# while it lasts, and bought to have it the rest of the year (the classic pond is summer's)
SEASON_OF = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
             6: "classic", 7: "classic", 8: "classic", 9: "autumn", 10: "autumn", 11: "autumn"}
THEME_PRICE = 1200      # Sumi, Yozakura, Sakura
POND_PRICE = 1200       # each pond (a season's is free while it lasts)
DECOR_PRICE = 500       # each thing on the pond
MYSTERY_PRICE = 700     # a mystery egg: a duck you don't have yet, picked at random (cheaper than choosing)
CUSTOM_PRICE = 4000     # asking for a new duck: you make it, they get it, and it joins the shop for everyone


def grain_for(session):
    """The grain one session earns."""
    if session.get("deleted") or session.get("status") == "withered" or session.get("manual") \
            or session.get("source") in UNEARNED:
        return 0
    minutes = min(int(session.get("minutes") or 0), GRAIN_CAP)
    rate = next(r for least, r in GRAIN_RATES if minutes >= least)
    earned = minutes * rate * (GRAIN_TOGETHER if session.get("room") else 1)
    return int(earned)


def grain_earned(sessions, goal, tz):
    """Everything a person has earned: their sessions, and a bonus for each day they reached the goal."""
    total = sum(grain_for(s) for s in sessions)
    counted = [s for s in sessions if grain_for(s)]
    days = sum(1 for m in minutes_by_day(counted, tz).values() if goal and m >= goal)
    return total + days * GRAIN_GOAL_DAY


def price(kind):
    """What a duck costs in the shop, or None for one that comes with hours."""
    return None if kind in HOUR_DUCKS or kind in HOLIDAY else PRICE


def event_on(event, day):
    """Whether a holiday is on: its month (Lunar New Year: from a week before it to the Lantern Festival)."""
    if event == "lunar":
        at = LUNAR_NEW_YEAR.get(day.year)
        return bool(at) and -7 <= (day - date(day.year, *at)).days <= 15
    return EVENT_MONTHS.get(event) == day.month


def in_season(kind, day):
    """Whether a duck can be hatched today: a holiday duck only in its holiday."""
    return kind not in HOLIDAY or event_on(HOLIDAY[kind], day)


def item_price(item):
    """What a theme, pond or decoration costs ("theme:sumi"), or None for a free one (and a holiday's)."""
    kind, _, name = item.partition(":")
    if item in FREE_ITEMS or (kind in ("theme", "pond") and name in EVENTS):
        return None
    return {"theme": THEME_PRICE, "decor": DECOR_PRICE}.get(kind) or POND_PRICE


def owned_ducks(hours, bought, day):
    """The ducks someone can hatch: the plain ones their hours have unlocked, the ones they bought, and the
    holiday's duck while it's on."""
    return tuple(k for k in species() if (k in HOUR_DUCKS and hours >= HOUR_DUCKS[k]) or k in bought
                 or (k in HOLIDAY and in_season(k, day)))


def owned_items(items, bought, day):
    """The themes, ponds and decorations someone can use: the free ones, the ones they bought, and the
    holiday's theme and pond while it's on."""
    return tuple(i for i in items if i in FREE_ITEMS or i in bought or i == f"pond:{SEASON_OF[day.month]}"
                 or (i.partition(":")[2] in EVENTS and i.partition(":")[0] in ("theme", "pond") and event_on(i.partition(":")[2], day)))
