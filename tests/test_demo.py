"""The demo Dakku: made-up ducks, open to anyone, and never your real data."""
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from dakku import __main__ as entry, demo, logic
from dakku.app import App
from dakku.web import Server, make_handler
from tests.test_api import Client


def at(day, hour, minute=0, tz=None):
    """Milliseconds for a local time on `day` (a date) in the demo's time zone."""
    return int(datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).timestamp() * 1000)


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        web = root / "web"
        web.mkdir()
        (web / "index.html").write_text("<!doctype html><title>Dakku</title>")
        self.app = App(root / "demo", web, start_threads=False, demo=True)
        self.tz = logic.zone(self.app.settings()["timeZone"])
        self.server = Server(("127.0.0.1", 0), make_handler(self.app))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        # a phone over Tailscale, which the real Dakku would ask to sign in
        self.phone = Client(self.port, host="my-pc.example.ts.net", extra={"X-Forwarded-For": "100.64.0.7"})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.close()
        self.tmp.cleanup()

    def test_anyone_is_let_in(self):
        me = self.phone.call("GET", "/api/whoami")[1]
        self.assertTrue(me["signedIn"])
        self.assertTrue(me["demo"])
        self.assertFalse(me["trusted"])
        status, body, _ = self.phone.call("GET", "/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertGreater(len(body["sessions"]), 150)
        self.assertTrue(body["anki"]["data"]["byDay"])

    def test_what_the_demo_leaves_out(self):
        for method, path, body in (("POST", "/api/login", {"passcode": "anything"}), ("GET", "/api/passcode", None),
                                   ("POST", "/api/pair", {}), ("POST", "/api/push/subscribe", {}), ("POST", "/api/import", {}),
                                   ("DELETE", "/api/devices/abcdef", None)):
            self.assertEqual(self.phone.call(method, path, body)[0], 403, path)

    def test_it_still_works_like_dakku(self):
        status, body, _ = self.phone.call("POST", "/api/timer", {"action": "start", "id": "trying-it", "minutes": 25})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.phone.call("POST", "/api/timer", {"action": "cancel", "id": "trying-it"})[0], 200)

    def test_a_full_pond_and_a_good_streak(self):
        sessions = self.app.store.sessions()
        self.assertEqual({s["species"] for s in sessions}, set(logic.species()))
        self.assertLessEqual(max(s["start"] + s["minutes"] * 60_000 for s in sessions), int(datetime.now().timestamp() * 1000) + 1000)
        self.assertGreaterEqual(self.app.summary()["streak"], 25)

    def test_friends_to_study_with(self):
        together = self.phone.call("GET", "/api/together")[1]
        self.assertEqual([g["name"] for g in together["groups"]], ["Study club"])
        self.assertEqual({p["name"] for p in together["people"]}, {"You", "Mina", "Kai"})
        group = self.phone.call("GET", "/api/groups/demo-club")[1]
        self.assertGreater(group["stats"]["sessions"], 20)
        self.assertEqual({s["person"] for s in group["pond"]}, {"me", "demo-mina", "demo-kai"})
        self.assertTrue(all(b["total"] > 0 for b in group["board"]))
        if datetime.now(self.tz).hour >= 7:  # someone's studying, and you can join them
            room = together["rooms"][0]
            self.assertIn(room["host"], ("demo-mina", "demo-kai"))
            status, body, _ = self.phone.call("POST", "/api/timer", {"action": "join", "room": room["id"], "species": "king"})
            self.assertEqual(status, 200, body)
            self.assertEqual(body["timer"]["host"], room["host"])

    def test_the_same_ducks_every_time(self):
        self.assertEqual(demo.fill(self.app, int(datetime.now().timestamp() * 1000)), 0)  # nothing new a moment later
        other = App(Path(self.tmp.name) / "again", Path(self.tmp.name) / "web", start_threads=False, demo=True)
        try:
            # (today's early duck, if there is one, is timed from when the demo started, so it can differ)
            mine = {s["id"]: (s["start"], s["minutes"], s["species"]) for s in self.app.store.sessions() if not s["id"].endswith("-early")}
            theirs = {s["id"]: (s["start"], s["minutes"], s["species"]) for s in other.store.sessions() if not s["id"].endswith("-early")}
            self.assertGreater(len(mine), 150)
            self.assertEqual(mine, theirs)
        finally:
            other.close()

    def blank(self):
        """A Dakku with nothing in it yet, to fill as of a moment in the past."""
        app = App(Path(self.tmp.name) / f"blank{id(self)}", Path(self.tmp.name) / "web", start_threads=False)
        self.addCleanup(app.close)
        return app

    def past_day(self, fits):
        day = datetime.now(self.tz).date() - timedelta(days=60)
        while not fits(demo.plan(day, True)):
            day += timedelta(days=1)
        return day

    def test_ducks_hatch_as_the_day_goes_on(self):
        app = self.blank()
        day = self.past_day(lambda p: len(p) >= 2 and p[0][0] < 10 and p[-1][0] >= 12)  # a morning and an afternoon
        planned = demo.plan(day, True)
        demo.fill(app, at(day, 11, 0, self.tz))
        ended = [i for i, p in enumerate(planned) if at(day, p[0], p[1], self.tz) + p[2] * 60_000 <= at(day, 11, 0, self.tz)]
        self.assertTrue(ended)
        for i in range(len(planned)):
            self.assertEqual(app.store.get_session(f"demo-{day.isoformat()}-{i}") is not None, i in ended, i)
        demo.fill(app, at(day, 23, 59, self.tz))
        for i in range(len(planned)):
            self.assertIsNotNone(app.store.get_session(f"demo-{day.isoformat()}-{i}"), i)

    def test_an_early_duck_so_today_isnt_empty(self):
        app = self.blank()
        day = self.past_day(lambda p: p and p[0][0] >= 9)  # nothing finished by 8:30
        demo.fill(app, at(day, 8, 30, self.tz))
        self.assertIsNotNone(app.store.get_session(f"demo-{day.isoformat()}-early"))
        self.assertIsNone(app.store.get_session(f"demo-{day.isoformat()}-0"))


class Startup(unittest.TestCase):
    def test_the_demo_never_opens_your_data(self):
        with mock.patch.object(entry, "App") as fake:
            _, _, port = entry.build(["--demo"], {"DAKKU_DATA": "/home/someone/real-data", "DAKKU_PORT": "8640"})
        kwargs = fake.call_args.kwargs
        self.assertEqual(Path(kwargs["data_dir"]), entry.ROOT / "demo")
        self.assertTrue(kwargs["demo"])
        self.assertNotIn("backup_dir", kwargs)
        self.assertEqual(port, 8642)

    def test_the_real_dakku_is_unchanged(self):
        with mock.patch.object(entry, "App") as fake:
            _, _, port = entry.build([], {"DAKKU_DATA": "/tmp/dakku-data"})
        self.assertEqual(fake.call_args.kwargs["data_dir"], "/tmp/dakku-data")
        self.assertNotIn("demo", fake.call_args.kwargs)
        self.assertEqual(port, 8640)


if __name__ == "__main__":
    unittest.main()
