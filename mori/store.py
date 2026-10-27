"""SQLite storage for Dakku.

Every change to a session bumps a global revision number, so each device can ask
"what changed since revision N?" and stay in sync. Deleted sessions stay behind as
tombstones so the deletion reaches every device too.

Dakku is yours, and friends you invite get their own ponds on it. Every session, device and
notification subscription belongs to a person: "me" is you, the person whose PC this is.
Sessions done together share a `room`: the id of the session they joined.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  id      TEXT PRIMARY KEY,
  start   INTEGER NOT NULL,             -- ms since 1970
  minutes INTEGER NOT NULL,
  tag     TEXT NOT NULL DEFAULT '',
  species TEXT NOT NULL DEFAULT '',
  status  TEXT NOT NULL DEFAULT 'done', -- 'done' or 'withered'
  source  TEXT NOT NULL DEFAULT '',     -- 'mori', 'genkan', 'manual', 'import'
  manual  INTEGER NOT NULL DEFAULT 0,
  note    TEXT NOT NULL DEFAULT '',
  updated INTEGER NOT NULL,             -- last edit, ms; newest edit wins
  rev     INTEGER NOT NULL,             -- global revision of the last change
  deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sessions_by_rev ON sessions(rev);
CREATE INDEX IF NOT EXISTS sessions_by_start ON sessions(start);
CREATE TABLE IF NOT EXISTS devices (
  id         TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  created    INTEGER NOT NULL,
  last_seen  INTEGER NOT NULL,
  last_ip    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS push (
  endpoint  TEXT PRIMARY KEY,
  p256dh    TEXT NOT NULL,
  auth      TEXT NOT NULL,
  origin    TEXT NOT NULL,
  device_id TEXT NOT NULL DEFAULT '',
  created   INTEGER NOT NULL,
  failures  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS people (
  id      TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  color   TEXT NOT NULL,
  mark    TEXT NOT NULL,                -- the letter or emoji shown on their ducks
  created INTEGER NOT NULL,
  updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS groups (
  id      TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  theme   TEXT NOT NULL DEFAULT '',     -- the group pond's look
  created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  grp    TEXT NOT NULL,
  person TEXT NOT NULL,
  joined INTEGER NOT NULL,
  PRIMARY KEY (grp, person)
);
CREATE TABLE IF NOT EXISTS invites (
  id        TEXT PRIMARY KEY,
  code_hash TEXT NOT NULL UNIQUE,
  grp       TEXT NOT NULL DEFAULT '',   -- the group it adds you to
  person    TEXT NOT NULL DEFAULT '',   -- set: signs a new device in as this person instead
  created   INTEGER NOT NULL,
  expires   INTEGER NOT NULL,
  uses      INTEGER NOT NULL            -- how many more times it works
);
"""
# added after the first version: (table, column, definition)
LATER_COLUMNS = (("sessions", "person", "TEXT NOT NULL DEFAULT 'me'"), ("sessions", "room", "TEXT NOT NULL DEFAULT ''"),
                 ("devices", "person", "TEXT NOT NULL DEFAULT 'me'"), ("push", "person", "TEXT NOT NULL DEFAULT 'me'"),
                 ("sessions", "rounds", "INTEGER NOT NULL DEFAULT 0"))

COLUMNS = ("id", "start", "minutes", "tag", "species", "status", "source", "manual", "note", "updated", "rev", "deleted", "person", "room", "rounds")
DEFAULTS = {"tag": "", "species": "", "status": "done", "source": "", "manual": 0, "note": "", "deleted": 0, "person": "me", "room": "", "rounds": 0}


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.executescript(SCHEMA)
            for table, column, definition in LATER_COLUMNS:
                if column not in {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            self.db.execute("CREATE INDEX IF NOT EXISTS sessions_by_person ON sessions(person, rev)")
            self.db.execute("CREATE INDEX IF NOT EXISTS sessions_by_room ON sessions(room)")
            self._set(self.db, "schema", 2)

    @contextmanager
    def tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    # ── key/value ────────────────────────────────────────────────────────────
    @staticmethod
    def _get(db, key, default=None):
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def _set(db, key, value):
        db.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, json.dumps(value, ensure_ascii=False)))

    def get(self, key, default=None):
        with self.lock:
            return self._get(self.db, key, default)

    def set(self, key, value):
        with self.tx() as db:
            self._set(db, key, value)

    def _next_rev(self, db):
        rev = self._get(db, "rev", 0) + 1
        self._set(db, "rev", rev)
        return rev

    def rev(self):
        return self.get("rev", 0)

    # ── sessions ─────────────────────────────────────────────────────────────
    def get_session(self, sid):
        with self.lock:
            row = self.db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def upsert(self, data):
        """Insert or update by id. The newest `updated` wins; fields not given keep their value.
        Returns (row, changed)."""
        with self.tx() as db:
            return self._upsert(db, data)

    def _upsert(self, db, data):
        row = db.execute("SELECT * FROM sessions WHERE id=?", (data["id"],)).fetchone()
        if row is None and ("start" not in data or "minutes" not in data):
            raise KeyError("a new session needs a start and minutes")
        if row is not None and data["updated"] < row["updated"]:
            return dict(row), False
        merged = dict(row) if row else dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in COLUMNS and k not in ("rev", "deleted") and (row is None or k != "person")})
        merged["deleted"] = 0
        merged["rev"] = self._next_rev(db)
        db.execute(f"INSERT OR REPLACE INTO sessions({','.join(COLUMNS)}) VALUES({','.join('?' * len(COLUMNS))})",
                   [merged[c] for c in COLUMNS])
        return merged, True

    def delete(self, sid, updated):
        with self.tx() as db:
            return self._delete(db, sid, updated)

    def _delete(self, db, sid, updated):
        row = db.execute("SELECT updated, deleted FROM sessions WHERE id=?", (sid,)).fetchone()
        if row is None or row["deleted"] or updated < row["updated"]:
            return False
        db.execute("UPDATE sessions SET deleted=1, updated=?, rev=? WHERE id=?", (updated, self._next_rev(db), sid))
        return True

    def apply(self, ops):
        """Apply a batch of sync operations in one transaction. Returns how many changed anything."""
        changed = 0
        with self.tx() as db:
            for op in ops:
                if op["op"] == "upsert":
                    changed += self._upsert(db, op["session"])[1]
                elif op["op"] == "delete":
                    changed += self._delete(db, op["id"], op["updated"])
        return changed

    def rename_species(self, mapping):
        """Give sessions a new species name (for when Dakku's trees became ducks). Each change gets a
        new revision, so every device picks it up on its next sync."""
        changed = 0
        with self.tx() as db:
            for old, new in mapping.items():
                for (sid,) in db.execute("SELECT id FROM sessions WHERE species=?", (old,)).fetchall():
                    db.execute("UPDATE sessions SET species=?, rev=? WHERE id=?", (new, self._next_rev(db), sid))
                    changed += 1
        return changed

    def since(self, rev, person="me"):
        with self.lock:
            rows = self.db.execute("SELECT * FROM sessions WHERE rev > ? AND person=? ORDER BY rev", (rev, person)).fetchall()
        return [dict(r) for r in rows]

    def sessions(self, include_deleted=False, person="me"):
        query = "SELECT * FROM sessions WHERE person=?" + ("" if include_deleted else " AND deleted=0") + " ORDER BY start"
        with self.lock:
            return [dict(r) for r in self.db.execute(query, (person,)).fetchall()]

    def sessions_of(self, people):
        """Everyone's sessions in `people`, for group ponds and leaderboards."""
        people = list(people)
        if not people:
            return []
        marks = ",".join("?" * len(people))
        with self.lock:
            return [dict(r) for r in self.db.execute(f"SELECT * FROM sessions WHERE deleted=0 AND person IN ({marks}) ORDER BY start", people)]

    def focused_minutes(self, person="me"):
        with self.lock:
            row = self.db.execute("SELECT COALESCE(SUM(minutes), 0) FROM sessions WHERE deleted=0 AND status='done' AND person=?", (person,)).fetchone()
        return row[0]

    def set_room(self, sid, room):
        """Mark a session as done together, in the room `room`."""
        with self.tx() as db:
            db.execute("UPDATE sessions SET room=?, rev=? WHERE id=?", (room, self._next_rev(db), sid))

    def timers(self):
        """Everyone's running timer, by person."""
        with self.lock:
            rows = self.db.execute("SELECT key, value FROM meta WHERE key='timer' OR key LIKE 'timer:%'").fetchall()
        out = {}
        for row in rows:
            t = json.loads(row["value"])
            if t:
                out["me" if row["key"] == "timer" else row["key"][6:]] = t
        return out

    # ── devices ──────────────────────────────────────────────────────────────
    def add_device(self, device_id, token_hash, name, now, ip, person="me"):
        with self.tx() as db:
            db.execute("INSERT INTO devices(id, token_hash, name, created, last_seen, last_ip, person) VALUES(?,?,?,?,?,?,?)",
                       (device_id, token_hash, name, now, now, ip, person))

    def device_by_token(self, token_hash):
        with self.lock:
            row = self.db.execute("SELECT * FROM devices WHERE token_hash=?", (token_hash,)).fetchone()
        return dict(row) if row else None

    def touch_device(self, device_id, now, ip):
        with self.tx() as db:
            db.execute("UPDATE devices SET last_seen=?, last_ip=? WHERE id=?", (now, ip, device_id))

    def devices(self, person="me"):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT id, name, created, last_seen, last_ip, person FROM devices WHERE person=? ORDER BY last_seen DESC", (person,))]

    def rename_device(self, device_id, name, person="me"):
        with self.tx() as db:
            return db.execute("UPDATE devices SET name=? WHERE id=? AND person=?", (name, device_id, person)).rowcount > 0

    def remove_device(self, device_id, person="me"):
        with self.tx() as db:
            if not db.execute("DELETE FROM devices WHERE id=? AND person=?", (device_id, person)).rowcount:
                return False
            db.execute("DELETE FROM push WHERE device_id=?", (device_id,))
            return True

    def remove_all_devices(self, person="me"):
        with self.tx() as db:
            db.execute("DELETE FROM push WHERE person=?", (person,))
            db.execute("DELETE FROM devices WHERE person=?", (person,))

    # ── push subscriptions ───────────────────────────────────────────────────
    def add_push(self, endpoint, p256dh, auth, origin, device_id, now, person="me"):
        with self.tx() as db:
            db.execute("INSERT OR REPLACE INTO push(endpoint, p256dh, auth, origin, device_id, created, failures, person) VALUES(?,?,?,?,?,?,0,?)",
                       (endpoint, p256dh, auth, origin, device_id, now, person))

    def remove_push(self, endpoint, person=None):
        """A push subscription gone: one of `person`'s, or (from the push service) whoever's it was."""
        with self.tx() as db:
            if person is None:
                db.execute("DELETE FROM push WHERE endpoint=?", (endpoint,))
            else:
                db.execute("DELETE FROM push WHERE endpoint=? AND person=?", (endpoint, person))

    def pushes(self, device_id=None, person="me"):
        with self.lock:
            if device_id is None:
                rows = self.db.execute("SELECT * FROM push WHERE person=?", (person,)).fetchall()
            else:
                rows = self.db.execute("SELECT * FROM push WHERE device_id=?", (device_id,)).fetchall()
        return [dict(r) for r in rows]

    def push_result(self, endpoint, ok):
        with self.tx() as db:
            if ok:
                db.execute("UPDATE push SET failures=0 WHERE endpoint=?", (endpoint,))
            else:
                db.execute("UPDATE push SET failures=failures+1 WHERE endpoint=?", (endpoint,))
                db.execute("DELETE FROM push WHERE endpoint=? AND failures >= 5", (endpoint,))

    # ── people and groups ────────────────────────────────────────────────────
    def person(self, pid):
        with self.lock:
            row = self.db.execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None

    def people(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM people ORDER BY created")]

    def save_person(self, person):
        with self.tx() as db:
            db.execute("INSERT INTO people(id, name, color, mark, created, updated) VALUES(:id, :name, :color, :mark, :created, :updated) "
                       "ON CONFLICT(id) DO UPDATE SET name=excluded.name, color=excluded.color, mark=excluded.mark, updated=excluded.updated",
                       person)

    def remove_person(self, pid):
        """Takes away someone's access: their devices, groups and invites. Their ducks stay in the
        group ponds they were part of."""
        with self.tx() as db:
            db.execute("DELETE FROM push WHERE person=?", (pid,))
            db.execute("DELETE FROM devices WHERE person=?", (pid,))
            db.execute("DELETE FROM members WHERE person=?", (pid,))
            db.execute("DELETE FROM invites WHERE person=?", (pid,))
            return db.execute("DELETE FROM people WHERE id=?", (pid,)).rowcount > 0

    def groups(self):
        with self.lock:
            groups = [dict(r) for r in self.db.execute("SELECT * FROM groups ORDER BY created")]
            for g in groups:
                g["members"] = [r[0] for r in self.db.execute("SELECT person FROM members WHERE grp=? ORDER BY joined", (g["id"],))]
        return groups

    def save_group(self, group):
        with self.tx() as db:
            db.execute("INSERT INTO groups(id, name, theme, created) VALUES(:id, :name, :theme, :created) "
                       "ON CONFLICT(id) DO UPDATE SET name=excluded.name, theme=excluded.theme", group)

    def remove_group(self, gid):
        with self.tx() as db:
            db.execute("DELETE FROM members WHERE grp=?", (gid,))
            db.execute("DELETE FROM invites WHERE grp=?", (gid,))
            return db.execute("DELETE FROM groups WHERE id=?", (gid,)).rowcount > 0

    def add_member(self, gid, pid, now):
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO members(grp, person, joined) VALUES(?,?,?)", (gid, pid, now))

    def remove_member(self, gid, pid):
        with self.tx() as db:
            return db.execute("DELETE FROM members WHERE grp=? AND person=?", (gid, pid)).rowcount > 0

    # ── invites ──────────────────────────────────────────────────────────────
    def add_invite(self, invite):
        with self.tx() as db:
            db.execute("INSERT INTO invites(id, code_hash, grp, person, created, expires, uses) "
                       "VALUES(:id, :code_hash, :grp, :person, :created, :expires, :uses)", invite)

    def invites(self, now):
        with self.tx() as db:
            db.execute("DELETE FROM invites WHERE expires <= ? OR uses <= 0", (now,))
            return [dict(r) for r in db.execute("SELECT id, grp, person, created, expires, uses FROM invites ORDER BY created DESC")]

    def find_invite(self, code_hash, now):
        with self.lock:
            row = self.db.execute("SELECT * FROM invites WHERE code_hash=? AND expires > ? AND uses > 0", (code_hash, now)).fetchone()
        return dict(row) if row else None

    def use_invite(self, code_hash, now):
        """The invite for this code, used up once; None if there's no such invite or it ran out."""
        with self.tx() as db:
            row = db.execute("SELECT * FROM invites WHERE code_hash=? AND expires > ? AND uses > 0", (code_hash, now)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE invites SET uses=uses-1 WHERE id=?", (row["id"],))
            return dict(row)

    def remove_invite(self, iid):
        with self.tx() as db:
            return db.execute("DELETE FROM invites WHERE id=?", (iid,)).rowcount > 0

    # ── backups ──────────────────────────────────────────────────────────────
    def backup_to(self, path):
        target = sqlite3.connect(str(path))
        try:
            with self.lock:
                self.db.backup(target)
        finally:
            target.close()
