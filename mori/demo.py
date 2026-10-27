"""The demo Dakku: made-up study sessions, for showing people what a full pond looks like.

python3 -m mori --demo (scripts/demo.sh runs it) keeps its own data in demo/, apart from yours,
and lets in anyone who can reach it without signing in. Each day's sessions are made from that
day's date, so they come out the same every time, and fill() adds the ones that have finished
by now: the demo pond grows through the day and from one day to the next, like a real one.

Two made-up friends, Mina and Kai, are in a study group with you: they have ponds of their
own, often join your sessions (so the group pond and leaderboard fill up), and one of them is
nearly always studying right now, so whoever's trying the demo can join in.
"""
import random
from datetime import datetime, timedelta

from . import logic

DAYS = 150           # how far back the made-up history goes
STEADY = 40          # no missed weekdays in the last this-many days, so the streak looks good
TAGS = ["CCNA"] * 5 + ["Japanese"] * 4 + ["Subnetting"] * 2 + ["Reading"]
LENGTHS = [25, 25, 25, 30, 45, 45, 50, 60, 15, 90]
SOURCES = ["mori", "mori", "mori", "genkan", "genkan", "manual"]
# (id, name, colour, mark, what they study, their favourite duck)
FRIENDS = (("demo-mina", "Mina", "#D9568F", "M", ["Japanese", "Japanese", "Design", "Reading"], "kirby"),
           ("demo-kai", "Kai", "#E9A100", "K", ["Calculus", "Coding", "Coding", "Physics"], "sonic"))
GROUP = "demo-club"
DECKS = {"Japanese::Core 2k": (20, 9, 64), "Japanese::Kanji": (10, 4, 38), "CCNA::Ports & protocols": (5, 2, 21),
         "CCNA::Subnetting": (0, 3, 17)}


def plan(day, steady):
    """The sessions made up for one day: (hour, minute, minutes, tag, duck, cold, source, pomodoro rounds)."""
    rnd = random.Random(f"mori-demo-{day.isoformat()}")
    weekend = day.weekday() >= 5
    skip = rnd.random() < (0.45 if weekend else 0.05)
    if skip and (weekend or not steady):
        return []
    count = rnd.choice([1, 1, 2] if weekend else [2, 2, 3, 3, 4])
    hours = sorted(rnd.sample([10, 11, 14, 15, 16, 20] if weekend else [7, 9, 12, 13, 17, 19, 20, 21, 22], count))
    out = [[hour, rnd.choice([0, 5, 10, 15, 20, 30, 40]), rnd.choice(LENGTHS), rnd.choice(TAGS),
            rnd.choice(logic.species()), rnd.random() < 0.05, rnd.choice(SOURCES), 0] for hour in hours]
    for o in out:  # some are pomodoros: rounds of 25 minutes (the breaks don't count)
        if not o[5] and o[6] == "mori" and rnd.random() < 0.2:
            o[7] = rnd.choice([2, 3, 4, 4])
            o[2] = 25 * o[7]
    if steady and not weekend and sum(o[2] for o in out if not o[5]) < 45:
        out[0][2], out[0][5] = 45, False  # a recent weekday always reaches the goal, so the streak holds
    return [tuple(o) for o in out]


def session(sid, start, minutes, tag, duck, cold, source, rounds=0):
    return {"id": sid, "start": start, "minutes": minutes, "tag": tag, "species": duck, "status": "withered" if cold else "done",
            "source": source, "manual": source == "manual", "note": "", "updated": start + minutes * 60_000, "rounds": rounds}


def friends(app, now):
    """Mina and Kai, and the study group you're all in (made once)."""
    if app.store.person(FRIENDS[0][0]):
        return
    if app.store.person("me")["name"] == "Me":
        app.put_settings({"name": "You"})
    for pid, name, color, mark, tags, duck in FRIENDS:
        app.store.save_person({"id": pid, "name": name, "color": color, "mark": mark, "created": now, "updated": now})
        app.put_settings({"name": name, "tags": [{"name": t} for t in dict.fromkeys(tags)], "tag": tags[0],
                          "species": duck, "randomSpecies": False}, pid)
    app.store.save_group({"id": GROUP, "name": "Study club", "theme": "", "created": now})
    for pid in ("me", *(f[0] for f in FRIENDS)):
        app.store.add_member(GROUP, pid, now)


def joined(day, host_plan, friend):
    """When a friend joins one of your sessions that day: (index of yours, minutes in, minutes stayed), or None."""
    pid = friend[0]
    rnd = random.Random(f"mori-demo-{pid}-{day.isoformat()}")
    done = [i for i, p in enumerate(host_plan) if not p[5] and p[2] >= 25]
    if not done or rnd.random() > (0.45 if pid == "demo-mina" else 0.25):
        return None
    i = rnd.choice(done)
    late = rnd.choice([0, 0, 5, 10, 15])
    stayed = host_plan[i][2] - late if rnd.random() > 0.3 else max(10, (host_plan[i][2] - late) // 2)  # sometimes they leave early
    return i, late, stayed


def fill(app, now):
    """Adds the made-up sessions that have finished by `now` and aren't in the demo yet."""
    tz = logic.zone(app.settings()["timeZone"])
    local = datetime.fromtimestamp(now / 1000, tz)
    today, ops = local.date(), []
    friends(app, now)
    for back in range(DAYS, -1, -1):
        day = today - timedelta(days=back)
        mine = plan(day, back <= STEADY)
        at = lambda hour, minute: int(datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).timestamp() * 1000)  # noqa: E731
        for i, (hour, minute, minutes, tag, duck, cold, source, rounds) in enumerate(mine):
            start = at(hour, minute)
            sid = f"demo-{day.isoformat()}-{i}"
            if start + minutes * 60_000 <= now and app.store.get_session(sid) is None:
                ops.append({"op": "upsert", "session": session(sid, start, minutes, tag, duck, cold, source, rounds)})
        for friend in FRIENDS:
            pid, tags, duck = friend[0], friend[4], friend[5]
            rnd = random.Random(f"mori-demo-{pid}-solo-{day.isoformat()}")
            # their own sessions, from their own week
            for j, (hour, minute, minutes, _, kind, cold, _, rounds) in enumerate(plan(day + timedelta(days=3 + len(pid)), True)[:2]):
                start = at(min(22, hour + 1), minute)
                sid = f"{pid}-{day.isoformat()}-{j}"
                if start + minutes * 60_000 <= now and app.store.get_session(sid) is None:
                    kind = duck if rnd.random() < 0.4 else kind
                    ops.append({"op": "upsert", "session": dict(session(sid, start, minutes, rnd.choice(tags), kind, cold, "mori", rounds), person=pid)})
            # and the sessions of yours they joined
            together = joined(day, mine, friend)
            if together:
                i, late, stayed = together
                hour, minute = mine[i][:2]
                start = at(hour, minute) + late * 60_000
                sid = f"{pid}-{day.isoformat()}-with"
                if start + stayed * 60_000 <= now and app.store.get_session(sid) is None:
                    kind = duck if rnd.random() < 0.5 else rnd.choice(logic.species())
                    ops.append({"op": "upsert", "session": dict(session(sid, start, stayed, rnd.choice(tags), kind, False, "mori"),
                                                                person=pid, room=f"demo-{day.isoformat()}-{i}")})
    # so today's pond isn't empty first thing: one from earlier this morning, if nothing's finished yet
    early = f"demo-{today.isoformat()}-early"
    finished_today = any(op["session"]["id"].startswith(f"demo-{today.isoformat()}") for op in ops) or any(
        app.store.get_session(f"demo-{today.isoformat()}-{i}") for i in range(4))
    if local.hour >= 6 and not finished_today and app.store.get_session(early) is None:
        ops.append({"op": "upsert", "session": session(early, now - 40 * 60_000, 25, "Japanese", "shiro", False, "mori")})
    added = len(ops)
    if ops:
        app.store.apply(ops)
        for pid in {op["session"].get("person", "me") for op in ops}:
            app._note_tags([op["session"]["tag"] for op in ops if op["session"].get("person", "me") == pid], pid)
        app._changed()
    studying(app, now, local)
    return added


def studying(app, now, local):
    """Someone's nearly always in the middle of a session, so you can join them: Mina by day, Kai
    in the evening. (When theirs hatches, the next one starts a while later.)"""
    pid, name, _, _, tags, duck = FRIENDS[0] if 7 <= local.hour < 19 else FRIENDS[1]
    timers = app.store.timers()
    if any(t for p, t in timers.items() if p in (FRIENDS[0][0], FRIENDS[1][0])) or local.hour < 7:
        return
    rnd = random.Random(f"mori-demo-live-{now // 3_600_000}")
    pomo = rnd.random() < 0.4  # sometimes a pomodoro, so you can try joining one of those too
    planned = 4 * 25 + 3 * 5 if pomo else rnd.choice([45, 50, 60, 90])
    begun = now - rnd.randint(6, planned // 2) * 60_000
    timer = {"id": f"{pid}-live-{now // 60_000}", "mode": "pomo" if pomo else "timer", "planned": planned * 60_000,
             "startedAt": begun, "acc": 0, "runFrom": begun, "tag": rnd.choice(tags), "species": duck, "deep": False,
             "source": "mori", "device": "iPhone", "updated": now, "open": True, "announced": True}
    if pomo:
        timer["pomo"] = {"focus": 25 * 60_000, "brk": 5 * 60_000, "rounds": 4}
    app.store.set(app._key("timer", pid), timer)
    app._changed()


def anki(now, tz):
    """Made-up Anki numbers: a few decks with cards due, and reviews on most days."""
    today = datetime.fromtimestamp(now / 1000, tz).date()
    by_day = []
    for back in range(DAYS, -1, -1):
        day = today - timedelta(days=back)
        rnd = random.Random(f"mori-demo-anki-{day.isoformat()}")
        if back <= STEADY or rnd.random() > 0.08:
            by_day.append([day.isoformat(), rnd.randint(35, 190) if back else rnd.randint(40, 90)])
    return {"decks": sorted(DECKS), "counts": {k: list(v) for k, v in DECKS.items()}, "byDay": by_day, "at": now - 4 * 60_000}
