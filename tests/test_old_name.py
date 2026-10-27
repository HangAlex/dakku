"""Dakku was called Mori before it had its name: everything from then still works, under Dakku's name."""
import http.client
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dakku.app import App, now_ms
from dakku.store import database
from tests.test_api import Client
from tests.test_together import TogetherTest


class SignIns(TogetherTest):
    def raw(self, port, headers, method="GET", path="/api/whoami"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path, b"{}" if method == "POST" else None, headers)
        res = conn.getresponse()
        res.read()
        cookies = res.headers.get_all("Set-Cookie") or []
        conn.close()
        return res.status, cookies

    def test_a_sign_in_from_then_still_works_and_moves_to_the_new_cookie(self):
        status, body, _ = self.me.call("POST", "/api/pair")
        phone = Client(self.port, host="pc.tail1234.ts.net", extra={"X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https"})
        self.assertEqual(phone.call("POST", "/api/login", {"pair": body["code"]})[0], 200)
        token = phone.cookie.split("=", 1)[1]
        status, cookies = self.raw(self.port, {"Host": "pc.tail1234.ts.net", "X-Forwarded-For": "100.64.0.9",
                                               "X-Forwarded-Proto": "https", "Cookie": f"mori={token}"}, path="/api/bootstrap")
        self.assertEqual(status, 200)  # still signed in
        self.assertIn(f"dakku={token}; Path=/; Max-Age=34560000; HttpOnly; SameSite=Lax; Secure", cookies)
        self.assertIn("mori=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax", cookies)

    def test_a_friends_sign_in_from_then_too(self):
        mina = self.friend(self.group())
        token = mina.cookie.split("=", 1)[1]
        status, cookies = self.raw(self.friends_port, {"Host": "pc.example.ts.net:8443", "X-Forwarded-For": "203.0.113.9",
                                                       "X-Forwarded-Proto": "https", "Cookie": f"mori_friend={token}"}, path="/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertTrue(any(c.startswith(f"dakku_friend={token};") for c in cookies), cookies)

    def test_a_made_up_sign_in_from_then_is_nothing(self):
        status, cookies = self.raw(self.friends_port, {"Host": "pc.example.ts.net:8443", "X-Forwarded-For": "203.0.113.9",
                                                       "X-Forwarded-Proto": "https", "Cookie": "mori_friend=nope"}, path="/api/bootstrap")
        self.assertEqual((status, cookies), (401, []))

    def test_signing_out_clears_both(self):
        mina = self.friend(self.group())
        status, _, res = mina.call("POST", "/api/logout")
        self.assertEqual(status, 200)
        self.assertEqual(sorted(c.split("=")[0] for c in res.headers.get_all("Set-Cookie")), ["dakku_friend", "mori_friend"])

    def test_the_genkan_homepage_still_gets_in_with_its_header(self):
        here = {"Host": "127.0.0.1", "Content-Type": "application/json"}
        self.assertEqual(self.raw(self.port, {**here, "X-Mori": "1"}, "POST", "/api/sync")[0], 200)  # what Genkan sends
        self.assertEqual(self.raw(self.port, {**here, "X-Dakku": "1"}, "POST", "/api/sync")[0], 200)
        self.assertEqual(self.raw(self.port, here, "POST", "/api/sync")[0], 403)  # (another website couldn't add either)


class Data(unittest.TestCase):
    def test_the_database_from_then_becomes_dakkus_with_everything_in_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            running, folder = Path(tmp) / "running", Path(tmp) / "data"
            running.mkdir()
            folder.mkdir()
            old = sqlite3.connect(running / "mori.db")
            old.execute("PRAGMA journal_mode=WAL")
            old.execute("PRAGMA wal_autocheckpoint=0")  # (so the changes are still only in the journal)
            old.execute("CREATE TABLE notes (text TEXT)")
            old.execute("INSERT INTO notes VALUES ('kept')")
            old.commit()
            for name in ("mori.db", "mori.db-wal"):  # what's left when a server is stopped mid-run
                (folder / name).write_bytes((running / name).read_bytes())
            old.close()
            self.assertGreater((folder / "mori.db-wal").stat().st_size, 0)
            self.assertEqual(database(folder), folder / "dakku.db")
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["dakku.db"])
            self.assertEqual(sqlite3.connect(folder / "dakku.db").execute("SELECT text FROM notes").fetchall(), [("kept",)])

    def test_its_left_alone_while_something_still_has_it_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            other = sqlite3.connect(folder / "mori.db")
            other.execute("PRAGMA journal_mode=WAL")
            other.execute("CREATE TABLE notes (text TEXT)")
            other.execute("INSERT INTO notes VALUES ('kept')")
            other.commit()
            other.execute("BEGIN")
            other.execute("SELECT * FROM notes").fetchall()  # a reader in the middle of reading
            self.assertEqual(database(folder), folder / "mori.db")
            self.assertTrue((folder / "mori.db").exists())
            other.close()

    def test_sessions_from_then_are_dakkus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            app = App(root / "data", root / "web", anki_url=None, start_threads=False)
            app.store.upsert({"id": "oldOne01", "start": now_ms() - 3_600_000, "minutes": 25, "source": "mori", "updated": now_ms()})
            app.close()
            app = App(root / "data", root / "web", anki_url=None, start_threads=False)
            try:
                self.assertEqual(app.store.get_session("oldOne01")["source"], "dakku")
                app.push({"ops": [{"op": "upsert", "session": {"id": "fromAnOldPage", "start": now_ms() - 60_000, "minutes": 1, "source": "mori"}}]})
                self.assertEqual(app.store.get_session("fromAnOldPage")["source"], "dakku")  # what an older page still says
                self.assertEqual(json.loads(json.dumps(app.export()))["app"], "dakku")
            finally:
                app.close()

    def test_backups_from_then_get_dakkus_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            backups = root / "backups"
            backups.mkdir()
            (backups / "mori-2026-10-25.json").write_text("{}")
            (backups / "mori-2026-10-25.db").write_text("")
            app = App(root / "data", root / "web", backup_dir=backups, anki_url=None, start_threads=False)
            try:
                day = app.backup(force=True)
            finally:
                app.close()
            self.assertEqual(sorted(p.name for p in backups.iterdir()),
                             sorted(["dakku-2026-10-25.db", "dakku-2026-10-25.json", f"dakku-{day}.db", f"dakku-{day}.json"]))


if __name__ == "__main__":
    unittest.main()
