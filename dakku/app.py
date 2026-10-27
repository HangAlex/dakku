"""Dakku's server logic: sign-in, sessions, the shared timer, sync, notifications and backups,
and studying together with friends.

web.py turns HTTP requests into calls on App; everything that matters happens here.

The timer lives on the server, so an egg started on your phone keeps warming on the
homepage and vice versa, and its duck is logged when it hatches even if every screen is off.

Friends you invite get their own pond on your Dakku (person "me" is you). Anyone in a group with
you can join a session you're in the middle of: each of you hatches your own duck, for the time
you each studied, when the session ends. There's no lobby: a session is joinable as it runs.
"""
import csv
import hashlib
import hmac
import io
import json
import math
import os
import queue
import re
import secrets
import socket
import subprocess
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__, anki, demo as demo_data, ec, logic, webpush, words
from .store import Store, database

MINUTE = 60_000
MAX_STOPWATCH = 240 * MINUTE
ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# 朱 vermilion, 若竹 bamboo, 山吹 gold, 牡丹 peony, 瑠璃 lapis, 常磐 evergreen, 菫 violet, 紅 crimson:
# traditional colors in an order that stays distinguishable for color-blind eyes (checked with a validator)
TAG_COLORS = ("#D9482B", "#12A37A", "#E9A100", "#D9568F", "#2B6CC4", "#2E8B3A", "#6C55C8", "#C9283E")
THEMES = ("ai", "sumi", "yozakura", "sakura", "halloween", "thanksgiving", "christmas")  # dark, and Sakura, the one light one
EXTENSION_ORIGINS = ("chrome-extension://laplipljbbgpfinlebaaphokcbijpgoo",)  # the Genkan homepage
KEEP_BACKUPS = 30
PAIR_MINUTES = 10
PAIR_RE = re.compile(r"^\d{3}[\s-]?\d{3}$")
INVITE_DAYS = 7
FRIENDS_HTTPS = 8443  # the port Tailscale Funnel opens the friends' door on (see scripts/enable-friends.sh)
EVENTS = ("halloween", "thanksgiving", "christmas")  # each a theme and a pond, to pick any time
POND_THEMES = ("classic", "spring", "autumn", "winter", "night", "garden", "sakura") + EVENTS + ("seasonal",)
DECOR = ("torii", "lantern", "koi", "lanterns", "lotus")  # things to put on the pond, as many as you like
POMO_LIMITS = {"focus": (5, 120), "brk": (1, 60), "rounds": (1, 12)}  # minutes, minutes, rounds
UNDO_MS = 10_000  # a session can be called off this soon after it starts, as if it never began
CHEER_LEN = 140  # a cheer: a short message for someone studying, shown on their screen and phone
CHEER_GAP = 15_000  # between two cheers to the same person
CHEER_HOURLY = 40  # cheers anyone can send in an hour
RECAP_AT = 19 * 60  # Sunday evening, local time: the week's recap
LIVE_PER_PERSON = 8  # live-update connections each person may have open at once (each holds one of a door's MAX_CONNECTIONS)
HOST_CLOCK = ("id", "mode", "planned", "pomo", "acc", "runFrom", "startedAt", "elapsed", "running", "now", "remaining",
              "endsAt", "round", "phase", "phaseLeft", "focused")  # what a guest is shown of the host's timer
PAIRS_EACH = 3  # pairing codes each person can have waiting at once
PUSH_PER_PERSON = 10  # devices with notifications on, per person (each device has one)
ORIGIN_RE = re.compile(r"^https://[A-Za-z0-9.-]{1,200}(:\d{1,5})?$")  # where Dakku was opened, for notifications


def now_ms():
    return int(time.time() * 1000)


def new_id():
    return secrets.token_urlsafe(9)


def pomo_focus(t, elapsed):
    """How much of a pomodoro's time on the clock (ms) went to focusing, not to breaks."""
    p = t["pomo"]
    whole, rest = divmod(max(0, elapsed), p["focus"] + p["brk"])
    return min(p["rounds"] * p["focus"], whole * p["focus"] + min(rest, p["focus"]))


def pomo_phase(t, elapsed):
    """Where a pomodoro is: its round (from 1), "focus" or "break", and what's left of that part (ms)."""
    p = t["pomo"]
    cycle = p["focus"] + p["brk"]
    rnd, rest = divmod(max(0, min(elapsed, t["planned"])), cycle)
    if rnd >= p["rounds"]:
        return p["rounds"], "focus", 0
    if rest < p["focus"]:
        return rnd + 1, "focus", p["focus"] - rest
    return rnd + 1, "break", cycle - rest


def pomo_rounds(t, elapsed):
    """How many of a pomodoro's focus rounds are done."""
    p = t["pomo"]
    if elapsed < p["focus"]:
        return 0
    return min(p["rounds"], (elapsed - p["focus"]) // (p["focus"] + p["brk"]) + 1)


def log(*parts):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *parts, flush=True)


class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def system_time_zone():
    try:
        target = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return "UTC"


def default_settings(tz, friend=False):
    tags = ["Study", "Reading"] if friend else ["CCNA", "Japanese", "Reading"]
    return {
        "name": "", "goal": 30, "timeZone": tz, "dayMode": "home",
        "presets": [15, 25, 45, 60], "minutes": 25, "mode": "timer",
        "tags": [{"name": t, "color": TAG_COLORS[i]} for i, t in enumerate(tags)],
        "tag": tags[0], "species": "shiro", "randomSpecies": True,
        "deepFocus": False, "keepAwake": True, "sound": True, "theme": "ai",
        "reminder": {"enabled": False, "time": "20:00", "weekdaysOnly": True},
        "openSessions": True, "friendAlerts": True, "cheerAlerts": True, "weeklyRecap": True, "pondTheme": "classic", "decor": [],
        "pomo": {"focus": 25, "brk": 5, "rounds": 4},
    }


def initial(name):
    """The mark on someone's ducks until they pick one: the first letter of their name."""
    name = str(name or "").strip()
    return name[:1].upper() if name else "?"


def clean_mark(raw, name):
    mark = re.sub(r"\s+", "", str(raw or ""))[:4]  # a letter or two, or an emoji
    return mark or initial(name)


def private(folder):
    """Only you (this PC's account) can open `folder` and the files in it: Dakku's data and its backups."""
    os.chmod(folder, 0o700)
    for path in Path(folder).iterdir():
        if path.is_file() and not path.is_symlink():
            os.chmod(path, 0o600)


def clean_source(raw):
    """Where a session came from: dakku, genkan, manual, import… (an older Dakku page still says "mori",
    Dakku's name before it had one.)"""
    source = re.sub(r"[^a-z]", "", str(raw or "").lower())[:12]
    return "dakku" if source == "mori" else source


def _int(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ApiError(400, f"{name} must be a number")
    if not math.isfinite(number):  # (1e400 is a float too: infinity)
        raise ApiError(400, f"{name} must be a number")
    return int(round(number))


def _when(value, now):
    """A time a device says something changed (ms), or now if it's missing or makes no sense; never
    more than a minute ahead."""
    try:
        number = float(value or now)
    except (TypeError, ValueError, OverflowError):
        number = now
    return max(0, min(int(number) if math.isfinite(number) else now, now + MINUTE))


def clean_settings(incoming, current):
    if not isinstance(incoming, dict):
        raise ApiError(400, "settings must be an object")
    s = json.loads(json.dumps(current))
    g = incoming
    if "name" in g:
        s["name"] = str(g["name"] or "").strip()[:40]
    if "goal" in g:
        s["goal"] = max(5, min(600, _int(g["goal"], "goal")))
    if "minutes" in g:
        s["minutes"] = max(1, min(300, _int(g["minutes"], "minutes")))
    if "timeZone" in g and logic.zone(str(g["timeZone"])).key == str(g["timeZone"]):
        s["timeZone"] = str(g["timeZone"])
    if "dayMode" in g:
        s["dayMode"] = "device" if g["dayMode"] == "device" else "home"
    if "mode" in g:
        s["mode"] = g["mode"] if g["mode"] in ("stopwatch", "pomo") else "timer"
    if isinstance(g.get("pomo"), dict):
        s["pomo"] = clean_pomo(g["pomo"], s.get("pomo"))
    if "presets" in g and isinstance(g["presets"], list):
        presets = sorted({max(1, min(300, _int(p, "preset"))) for p in g["presets"][:8]})
        s["presets"] = presets[:6] or [25]
    if "tags" in g and isinstance(g["tags"], list):
        tags, seen = [], set()
        for i, tag in enumerate(g["tags"][:24]):
            if not isinstance(tag, dict):
                continue
            name = str(tag.get("name") or "").strip()[:24]
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            color = str(tag.get("color") or "")
            tags.append({"name": name, "color": color if COLOR_RE.match(color) else TAG_COLORS[i % len(TAG_COLORS)]})
        s["tags"] = tags
    if "tag" in g:
        s["tag"] = str(g["tag"] or "").strip()[:24]
    if logic.kind(g.get("species")):
        s["species"] = logic.kind(g["species"])
    for key in ("randomSpecies", "deepFocus", "keepAwake", "sound"):
        if key in g:
            s[key] = bool(g[key])
    if g.get("theme") in THEMES:
        s["theme"] = g["theme"]
    for key in ("openSessions", "friendAlerts", "cheerAlerts", "weeklyRecap"):
        if key in g:
            s[key] = bool(g[key])
    if g.get("pondTheme") in POND_THEMES:
        s["pondTheme"] = g["pondTheme"]
    if isinstance(g.get("decor"), list):
        s["decor"] = [d for d in DECOR if d in g["decor"]]
    if isinstance(g.get("reminder"), dict):
        r = dict(s.get("reminder") or {})
        if "enabled" in g["reminder"]:
            r["enabled"] = bool(g["reminder"]["enabled"])
        if TIME_RE.match(str(g["reminder"].get("time", ""))):
            r["time"] = g["reminder"]["time"]
        if "weekdaysOnly" in g["reminder"]:
            r["weekdaysOnly"] = bool(g["reminder"]["weekdaysOnly"])
        s["reminder"] = r
    return s


def clean_pomo(raw, current=None):
    """A pomodoro's shape, in minutes: how long to focus, how long each break, and how many rounds."""
    out = dict(current or {"focus": 25, "brk": 5, "rounds": 4})
    for key, (low, high) in POMO_LIMITS.items():
        if isinstance(raw, dict) and raw.get(key) is not None:
            out[key] = max(low, min(high, _int(raw[key], key)))
    return out


def clean_session(raw, now):
    if not isinstance(raw, dict):
        raise ApiError(400, "a session must be an object")
    sid = str(raw.get("id", ""))
    if not ID_RE.match(sid):
        raise ApiError(400, "session ids are 4–64 letters, digits, - or _")
    out = {"id": sid}
    if "start" in raw:
        start = _int(raw["start"], "start")
        if not 946_684_800_000 <= start <= now + 86_400_000:
            raise ApiError(400, "that start time is out of range")
        out["start"] = start
    if "minutes" in raw:
        minutes = _int(raw["minutes"], "minutes")
        if not 0 <= minutes <= 1440:
            raise ApiError(400, "minutes must be between 0 and 1440")
        out["minutes"] = minutes
    if "tag" in raw:
        out["tag"] = str(raw["tag"] or "").strip()[:40]
    if "note" in raw:
        out["note"] = str(raw["note"] or "").strip()[:300]
    if "source" in raw:
        out["source"] = clean_source(raw["source"])
    if "species" in raw:
        out["species"] = logic.kind(raw["species"])
    if "status" in raw:
        out["status"] = "withered" if raw["status"] == "withered" else "done"
    if "manual" in raw:
        out["manual"] = 1 if raw["manual"] else 0
    if "rounds" in raw:
        out["rounds"] = max(0, min(50, _int(raw["rounds"] or 0, "rounds")))
    out["updated"] = _when(raw.get("updated"), now)
    return out


def public(row):
    return {"id": row["id"], "start": row["start"], "minutes": row["minutes"], "tag": row["tag"],
            "species": row["species"], "status": row["status"], "source": row["source"],
            "manual": bool(row["manual"]), "note": row["note"], "updated": row["updated"],
            "deleted": bool(row["deleted"]), "room": row.get("room", ""), "rounds": row.get("rounds") or 0}


def span(session):
    """When a session ran, as far as its record says: from its start, for its minutes."""
    return session["start"], session["start"] + session["minutes"] * MINUTE


def union(spans):
    """How long (ms) a set of time spans covers, overlaps counted once."""
    total, end = 0, None
    for a, b in sorted((a, b) for a, b in spans if b > a):
        if end is None or a > end:
            total, end = total + b - a, b
        elif b > end:
            total, end = total + b - end, b
    return total


def public_person(p):
    return {"id": p["id"], "name": p["name"], "color": p["color"], "mark": p["mark"]}


def guess_device(user_agent):
    ua = user_agent or ""
    for needle, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android phone"),
                         ("Macintosh", "Mac"), ("Windows", "Windows PC"), ("Linux", "Linux PC")):
        if needle in ua:
            return name
    return "Browser"


class Ctx:
    """Who is asking: set up by web.py for every request. `public` is the friends' door."""

    def __init__(self, ip="", local=False, device=None, https=False, origin="", user_agent="", public=False):
        self.ip, self.local, self.device, self.https, self.origin, self.user_agent = ip, local, device, https, origin, user_agent
        self.public = public

    @property
    def signed_in(self):
        return self.local or self.device is not None

    @property
    def person(self):
        if self.local:
            return "me"  # this PC is always you, whatever a browser here is signed in as
        if self.device:
            return self.device.get("person") or "me"
        return None

    @property
    def owner(self):
        return self.person == "me"

    @property
    def device_id(self):
        return self.device["id"] if self.device else ("local" if self.local else "")

    @property
    def device_name(self):
        return self.device["name"] if self.device else ("This PC" if self.local else "")


class App:
    def __init__(self, data_dir, web_dir, backup_dir=None, anki_url=None, dev_origins=(), start_threads=True, demo=False, friends_url=None):
        self.demo = demo  # the demo Dakku: made-up ducks, and everyone who can reach it is let in (see demo.py)
        self.friends_url = (friends_url or "").rstrip("/") or None  # where friends reach the friends' door, if not by Funnel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        private(self.data_dir)
        self.web_dir = Path(web_dir).resolve()
        logic.use_ducks(self.web_dir / "ducks" / "ducks.json")  # the painted ducks, as published
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self.anki_url = anki_url
        self.allowed_origins = set(EXTENSION_ORIGINS) | {o for o in dev_origins if o}
        self.store = Store(database(self.data_dir))
        self.vapid = webpush.Vapid(str(self.data_dir / "vapid.json"))
        private(self.data_dir)  # (again, now the database is open: SQLite's own files take its permissions)
        self.lock = threading.RLock()
        self.port = 8640
        self.started = time.time()
        self.system_tz = system_time_zone()
        self._clients, self._clients_lock = {}, threading.Lock()  # each open page's live updates, and whose they are
        self._let_go = set()  # the ones that should end: someone opened more than LIVE_PER_PERSON
        self._failures, self._fail_lock = {}, threading.Lock()
        self._pairs, self._pair_lock = {}, threading.Lock()
        self._cheers_sent = {}  # who cheered whom when, to keep cheers from turning into spam
        self._anki_live = False
        self._addresses_cache = (0, None)
        self._touched = {}
        settings = self.store.get("settings")
        if settings is None:
            self.store.set("settings", default_settings(self.system_tz))
        else:
            fresh = dict(default_settings(self.system_tz), **settings)  # settings added since keep their defaults
            fresh["species"] = logic.kind(fresh.get("species")) or "shiro"
            fresh["theme"] = fresh["theme"] if fresh.get("theme") in THEMES else "ai"
            if fresh != settings:
                self.store.set("settings", fresh)
        if not self.store.person("me"):  # you, as your friends see you
            name = self.store.get("settings").get("name") or "Me"
            self.store.save_person({"id": "me", "name": name, "color": TAG_COLORS[4], "mark": initial(name),
                                    "created": now_ms(), "updated": now_ms()})
        self.store.rename_species(logic.OLD_SPECIES)  # sessions from the tree days hatch as ducks
        if not self.store.get("passcode"):
            self.set_passcode(words.passcode())
        if demo:
            demo_data.fill(self, now_ms())
        self._stop = threading.Event()
        if start_threads:
            threading.Thread(target=self._scheduler, name="dakku-scheduler", daemon=True).start()

    def close(self):
        self._stop.set()
        with self.store.lock:
            self.store.db.close()

    # ── sign-in ──────────────────────────────────────────────────────────────
    def set_passcode(self, code):
        code = words.normalize(code)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", code.encode(), salt, 240_000)
        self.store.set("passcode", {"salt": salt.hex(), "hash": digest.hex(), "iterations": 240_000})
        path = self.data_dir / "passcode.txt"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        return code

    def check_passcode(self, text):
        saved = self.store.get("passcode")
        digest = hashlib.pbkdf2_hmac("sha256", words.normalize(text).encode(), bytes.fromhex(saved["salt"]), saved["iterations"])
        return hmac.compare_digest(digest.hex(), saved["hash"])

    def passcode_plain(self):
        try:
            return (self.data_dir / "passcode.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _rate_check(self, ctx, guessable=True):
        """Wrong codes are limited per address, and per door (so strangers trying codes at the friends' door,
        on the internet, can't lock you out of your own). The door-wide limit is only for codes short enough
        to guess, pairing codes and passcodes: an invite's code is far too long, so strangers getting those
        wrong never hold up a friend's real invite."""
        now = time.time()
        with self._fail_lock:
            for key in list(self._failures):
                self._failures[key] = [t for t in self._failures[key] if now - t < 3600]
                if not self._failures[key]:
                    del self._failures[key]
            mine = [t for t in self._failures.get((ctx.public, ctx.ip), []) if now - t < 600]
            if len(mine) >= 5:
                raise ApiError(429, "Too many tries. Wait a few minutes, then try again.", retryAfter=int(600 - (now - mine[0])) + 1)
            if guessable and len(self._failures.get(("guesses", ctx.public), [])) >= 40:
                raise ApiError(429, "Too many sign-in attempts lately. Try again in an hour.", retryAfter=3600)

    def _rate_fail(self, ctx, guessable=True):
        with self._fail_lock:
            self._failures.setdefault((ctx.public, ctx.ip), []).append(time.time())
            if guessable:
                self._failures.setdefault(("guesses", ctx.public), []).append(time.time())

    def device_for_token(self, token):
        if not token:
            return None
        return self.store.device_by_token(hashlib.sha256(token.encode()).hexdigest())

    def touch(self, ctx):
        if not ctx.device or self.demo:
            return
        now = now_ms()
        if now - self._touched.get(ctx.device["id"], 0) > MINUTE:
            self._touched[ctx.device["id"]] = now
            self.store.touch_device(ctx.device["id"], now, ctx.ip)

    def new_pair_code(self, person="me"):
        """A one-time, 6-digit code that signs a new device in as `person`. Yours are shown on this
        PC; a friend's on a device they're already signed in on (say, Safari before the Home Screen)."""
        now = time.time()
        with self._pair_lock:
            self._pairs = {c: v for c, v in self._pairs.items() if v[0] > now}
            theirs = sorted((v[0], c) for c, v in self._pairs.items() if v[1] == person)
            for _, old in theirs[:max(0, len(theirs) - PAIRS_EACH + 1)]:
                del self._pairs[old]  # a person's newest few work; asking again and again only replaces them
            code = f"{secrets.randbelow(1_000_000):06d}"
            while code in self._pairs:
                code = f"{secrets.randbelow(1_000_000):06d}"
            self._pairs[code] = (now + PAIR_MINUTES * 60, person)
        return {"code": code, "expires": int((now + PAIR_MINUTES * 60) * 1000)}

    def _use_pair_code(self, text):
        """Who the code signs in as, or None. Each code works once."""
        code = re.sub(r"\D", "", text)
        with self._pair_lock:
            until, person = self._pairs.pop(code, (0, None))
        return person if until > time.time() else None

    def _new_device(self, ctx, person, name):
        token = secrets.token_urlsafe(32)
        device = {"id": new_id(), "name": str(name or "").strip()[:40] or guess_device(ctx.user_agent), "person": person}
        self.store.add_device(device["id"], hashlib.sha256(token.encode()).hexdigest(), device["name"], now_ms(), ctx.ip, person)
        log("signed in:", device["name"], "as", person, "from", ctx.ip)
        return token, device

    def login(self, ctx, body):
        self._rate_check(ctx)
        code = str(body.get("passcode") or "").strip()
        pair = str(body.get("pair") or "").strip() or (code if PAIR_RE.match(code) else "")
        person = None
        if pair:
            person = self._use_pair_code(pair)
            if person == "me" and ctx.public:
                person = None  # you sign in at your own address, never at the friends' door
        elif code and not ctx.public and self.check_passcode(code):
            person = "me"
        if person is None or (person != "me" and self.store.person(person) is None):
            self._rate_fail(ctx)
            time.sleep(0.4)
            raise ApiError(401, "That passcode isn't right." if code and not pair and not ctx.public else "That pairing code has expired or isn't right.")
        return self._new_device(ctx, person, body.get("name"))

    def logout(self, ctx):
        if ctx.device:
            self.store.remove_device(ctx.device["id"], ctx.person)

    def change_passcode(self, ctx, body):
        if not ctx.local:
            self._rate_check(ctx)
            if not self.check_passcode(str(body.get("current") or "")):
                self._rate_fail(ctx)
                raise ApiError(401, "Your current passcode isn't right.")
        wanted = words.normalize(body.get("next") or "")
        if wanted and len(wanted.replace("-", "")) < 12:
            raise ApiError(400, "Pick something longer: at least 12 letters.")
        code = self.set_passcode(wanted or words.passcode())
        if body.get("signOutOthers", True):
            keep = ctx.device["id"] if ctx.device else None
            for device in self.store.devices("me"):  # your devices; friends don't use the passcode
                if device["id"] != keep:
                    self.store.remove_device(device["id"], "me")
        return {"passcode": code}

    def whoami(self, ctx):
        device = ctx.device and {"id": ctx.device["id"], "name": ctx.device["name"]}
        pid = ctx.person
        person = self.store.person(pid) if pid else None
        return {"signedIn": ctx.signed_in, "trusted": ctx.local, "https": ctx.https, "version": __version__, "demo": self.demo,
                "public": ctx.public, "role": None if not pid else "owner" if pid == "me" else "friend",
                "person": public_person(person) if person else None,
                "device": device or ({"id": "local", "name": "This PC"} if ctx.local else None)}

    # ── settings ─────────────────────────────────────────────────────────────
    @staticmethod
    def _key(kind, pid):
        """Each person's own settings, timer and so on. The plain keys are yours."""
        return kind if pid == "me" else f"{kind}:{pid}"

    def settings(self, pid="me"):
        s = self.store.get(self._key("settings", pid))
        if s is None:
            person = self.store.person(pid)
            s = dict(default_settings(self.system_tz, friend=pid != "me"), name=person["name"] if person and pid != "me" else "")
            self.store.set(self._key("settings", pid), s)
        return s

    def put_settings(self, patch, pid="me"):
        with self.lock:
            merged = clean_settings(patch, self.settings(pid))
            self.store.set(self._key("settings", pid), merged)
        if isinstance(patch, dict) and merged["name"] and "name" in patch:
            self._rename(pid, merged["name"])
        self._changed({pid})
        return merged

    def _rename(self, pid, name):
        person = self.store.person(pid)
        if person and person["name"] != name:
            # a mark that was just the old initial follows the new name; one you picked stays
            mark = initial(name) if person["mark"] == initial(person["name"]) else person["mark"]
            self.store.save_person(dict(person, name=name, mark=mark, updated=now_ms()))

    def _note_tags(self, names, pid="me"):
        names = [n.strip()[:24] for n in names if n and n.strip()]
        if not names:
            return
        with self.lock:
            s = self.settings(pid)
            known = {t["name"].lower() for t in s["tags"]}
            added = False
            for name in names:
                if name.lower() not in known and len(s["tags"]) < 24:
                    s["tags"].append({"name": name, "color": TAG_COLORS[len(s["tags"]) % len(TAG_COLORS)]})
                    known.add(name.lower())
                    added = True
            if added:
                self.store.set(self._key("settings", pid), s)

    def species_for(self, sid, requested=None, pid="me"):
        kinds = logic.species()
        if requested in kinds:
            return requested
        if requested is None:  # from the homepage or a hand log: give the pond some variety
            return kinds[int(hashlib.sha256(sid.encode()).hexdigest(), 16) % len(kinds)]
        s = self.settings(pid)
        return s["species"] if s["species"] in kinds else "shiro"

    # ── the shared timer, and studying together ──────────────────────────────
    # Each person has one timer at a time. A guest's timer joins someone else's session (its
    # `room` is that session's id, its `host` that person): it counts the guest's own time, and
    # their duck hatches when the session they joined ends, or when they leave.
    @staticmethod
    def view(t, now):
        if not t:
            return None
        running = t["runFrom"] is not None
        elapsed = t["acc"] + (now - t["runFrom"] if running else 0)
        out = dict(t, elapsed=elapsed, running=running, now=now, remaining=None, endsAt=None)
        if t["mode"] in ("timer", "pomo"):
            out["remaining"] = max(0, t["planned"] - elapsed)
            out["endsAt"] = t["runFrom"] + t["planned"] - t["acc"] if running else None
        if t["mode"] == "pomo":
            out["round"], out["phase"], out["phaseLeft"] = pomo_phase(t, elapsed)
            out["focused"] = pomo_focus(t, elapsed)
        return out

    def timer(self, pid="me", now=None):
        return self._timer_view(pid, self.store.get(self._key("timer", pid)), now or now_ms())

    def _timer_view(self, pid, t, now, timers=None):
        """A timer as its person sees it: with everyone in the session, and for a guest, the host's
        clock (their duck hatches when it runs out)."""
        v = self.view(t, now)
        if not v:
            return None
        timers = self.store.timers() if timers is None else timers
        host = t.get("host") or pid
        room = t.get("room") or t["id"]
        if t.get("room"):
            host_t = timers.get(host)
            hv = self.view(host_t, now) if host_t and host_t["id"] == room else None
            v["hostTimer"] = {k: hv[k] for k in HOST_CLOCK if k in hv} if hv else None  # their clock, not their device
        v["party"] = self._party(room, host, timers, now)
        v["cheers"] = [{k: c[k] for k in ("id", "from", "name", "text", "at")}
                       for c in self.store.get(self._key("cheers", pid)) or [] if c["timer"] == t["id"]]
        return v

    def _party(self, room, host, timers, now):
        out = []
        for pid, t in timers.items():
            if (pid == host and t["id"] == room) or t.get("room") == room:
                out.append({"person": pid, "species": t["species"], "tag": t["tag"], "since": t["startedAt"],
                            "elapsed": self.view(t, now)["elapsed"], "running": t["runFrom"] is not None, "host": pid == host})
        return sorted(out, key=lambda g: (not g["host"], g["since"]))

    def timer_action(self, ctx, body):
        action, pid = body.get("action"), ctx.person
        hatched = []
        with self.lock:
            now, key = now_ms(), self._key("timer", pid)
            t = self.store.get(key)
            if action == "start":
                result = self._start(ctx, pid, t, body, now)
            elif action == "join":
                result = self._join(ctx, pid, t, body, now)
            elif action == "drop":  # a device that lost its connection carried this timer on by itself
                if t and body.get("id") == t["id"]:
                    self.store.set(key, None)
                    hatched = self._end_guests(t["id"], now, t)
                result = {"timer": None}
            elif action in ("pause", "resume", "finish", "cancel"):
                if not t:
                    raise ApiError(409, "No timer is running.", timer=None)
                if body.get("id") and body["id"] != t["id"]:
                    raise ApiError(409, "That timer has already ended.", timer=self.timer(pid, now))
                result = getattr(self, "_" + action)(pid, t, now, body)
                if action in ("finish", "cancel") and not t.get("room"):
                    hatched = self._end_guests(t["id"], now, t)  # the session's over, so its guests hatch too
            else:
                raise ApiError(400, "Unknown timer action.")
            if result.get("timer"):
                result["timer"] = self.timer(pid, now)
        self._changed(self._audience(pid))
        if result.get("session") and result["session"]["status"] == "done" and action == "start":
            self._notify_hatched(result["session"], pid)
        for guest, session in hatched:
            self._notify_hatched(session, guest, host=pid)
        return result

    def _start(self, ctx, pid, t, body, now):
        if t:
            raise ApiError(409, "A timer is already running.", timer=self.timer(pid, now))
        s = self.settings(pid)
        mode = body.get("mode") if body.get("mode") in ("stopwatch", "pomo") else "timer"
        minutes = max(1, min(300, _int(body.get("minutes", s["minutes"]), "minutes")))
        pomo = clean_pomo(body.get("pomo"), s.get("pomo")) if mode == "pomo" else None
        if pomo:
            minutes = pomo["focus"] * pomo["rounds"]  # what the duck is for: the focus, not the breaks
        sid = str(body.get("id") or new_id())
        if not ID_RE.match(sid) or self.store.get_session(sid):
            sid = new_id()  # never reuse an id that is already logged
        started = now
        if body.get("startedAt") is not None:
            asked = _int(body["startedAt"], "startedAt")
            if now - 6 * 3600 * 1000 <= asked <= now:
                started = asked  # a timer begun while this device was offline
        acc, run_from = 0, started
        if body.get("elapsed") is not None:  # handed back by a device that carried it on offline (maybe paused)
            acc = max(0, min(_int(body["elapsed"], "elapsed"), now - started))
            run_from = now if body.get("running", True) else None
        tag = str(s["tag"] if body.get("tag") is None else body["tag"]).strip()[:40]
        source = clean_source(body.get("source")) or "dakku"
        t = {"id": sid, "mode": mode, "planned": minutes * MINUTE if mode == "timer" else None,
             "startedAt": started, "acc": acc, "runFrom": run_from, "tag": tag,
             "species": self.species_for(sid, body.get("species") or (None if s["randomSpecies"] else s["species"]), pid),
             "deep": bool(body.get("deep")), "source": source, "device": ctx.device_name or "Browser", "updated": now,
             "open": bool(s.get("openSessions", True) if body.get("open") is None else body["open"]),
             "announced": False}
        if pomo:
            t["pomo"] = {"focus": pomo["focus"] * MINUTE, "brk": pomo["brk"] * MINUTE, "rounds": pomo["rounds"]}
            t["planned"] = pomo["rounds"] * t["pomo"]["focus"] + (pomo["rounds"] - 1) * t["pomo"]["brk"]
            t["phaseKey"] = "1:focus"
        self._note_tags([tag], pid)
        if mode in ("timer", "pomo") and self.view(t, now)["elapsed"] >= t["planned"]:  # it already ran out while offline
            return {"timer": None, "session": self._log(t, minutes, "done", now, pid=pid, rounds=pomo["rounds"] if pomo else 0)}
        self.store.set(self._key("timer", pid), t)
        what = f"{minutes} min" if mode == "timer" else f"pomodoro {pomo['rounds']}×{pomo['focus']}/{pomo['brk']}" if pomo else "stopwatch"
        log("timer started:", t["tag"] or "(no tag)", what, "from", t["device"], "by", pid)
        return {"timer": self.view(t, now)}

    def _join(self, ctx, pid, t, body, now):
        """Join someone's session as it runs, with a duck of your own."""
        if t:
            raise ApiError(409, "Finish your own session first.", timer=self.timer(pid, now))
        room = str(body.get("room") or "")
        timers = self.store.timers()
        host = next((h for h, ht in timers.items() if ht["id"] == room and not ht.get("room")), None)
        if host is None:
            raise ApiError(404, "That session has already ended.")
        host_t = timers[host]
        if host == pid or not host_t.get("open") or not self._mates(pid, host):
            raise ApiError(403, "You can only join sessions of people in your groups.")
        s = self.settings(pid)
        gid = new_id()
        tag = str(s["tag"] if body.get("tag") is None else body["tag"]).strip()[:40]
        guest = {"id": gid, "mode": "room", "planned": None, "room": room, "host": host, "startedAt": now, "acc": 0,
                 "runFrom": now, "tag": tag, "hostAt": self.view(host_t, now)["elapsed"], "announced": False,
                 "species": self.species_for(gid, body.get("species") or (None if s["randomSpecies"] else s["species"]), pid),
                 "deep": bool(body.get("deep")), "source": "dakku", "device": ctx.device_name or "Browser", "updated": now}
        self._note_tags([tag], pid)
        self.store.set(self._key("timer", pid), guest)
        log("joined:", pid, "in", host + "'s session")
        return {"timer": self.view(guest, now)}

    def _pause(self, pid, t, now, body):
        if t["runFrom"] is not None:
            t.update(acc=t["acc"] + now - t["runFrom"], runFrom=None, updated=now)
            self.store.set(self._key("timer", pid), t)
        return {"timer": self.view(t, now)}

    def _resume(self, pid, t, now, body):
        if t["runFrom"] is None:
            t.update(runFrom=now, updated=now)
            self.store.set(self._key("timer", pid), t)
        return {"timer": self.view(t, now)}

    def _studied(self, pid, t, now):
        """How long (ms) a timer's person has studied: for a pomodoro, not counting its breaks, and for
        a guest of one, only while the host was focusing."""
        elapsed = self.view(t, now)["elapsed"]
        if t["mode"] == "pomo":
            return pomo_focus(t, elapsed)
        if t["mode"] == "room":
            host_t = self.store.timers().get(t["host"])
            if host_t and host_t["id"] == t["room"] and host_t["mode"] == "pomo" and "hostAt" in t:
                h = min(self.view(host_t, now)["elapsed"], host_t["planned"])
                return max(0, pomo_focus(host_t, h) - pomo_focus(host_t, t["hostAt"]))
        return elapsed

    def _finish(self, pid, t, now, body):
        """Done: your duck hatches for the time you studied. (For a guest, that's leaving early.)"""
        minutes = round(self._studied(pid, t, now) / MINUTE)
        if t["mode"] in ("timer", "pomo"):
            minutes = min(minutes, round((t["planned"] if t["mode"] == "timer" else t["pomo"]["focus"] * t["pomo"]["rounds"]) / MINUTE))
        minutes = min(minutes, MAX_STOPWATCH // MINUTE)
        rounds = pomo_rounds(t, self.view(t, now)["elapsed"]) if t["mode"] == "pomo" else 0
        self.store.set(self._key("timer", pid), None)
        if minutes < 1:
            return {"timer": None, "session": None}
        return {"timer": None, "session": self._log(t, minutes, "done", now, pid=pid, rounds=rounds)}

    def _cancel(self, pid, t, now, body):
        """Giving up: the egg goes cold. It stays in your pond but doesn't count toward goals. In a
        session's first seconds, it's called off instead, as if it never started."""
        v = self.view(t, now)
        self.store.set(self._key("timer", pid), None)
        studied = self._studied(pid, t, now)
        if v["elapsed"] < MINUTE or studied < MINUTE or now - t["startedAt"] <= UNDO_MS + 2000 and body.get("undo"):
            if body.get("undo"):
                log("called off:", t["tag"] or "(no tag)", "by", pid)
            return {"timer": None, "session": None}
        note = "Left Dakku during deep focus" if body.get("reason") == "left" else ""
        return {"timer": None, "session": self._log(t, int(studied // MINUTE), "withered", now, note, pid=pid)}

    def _log(self, t, minutes, status, now, note="", pid="me", rounds=0):
        joined = t.get("joined") or any(g.get("room") == t["id"] and now - g["startedAt"] >= UNDO_MS for g in self.store.timers().values())
        room = t.get("room") or (t["id"] if joined else "")
        session = {"id": t["id"], "start": t["startedAt"], "minutes": minutes, "tag": t["tag"], "species": t["species"],
                   "status": status, "source": t["source"], "manual": 0, "note": note, "updated": now, "person": pid,
                   "room": room, "rounds": rounds}
        row, _ = self.store.upsert(session)
        if row["person"] != pid:  # someone else's session has its id: it's still this person's, under a new one
            log("a session's id was taken by", row["person"], "so", pid, "gets a new one")
            row, _ = self.store.upsert(dict(session, id=secrets.token_urlsafe(9)))
        log("logged:", status, f"{minutes} min", t["tag"] or "(no tag)", "for", pid, "together" if room else "")
        return public(row)

    def _end_guests(self, room, now, host_t=None):
        """The session `room` is over: everyone who joined it hatches their duck. (`host_t` is the
        session itself, already gone from the timers, so a pomodoro's breaks can still be left out.)"""
        return [self._end_guest(pid, t, now, host_t) for pid, t in self.store.timers().items() if t.get("room") == room]

    def _end_guest(self, pid, t, now, host_t=None):
        key = self._key("timer", pid)
        current = self.store.get(key)
        if not current or current["id"] != t["id"]:
            return pid, None
        if host_t and host_t.get("mode") == "pomo" and "hostAt" in current:
            h = min(self.view(host_t, now)["elapsed"], host_t["planned"])
            studied = max(0, pomo_focus(host_t, h) - pomo_focus(host_t, current["hostAt"]))
        else:
            studied = self._studied(pid, current, now)
        minutes = min(round(studied / MINUTE), MAX_STOPWATCH // MINUTE)
        self.store.set(key, None)
        return pid, (self._log(current, minutes, "done", now, pid=pid) if minutes >= 1 else None)

    def _check_timers(self, now):
        hatched, started, joined, phases = [], [], [], []
        with self.lock:
            timers = self.store.timers()
            # once a session is past its first seconds (when it can still be called off), friends hear of it
            for pid, t in list(timers.items()):
                if t.get("announced", True) or now - t["startedAt"] < UNDO_MS:
                    continue
                t["announced"] = True
                self.store.set(self._key("timer", pid), t)
                fresh = now - t["startedAt"] < 5 * MINUTE  # not one handed back long after it began
                if t.get("room"):
                    host_t = timers.get(t["host"])
                    if host_t and host_t["id"] == t["room"] and not host_t.get("joined"):
                        host_t["joined"] = True
                        self.store.set(self._key("timer", t["host"]), host_t)
                    if fresh:
                        joined.append((t["host"], pid))
                elif t.get("open") and fresh:
                    started.append((pid, dict(t)))
            for pid, t in timers.items():
                if t["mode"] == "pomo" and t["runFrom"] is not None:
                    rnd, phase, _ = pomo_phase(t, t["acc"] + now - t["runFrom"])
                    key = f"{rnd}:{phase}"
                    if key != t.get("phaseKey") and t["acc"] + now - t["runFrom"] < t["planned"]:
                        t["phaseKey"] = key
                        self.store.set(self._key("timer", pid), t)
                        phases.append((pid, t, rnd, phase))
            for pid, t in timers.items():
                if t.get("room"):  # a guest: hatches when the session they joined is gone
                    host = timers.get(t["host"])
                    if not host or host["id"] != t["room"] or self.view(t, now)["elapsed"] >= MAX_STOPWATCH:
                        hatched.append(self._end_guest(pid, t, now) + (t["host"],))
                    continue
                if t["runFrom"] is None:
                    continue
                elapsed = t["acc"] + now - t["runFrom"]
                if t["mode"] == "timer" and elapsed >= t["planned"]:
                    session = self._log(t, round(t["planned"] / MINUTE), "done", now, pid=pid)
                elif t["mode"] == "pomo" and elapsed >= t["planned"]:
                    session = self._log(t, round(t["pomo"]["focus"] * t["pomo"]["rounds"] / MINUTE), "done", now, pid=pid,
                                        rounds=t["pomo"]["rounds"])
                elif t["mode"] == "stopwatch" and elapsed >= MAX_STOPWATCH:
                    session = self._log(t, MAX_STOPWATCH // MINUTE, "done", now, "Stopped automatically after 4 hours", pid=pid)
                else:
                    continue
                self.store.set(self._key("timer", pid), None)
                hatched.append((pid, session, None))
                hatched.extend(g + (pid,) for g in self._end_guests(t["id"], now, t))
        if hatched or started or joined or phases:
            self._changed()
        for pid, session, host in hatched:
            self._notify_hatched(session, pid, host=host)
        for host, t in started:
            self._notify_started(host, t)
        for host, guest in joined:
            self._notify_joined(host, guest)
        for pid, t, rnd, phase in phases:
            self._notify_phase(pid, t, rnd, phase, timers)

    # ── sync ─────────────────────────────────────────────────────────────────
    def pull(self, since, pid="me"):
        now = now_ms()
        with self.store.lock:
            rows, cursor = self.store.since(since, pid), self.store.rev()
        return {"cursor": cursor, "sessions": [public(r) for r in rows], "settings": self.settings(pid),
                "timer": self.timer(pid, now), "now": now}

    def push(self, body, pid="me"):
        ops = body.get("ops") or []
        if not isinstance(ops, list) or len(ops) > 5000:
            raise ApiError(400, "ops must be a list of at most 5000 changes")
        now, clean, tags = now_ms(), [], []
        # whose sessions are still running: their ids are seen in Together, and only their timers log them
        running = {t["id"]: who for who, t in self.store.timers().items()}
        for op in ops:
            if not isinstance(op, dict):
                continue
            if op.get("op") == "upsert":
                s = clean_session(op.get("session"), now)
                existing = self.store.get_session(s["id"])
                if existing is None:
                    if "start" not in s or "minutes" not in s or running.get(s["id"], pid) != pid:
                        continue
                    s.setdefault("status", "done")
                    s.setdefault("source", "sync")
                    if not s.get("species"):
                        s["species"] = self.species_for(s["id"], pid=pid)
                    s["person"] = pid
                elif existing["person"] != pid:
                    continue  # someone else's session
                s["person"] = pid  # (and the store won't let it change hands, whatever happens in between)
                clean.append({"op": "upsert", "session": s})
                tags.append(s.get("tag", ""))
            elif op.get("op") == "delete":
                sid = str(op.get("id", ""))
                existing = self.store.get_session(sid) if ID_RE.match(sid) else None
                if existing and existing["person"] == pid:
                    clean.append({"op": "delete", "id": sid, "updated": _when(op.get("updated"), now)})
        changed = self.store.apply(clean)
        self._note_tags(tags, pid)
        if isinstance(body.get("settings"), dict):
            with self.lock:
                self.store.set(self._key("settings", pid), clean_settings(body["settings"], self.settings(pid)))
            if body["settings"].get("name"):
                self._rename(pid, self.settings(pid)["name"])
            changed += 1
        if changed:
            self._changed({pid})
        return self.pull(max(0, min(_int(body.get("since") or 0, "since"), 2 ** 62)), pid)

    def import_data(self, body):
        data = body.get("data", body)
        if not isinstance(data, dict):
            raise ApiError(400, "That isn't a backup file.")
        now, items = now_ms(), []
        if isinstance(data.get("sessions"), list):  # a Dakku export
            items = [dict(s, source=s.get("source") or "import") for s in data["sessions"] if isinstance(s, dict) and not s.get("deleted")]
        elif isinstance(data.get("study"), dict) and isinstance(data["study"].get("sessions"), list):  # a Genkan backup
            items = [{"id": s.get("id"), "start": s.get("start"), "minutes": s.get("minutes"), "tag": s.get("label", ""),
                      "manual": s.get("manual", False), "source": "genkan"} for s in data["study"]["sessions"] if isinstance(s, dict)]
        else:
            raise ApiError(400, "That file isn't a Dakku or Genkan backup.")
        ops = []
        for item in items:
            item.setdefault("updated", now)
            try:
                clean_session(item, now)
            except ApiError:
                continue
            ops.append({"op": "upsert", "session": item})
        result = self.push({"ops": ops, "since": body.get("since", 0)})
        result["imported"] = len(ops)
        return result

    def bootstrap(self, ctx):
        now, pid = now_ms(), ctx.person
        with self.store.lock:
            rows, cursor = self.store.sessions(person=pid), self.store.rev()
        return {"me": self.whoami(ctx), "settings": self.settings(pid), "timer": self.timer(pid, now), "cursor": cursor,
                "sessions": [public(r) for r in rows], "now": now, "vapidKey": self.vapid.public_b64,
                "anki": self.anki_view() if pid == "me" else None, "together": self.together(pid),
                "server": {"version": __version__, "timeZone": self.system_tz, "since": int(self.started * 1000),
                           # your PC's addresses are yours: a friend only needs the door they came in by
                           "addresses": self.addresses() if ctx.owner else {"friends": self.addresses().get("friends")}}}

    # ── live updates (server-sent events) ────────────────────────────────────
    def subscribe(self, person="me"):
        """A page's live updates. Each person has at most LIVE_PER_PERSON at once: past that, their oldest
        is let go (see still_wanted), as the newest is the page they're looking at."""
        q = queue.Queue(maxsize=30)
        with self._clients_lock:
            theirs = [c for c, p in self._clients.items() if p == person and c not in self._let_go]
            self._let_go.update(theirs[:max(0, len(theirs) - LIVE_PER_PERSON + 1)])
            self._clients[q] = person
        return q

    def still_wanted(self, q):
        return q not in self._let_go

    def unsubscribe(self, q):
        with self._clients_lock:
            self._clients.pop(q, None)
            self._let_go.discard(q)

    def _changed(self, people=None):
        """Tell open pages something changed: only those of `people`, or everyone's."""
        with self._clients_lock:
            clients = [(q, p) for q, p in self._clients.items() if people is None or p in people]
        if not clients:
            return
        rev, now, timers, events = self.store.rev(), now_ms(), self.store.timers(), {}
        for q, person in clients:
            if person not in events:
                t = timers.get(person)
                events[person] = json.dumps({"rev": rev, "timer": self._timer_view(person, t, now, timers) if t else None,
                                             "together": True}, ensure_ascii=False)
            try:
                q.put_nowait(events[person])
            except queue.Full:
                pass

    def _audience(self, pid):
        """Whoever should hear about `pid` studying: them, and everyone in a group with them."""
        return {pid} | self._mates(pid)

    def _mates(self, pid, other=None):
        """Everyone in a group with `pid` (or, with `other`, whether those two share one)."""
        mates = set()
        for g in self.store.groups():
            if pid in g["members"]:
                mates.update(g["members"])
        mates.discard(pid)
        return other in mates if other is not None else mates

    # ── notifications ────────────────────────────────────────────────────────
    def push_subscribe(self, ctx, body):
        sub = body.get("subscription") or {}
        endpoint, keys = str(sub.get("endpoint") or ""), sub.get("keys") or {}
        if len(endpoint) > 2048 or not webpush.valid_endpoint(endpoint):
            raise ApiError(400, "That push service isn't supported.")
        try:
            ec.decode_point(webpush.unb64u(str(keys["p256dh"])[:100]))
            if len(webpush.unb64u(str(keys["auth"])[:40])) != 16:  # (a browser's auth secret is 16 bytes)
                raise ValueError
        except (KeyError, ValueError, TypeError):
            raise ApiError(400, "That subscription's keys look wrong.")
        if not ORIGIN_RE.match(ctx.origin):
            raise ApiError(400, "Notifications need Dakku opened over https.")
        self.store.add_push(endpoint, keys["p256dh"], keys["auth"], ctx.origin, ctx.device_id, now_ms(), ctx.person, keep=PUSH_PER_PERSON)
        return {"ok": True}

    def notify(self, payload, urgency="normal", device_id=None, topic=None, wait=False, person="me"):
        subs = self.store.pushes(device_id, person)
        results = []

        def deliver():
            for sub in subs:
                status, detail = webpush.send(sub, payload, self.vapid, sub["origin"], urgency=urgency, topic=topic)
                results.append({"status": status})  # (what the push service said stays in the log)
                if status in (404, 410):
                    self.store.remove_push(sub["endpoint"])
                else:
                    self.store.push_result(sub["endpoint"], 200 <= status < 300)
                log("push", status, payload.get("tag", ""), detail[:120])

        if wait:
            deliver()
            return results
        if subs:
            threading.Thread(target=deliver, daemon=True).start()
        return results

    def summary(self, pid="me"):
        s = self.settings(pid)
        return logic.summary(self.store.sessions(person=pid), s["goal"], logic.zone(s["timeZone"]), now_ms())

    def _name(self, pid):
        person = self.store.person(pid)
        return person["name"] if person else "Someone"

    def _notify_hatched(self, session, pid="me", host=None):
        if not session or session["status"] != "done" or not self.store.pushes(person=pid):
            return
        info = self.summary(pid)
        duck = logic.noun(session["species"])
        what = f" of {session['tag']}" if session["tag"] else ""
        together = f" with {self._name(host)}" if host else ""
        streak = f" · {info['streak']}-day streak" if info["streak"] else ""
        body = f"A {duck} hatched: {logic.fmt_minutes(session['minutes'])}{what}{together}. Today {info['today']}/{info['goal']} min{streak}."
        self.notify({"title": "鴨 · 誕生!", "body": body, "tag": "dakku-timer", "url": "/"}, urgency="high", topic="dakku-timer", person=pid)

    def _notify_joined(self, host, guest):
        if self.store.pushes(person=host):
            self.notify({"title": "鴨 · 一緒", "body": f"{self._name(guest)} joined your session.", "tag": "dakku-room", "url": "/"},
                        topic="dakku-room", person=host)

    def _notify_phase(self, pid, t, rnd, phase, timers):
        """A pomodoro moved on: a break, or back to focusing. Everyone in the session hears it."""
        p = t["pomo"]
        if phase == "break":
            body = f"Break time: {logic.fmt_minutes(round(p['brk'] / MINUTE))}. Round {rnd} of {p['rounds']} done."
        else:
            body = f"Back to focus: round {rnd} of {p['rounds']}, {logic.fmt_minutes(round(p['focus'] / MINUTE))}."
        title = "鴨 · 休憩" if phase == "break" else "鴨 · 集中"
        for who in [pid] + [g for g, gt in timers.items() if gt.get("room") == t["id"]]:
            if self.store.pushes(person=who):
                self.notify({"title": title, "body": body, "tag": "dakku-timer", "url": "/"}, urgency="high", topic="dakku-timer", person=who)

    def _notify_started(self, host, t):
        """Let friends know someone started studying, so they can join in."""
        what = f" of {t['tag']}" if t["tag"] else ""
        length = (f"{logic.fmt_minutes(round(t['planned'] / MINUTE))}" if t["mode"] == "timer"
                  else f"a pomodoro ({t['pomo']['rounds']} × {round(t['pomo']['focus'] / MINUTE)} min)" if t["mode"] == "pomo"
                  else "an open-ended session")
        for mate in self._mates(host):
            if self.settings(mate).get("friendAlerts", True) and self.store.pushes(person=mate):
                self.notify({"title": "鴨 · 一緒にどう？", "body": f"{self._name(host)} started {length}{what}. Join in?",
                             "tag": f"dakku-friend-{host}", "url": "/#together"}, topic="dakku-friend", person=mate)

    # ── cheers ───────────────────────────────────────────────────────────────
    def cheer(self, ctx, body):
        """A cheer for someone studying right now: a short message that pops up on their screen and
        their phone. You can cheer anyone whose session you can see in Together (and join)."""
        sender, to = ctx.person, str(body.get("to") or "")
        text = " ".join(str(body.get("text") or "").split())[:CHEER_LEN]
        if not text:
            raise ApiError(400, "Write something to cheer them on with.")
        if not sender or to == sender:
            raise ApiError(400, "Cheer on someone else.")
        rooms = (self.together(sender) or {}).get("rooms", [])
        if not any(r["host"] == to or any(g["person"] == to for g in r["party"]) for r in rooms):
            raise ApiError(409, "They're not studying where you can see right now.")
        now = now_ms()
        with self.lock:
            sent = [x for x in self._cheers_sent.get(sender, []) if now - x[1] < 3_600_000]
            if any(who == to and now - at < CHEER_GAP for who, at in sent):
                raise ApiError(429, "Give them a moment before the next one.")
            if len(sent) >= CHEER_HOURLY:
                raise ApiError(429, "That's a lot of cheering for one hour. Try again a bit later.")
            self._cheers_sent[sender] = sent + [(to, now)]
            t = self.store.get(self._key("timer", to))
            key = self._key("cheers", to)
            kept = [c for c in self.store.get(key) or [] if now - c["at"] < 86_400_000][-29:]
            self.store.set(key, kept + [{"id": new_id(), "from": sender, "name": self._name(sender), "text": text,
                                         "at": now, "timer": t["id"]}])
        if self.settings(to).get("cheerAlerts", True) and self.store.pushes(person=to):
            self.notify({"title": "鴨 · 応援", "body": f"{self._name(sender)}: {text}", "tag": f"dakku-cheer-{sender}", "url": "/"},
                        topic="dakku-cheer", person=to)
        log("cheer:", self._name(sender), "→", self._name(to))
        self._changed({to})
        return {"ok": True}

    def _check_reminders(self, now):
        for pid in [p["id"] for p in self.store.people()]:
            s = self.settings(pid)
            r = s.get("reminder") or {}
            if not r.get("enabled") or not self.store.pushes(person=pid):
                continue
            local = datetime.fromtimestamp(now / 1000, logic.zone(s["timeZone"]))
            if r.get("weekdaysOnly", True) and local.weekday() >= 5:
                continue
            hh, mm = map(int, r.get("time", "20:00").split(":"))
            late = local.hour * 60 + local.minute - (hh * 60 + mm)
            today, sent = local.date().isoformat(), self._key("reminderSent", pid)
            if late < 0 or self.store.get(sent) == today:
                continue
            self.store.set(sent, today)
            if late > 180 or self.store.get(self._key("timer", pid)):
                continue
            info = self.summary(pid)
            if info["today"] >= info["goal"]:
                continue
            need = info["goal"] - info["today"]
            body = (f"{need} more min today keeps your {info['streak']}-day streak going." if info["streak"]
                    else f"{need} min today starts a new streak.")
            self.notify({"title": "鴨 · 今日の卵", "body": body, "tag": "dakku-reminder", "url": "/"}, person=pid)

    def recap(self, pid="me", now=None):
        """The week in a line, for Sunday's notification: None for a week with no ducks."""
        s, now = self.settings(pid), now or now_ms()
        rows, tz = self.store.sessions(person=pid), logic.zone(s["timeZone"])
        w = logic.week(rows, tz, now)
        if not w["ducks"]:
            return None
        info = logic.summary(rows, s["goal"], tz, now)
        best = f" Best day: {w['best'].strftime('%A')}, {logic.fmt_minutes(w['bestMinutes'])}." if w["days"] > 1 else ""
        streak = f" {info['streak']}-day streak." if info["streak"] > 1 else ""
        ducks = "1 duck" if w["ducks"] == 1 else f"{w['ducks']} ducks"
        return f"This week: {logic.fmt_minutes(w['minutes'])} and {ducks}.{best}{streak}"

    def _check_recaps(self, now):
        for pid in [p["id"] for p in self.store.people()]:
            s = self.settings(pid)
            if not s.get("weeklyRecap", True) or not self.store.pushes(person=pid):
                continue
            local = datetime.fromtimestamp(now / 1000, logic.zone(s["timeZone"]))
            if local.weekday() != 6 or local.hour * 60 + local.minute < RECAP_AT:
                continue
            monday, sent = (local.date() - timedelta(days=6)).isoformat(), self._key("recapSent", pid)
            if self.store.get(sent) == monday:
                continue
            self.store.set(sent, monday)
            body = self.recap(pid, now) if local.hour < 23 else None  # (late: the PC was off all evening)
            if body:
                self.notify({"title": "鴨 · 今週", "body": body, "tag": "dakku-recap", "url": "/#stats"}, topic="dakku-recap", person=pid)

    # ── people, groups and invites ───────────────────────────────────────────
    def _person_or_404(self, pid):
        person = self.store.person(pid)
        if not person:
            raise ApiError(404, "No such person.")
        return person

    def _group_or_404(self, gid):
        group = next((g for g in self.store.groups() if g["id"] == gid), None)
        if not group:
            raise ApiError(404, "No such group.")
        return group

    def _next_color(self):
        used = [p["color"] for p in self.store.people()]
        return min(TAG_COLORS, key=lambda c: (used.count(c), TAG_COLORS.index(c)))

    def update_person(self, ctx, pid, body):
        """Name, color and mark: your own, or anyone's if it's your Dakku."""
        if pid != ctx.person and not ctx.owner:
            raise ApiError(403, "That's someone else's profile.")
        person = self._person_or_404(pid)
        name = str(body.get("name", person["name"]) or "").strip()[:30] or person["name"]
        color = str(body.get("color") or person["color"])
        mark = person["mark"]
        if "mark" in body:
            mark = clean_mark(body["mark"], name)
        elif mark == initial(person["name"]):  # just the initial: it follows a new name
            mark = initial(name)
        person = dict(person, name=name, color=color if COLOR_RE.match(color) else person["color"], mark=mark, updated=now_ms())
        self.store.save_person(person)
        with self.lock:
            s = self.settings(pid)
            if s["name"] != name:
                self.store.set(self._key("settings", pid), dict(s, name=name))
        self._changed(self._audience(pid))
        return public_person(person)

    def remove_person(self, pid):
        if pid == "me":
            raise ApiError(400, "You can't remove yourself from your own Dakku.")
        self._person_or_404(pid)
        with self.lock:
            t = self.store.get(self._key("timer", pid))
            if t:
                self.store.set(self._key("timer", pid), None)
                if not t.get("room"):
                    self._end_guests(t["id"], now_ms())
        audience = self._audience(pid)
        self.store.remove_person(pid)
        self._changed(audience)
        return {"ok": True}

    def people_view(self):
        """Everyone on your Dakku, for you to look after: their devices, groups and totals."""
        groups, now, out = self.store.groups(), now_ms(), []
        for person in self.store.people():
            devices = self.store.devices(person["id"])
            info = self.summary(person["id"])
            out.append(dict(public_person(person), created=person["created"], devices=devices,
                            lastSeen=max([d["last_seen"] for d in devices] or [0]),
                            groups=[g["id"] for g in groups if person["id"] in g["members"]],
                            minutes=self.store.focused_minutes(person["id"]), week=info["week"], streak=info["streak"],
                            studying=bool(self.store.get(self._key("timer", person["id"])))))
        return {"people": out, "groups": groups, "invites": self.store.invites(now)}

    def create_group(self, body):
        name = str(body.get("name") or "").strip()[:40] or "Study group"
        theme = body.get("theme") if body.get("theme") in POND_THEMES else ""
        group = {"id": new_id(), "name": name, "theme": theme, "created": now_ms()}
        self.store.save_group(group)
        self.store.add_member(group["id"], "me", now_ms())
        return dict(group, members=["me"])

    def update_group(self, ctx, gid, body):
        group = self._group_or_404(gid)
        if ctx.person not in group["members"] and not ctx.owner:
            raise ApiError(403, "You're not in that group.")
        if "name" in body:
            group["name"] = str(body["name"] or "").strip()[:40] or group["name"]
        if "theme" in body and (body["theme"] in POND_THEMES or body["theme"] == ""):
            group["theme"] = body["theme"]
        self.store.save_group(group)
        self._changed(set(group["members"]))
        return group

    def remove_group(self, gid):
        group = self._group_or_404(gid)
        self.store.remove_group(gid)
        self._changed(set(group["members"]))
        return {"ok": True}

    def add_member(self, gid, pid):
        group = self._group_or_404(gid)
        self._person_or_404(pid)
        self.store.add_member(gid, pid, now_ms())
        self._changed(set(group["members"]) | {pid})
        return self._group_or_404(gid)

    def remove_member(self, ctx, gid, pid):
        """You can take anyone out of a group on your Dakku; anyone can leave one themselves."""
        group = self._group_or_404(gid)
        if pid != ctx.person and not ctx.owner:
            raise ApiError(403, "Only the person whose Dakku this is can do that.")
        if not self.store.remove_member(gid, pid):
            raise ApiError(404, "They're not in that group.")
        self._changed(set(group["members"]))
        return {"ok": True}

    def create_invite(self, body):
        """A link that brings someone in: into a group, or (with a person) onto a new device of theirs."""
        gid, pid = str(body.get("group") or ""), str(body.get("person") or "")
        if gid:
            self._group_or_404(gid)
        if pid:
            if pid == "me":
                raise ApiError(400, "Sign your own devices in with a pairing code instead.")
            self._person_or_404(pid)
        if not gid and not pid:
            raise ApiError(400, "Invite someone into a group.")
        uses = 1 if pid else max(1, min(20, _int(body.get("uses", 5), "uses")))
        days = max(1, min(30, _int(body.get("days", INVITE_DAYS), "days")))
        code, now = secrets.token_urlsafe(12), now_ms()
        invite = {"id": new_id(), "code_hash": hashlib.sha256(code.encode()).hexdigest(), "grp": gid, "person": pid,
                  "created": now, "expires": now + days * 86_400_000, "uses": uses}
        self.store.add_invite(invite)
        base = self.addresses().get("friends")
        return {"id": invite["id"], "code": code, "url": f"{base}/join#{code}" if base else None, "expires": invite["expires"], "uses": uses}

    def peek_invite(self, ctx, body):
        """Who an invite is from and what it's for, before accepting it, for the join page."""
        self._rate_check(ctx, guessable=False)
        code = str(body.get("code") or "").strip()
        invite = self.store.find_invite(hashlib.sha256(code.encode()).hexdigest(), now_ms()) if code else None
        if not invite:
            self._rate_fail(ctx, guessable=False)
            raise ApiError(404, "That invite has expired or was already used. Ask for a new one.")
        group = next((g for g in self.store.groups() if g["id"] == invite["grp"]), None)
        people = [self._name(pid) for pid in (group["members"] if group else [])]
        host = self._name("me")
        return {"from": host if host != "Me" else None, "group": group["name"] if group else None, "people": people,
                "forPerson": self._name(invite["person"]) if invite["person"] else None}

    def join(self, ctx, body):
        """Accept an invite: a new person with their own pond (or this device signed in as the
        person it's for), in the group it's for. Returns (token or None, person)."""
        self._rate_check(ctx, guessable=False)
        code = str(body.get("code") or "").strip()
        invite = self.store.use_invite(hashlib.sha256(code.encode()).hexdigest(), now_ms()) if code else None
        if not invite:
            self._rate_fail(ctx, guessable=False)
            time.sleep(0.4)
            raise ApiError(401, "That invite has expired or was already used. Ask for a new one.")
        now, token = now_ms(), None
        if invite["person"]:
            pid = invite["person"]
            self._person_or_404(pid)
            token, _ = self._new_device(ctx, pid, body.get("device"))
        elif ctx.person:  # already signed in here (a friend, or you): just join the group
            pid = ctx.person
        else:
            name = str(body.get("name") or "").strip()[:30]
            if not name:
                raise ApiError(400, "Pick a name, so your friends know which ducks are yours.")
            color = str(body.get("color") or "")
            pid = new_id()
            self.store.save_person({"id": pid, "name": name, "color": color if COLOR_RE.match(color) else self._next_color(),
                                    "mark": clean_mark(body.get("mark"), name), "created": now, "updated": now})
            self.settings(pid)  # their own settings, with their name
            token, _ = self._new_device(ctx, pid, body.get("device"))
            log("new friend:", name, "via invite", invite["id"])
        if invite["grp"]:
            self.store.add_member(invite["grp"], pid, now)
        self._changed(self._audience(pid))
        return token, public_person(self.store.person(pid))

    def together(self, pid):
        """Your groups, the people in them, and the sessions of theirs you could join right now."""
        if not pid:
            return None
        groups = [g for g in self.store.groups() if pid in g["members"]]
        ids = {pid} | {m for g in groups for m in g["members"]}
        people = [public_person(p) for p in self.store.people() if p["id"] in ids]
        now, timers, rooms = now_ms(), self.store.timers(), []
        mine = timers.get(pid)
        for host, t in timers.items():
            if t.get("room"):
                continue
            here = mine is not None and (mine["id"] == t["id"] or mine.get("room") == t["id"])
            if host != pid and not here and not (t.get("open") and host in ids and now - t["startedAt"] >= UNDO_MS):
                continue
            v = self.view(t, now)
            rooms.append({"id": t["id"], "host": host, "tag": t["tag"], "species": t["species"], "mode": t["mode"],
                          "startedAt": t["startedAt"], "remaining": v["remaining"], "endsAt": v["endsAt"],
                          "running": v["running"], "elapsed": v["elapsed"], "open": bool(t.get("open")),
                          "phase": v.get("phase"), "round": v.get("round"), "phaseLeft": v.get("phaseLeft"), "pomo": t.get("pomo"),
                          "party": self._party(t["id"], host, timers, now), "mine": here})
        return {"groups": groups, "people": people, "rooms": rooms}

    def group_view(self, ctx, gid):
        """A group's pond (everything its people did together) and how everyone's doing."""
        group = self._group_or_404(gid)
        if ctx.person not in group["members"] and not ctx.owner:
            raise ApiError(403, "You're not in that group.")
        members = group["members"]
        sessions = self.store.sessions_of(members)
        # a session counts as together when two or more of the group were in it (its room, or the
        # session the others joined, whose id is the room)
        in_room = {}
        for s in sessions:
            if s["room"]:
                in_room.setdefault(s["room"], set()).add(s["person"])
        for s in sessions:
            if s["id"] in in_room:
                in_room[s["id"]].add(s["person"])
        shared = {room for room, who in in_room.items() if len(who) >= 2}
        by_room = {}
        for s in sessions:
            if (s["room"] or s["id"]) in shared and not s["deleted"]:
                by_room.setdefault(s["room"] or s["id"], []).append(s)
        # each of them gets a duck here for the time they studied together: a guest, their time in
        # the session (the host was there all along); the host, the time anyone else was there
        pond = []
        for room, those in by_room.items():
            host = next((x for x in those if x["id"] == room), None)
            for x in those:
                others = [span(o) for o in those if o is not x and o is not host]
                if x is host:
                    together = min(x["minutes"], round(union(others) / MINUTE))
                elif host:
                    together = x["minutes"]
                else:  # the host isn't in this group: only the time with the others who are
                    together = round(union([(max(a, span(x)[0]), min(b, span(x)[1])) for a, b in others]) / MINUTE)
                if together >= 1:
                    pond.append(dict(public(x), person=x["person"], minutes=together, own=x["minutes"]))
        now, board = now_ms(), []
        for pid in members:
            person = self.store.person(pid)
            if not person:
                continue
            settings = self.settings(pid)
            tz = logic.zone(settings["timeZone"])
            mine = [s for s in sessions if s["person"] == pid]
            info = logic.summary(mine, settings["goal"], tz, now)
            today = logic.day_of(now, tz)
            month = [s for s in mine if s["status"] == "done" and logic.day_of(s["start"], tz).replace(day=1) == today.replace(day=1)]
            tags = {}
            for s in mine:
                if s["status"] == "done":
                    tags[s["tag"] or "Untagged"] = tags.get(s["tag"] or "Untagged", 0) + s["minutes"]
            colors = {t["name"]: t["color"] for t in settings["tags"]}
            board.append({"person": pid, "week": info["week"], "today": info["today"], "streak": info["streak"],
                          "best": info["best"], "month": sum(s["minutes"] for s in month),
                          "total": sum(s["minutes"] for s in mine if s["status"] == "done"),
                          "ducks": sum(1 for s in mine if s["status"] == "done"),
                          "together": sum(s["minutes"] for s in pond if s["person"] == pid and s["status"] == "done"),
                          "tags": [{"name": n, "minutes": m, "color": colors.get(n, "")} for n, m in sorted(tags.items(), key=lambda x: -x[1])[:6]],
                          "studying": bool(self.store.get(self._key("timer", pid)))})
        rooms = {}
        for s in pond:
            rooms.setdefault(s["room"] or s["id"], []).append(s)
        longest = max((max(x["minutes"] for x in group_sessions) for group_sessions in rooms.values()), default=0)
        people = [public_person(p) for p in self.store.people() if p["id"] in members]
        return {"group": group, "people": people, "pond": pond, "board": board,
                "stats": {"sessions": len(rooms), "minutes": sum(s["minutes"] for s in pond if s["status"] == "done"), "longest": longest}}

    # ── Anki ─────────────────────────────────────────────────────────────────
    def refresh_anki(self):
        if not self.anki_url:
            return self.store.get("anki")
        try:
            snap = anki.snapshot(self.anki_url)
        except Exception:
            self._anki_live = False
            return self.store.get("anki")
        snap["at"] = now_ms()
        self.store.set("anki", snap)
        self._anki_live = True
        return snap

    def anki_view(self, refresh=False):
        if self.demo:
            return {"data": demo_data.anki(now_ms(), logic.zone(self.settings()["timeZone"])), "live": True}
        data = self.refresh_anki() if refresh else self.store.get("anki")
        return {"data": data, "live": self._anki_live}

    # ── backups, export ──────────────────────────────────────────────────────
    def export(self, pid="me"):
        return {"app": "dakku", "version": __version__, "exportedAt": datetime.now().astimezone().isoformat(),
                "settings": self.settings(pid), "sessions": [public(r) for r in self.store.sessions(person=pid)]}

    def export_csv(self, pid="me"):
        tz = logic.zone(self.settings(pid)["timeZone"])
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["date", "start", "minutes", "tag", "duck", "status", "source", "note", "id"])
        for row in self.store.sessions(person=pid):
            local = datetime.fromtimestamp(row["start"] / 1000, tz)
            writer.writerow([local.date().isoformat(), local.strftime("%H:%M"), row["minutes"], row["tag"],
                             row["species"], row["status"], row["source"], row["note"], row["id"]])
        return out.getvalue()

    def backup(self, force=False):
        if not self.backup_dir:
            return None
        tz = logic.zone(self.settings()["timeZone"])
        local = datetime.now(tz)
        today = local.date().isoformat()
        last = self.store.get("backupDay")
        if not force and (last == today or (last is not None and local.hour < 3)):
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        private(self.backup_dir)  # (everything you've studied, and the hashes of your passcode and sign-ins)
        self.store.backup_to(self.backup_dir / f"dakku-{today}.db")
        tmp = self.backup_dir / f"dakku-{today}.json.tmp"
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            f.write(json.dumps(self.export(), ensure_ascii=False, indent=1))
        tmp.replace(self.backup_dir / f"dakku-{today}.json")
        private(self.backup_dir)
        for old in self.backup_dir.glob("mori-????-??-??.*"):  # from before Dakku had its name
            renamed = self.backup_dir / f"dakku-{old.name[5:]}"
            if renamed.exists():
                old.unlink()  # (a later one from the same day)
            else:
                old.rename(renamed)
        for ext in ("db", "json"):  # the newest ones are kept
            for old in sorted(self.backup_dir.glob(f"dakku-????-??-??.{ext}"))[:-KEEP_BACKUPS]:
                old.unlink()
        self.store.set("backupDay", today)
        log("backup saved:", self.backup_dir / f"dakku-{today}.json")
        return today

    def build_id(self):
        """A fingerprint of the app's files."""
        digest = hashlib.sha256()
        for path in sorted(self.web_dir.rglob("*")):
            if path.is_file():
                st = path.stat()
                digest.update(f"{path.relative_to(self.web_dir)}:{st.st_mtime_ns}:{st.st_size};".encode())
        return digest.hexdigest()[:12]

    # ── where to reach Dakku ──────────────────────────────────────────────────
    def addresses(self):
        stamp, cached = self._addresses_cache
        # a friends' door that isn't open yet is looked for again soon, so it's there right after enable-friends.sh
        if cached is not None and time.time() - stamp < (300 if cached.get("friends") or self.demo else 20):
            return cached
        found = {"lan": [], "tailnet": None, "https": None, "friends": self.friends_url}
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("10.255.255.255", 1))
            found["lan"].append(f"http://{probe.getsockname()[0]}:{self.port}")
            probe.close()
        except OSError:
            pass
        found["lan"].append(f"http://{socket.gethostname()}.local:{self.port}")
        try:
            status = json.loads(subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=4).stdout)
            dns = (status.get("Self") or {}).get("DNSName", "").rstrip(".")
            if dns:
                found["tailnet"] = f"http://{dns}:{self.port}"
                serve = subprocess.run(["tailscale", "serve", "status", "--json"], capture_output=True, text=True, timeout=4).stdout
                if f'"{dns}:443"' in serve and not self.demo:  # (that address is the real Dakku's)
                    found["https"] = f"https://{dns}"
                if f'"{dns}:{FRIENDS_HTTPS}": true' in serve and not self.demo:  # the friends' door, open to the internet
                    found["friends"] = f"https://{dns}:{FRIENDS_HTTPS}"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        self._addresses_cache = (time.time(), found)
        return found

    # ── the background loop ──────────────────────────────────────────────────
    def _scheduler(self):
        last_minute = last_anki = last_demo = 0
        try:
            self.backup()
        except Exception:
            traceback.print_exc()
        while not self._stop.wait(1):
            try:
                now = now_ms()
                self._check_timers(now)
                if now - last_minute >= MINUTE:
                    last_minute = now
                    self._check_reminders(now)
                    self._check_recaps(now)
                    self.backup()
                if now - last_anki >= 10 * MINUTE:
                    last_anki = now
                    threading.Thread(target=self.refresh_anki, daemon=True).start()
                if self.demo and now - last_demo >= 5 * MINUTE:
                    last_demo = now
                    demo_data.fill(self, now)  # the day's made-up ducks hatch as it goes on
            except Exception:
                traceback.print_exc()
