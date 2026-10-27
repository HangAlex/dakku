"""Dakku's server, exercised over real HTTP with a throwaway data folder."""
import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from mori import ec, logic, webpush
from mori.app import LIVE_PER_PERSON, MINUTE, ApiError, App, Ctx, now_ms
from mori.web import Server, make_handler


class Client:
    def __init__(self, port, host="127.0.0.1", extra=None):
        self.port, self.host, self.extra, self.cookie = port, host, dict(extra or {}), None

    def call(self, method, path, body=None, headers=None, csrf=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"{self.host}:{self.port}" if ":" not in self.host else self.host, **self.extra, **(headers or {})}
        if self.cookie:
            h["Cookie"] = self.cookie
        if method not in ("GET", "HEAD") and csrf:
            h["X-Mori"] = "1"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        conn.request(method, path, data, h)
        res = conn.getresponse()
        raw = res.read()
        cookie = res.getheader("Set-Cookie")
        if cookie and cookie.startswith(("mori=", "mori_friend=")) and "Max-Age=0" not in cookie:
            self.cookie = cookie.split(";")[0]
        conn.close()
        try:
            payload = json.loads(raw) if raw and res.getheader("Content-Type", "").startswith("application/json") else raw
        except ValueError:
            payload = raw
        return res.status, payload, res


class MoriTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        web = root / "web"
        web.mkdir()
        (web / "index.html").write_text("<!doctype html><title>Dakku</title>" + "x" * 2000)
        (web / "sw.js").write_text("const BUILD = '__BUILD__'; self.addEventListener('fetch', () => {});")
        self.app = App(root / "data", web, backup_dir=root / "backups", anki_url=None, start_threads=False)
        self.server = Server(("127.0.0.1", 0), make_handler(self.app))
        self.port = self.server.server_address[1]
        self.app.port = self.port
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.local = Client(self.port)
        self.phone = Client(self.port, host="my-pc.example.ts.net", extra={"X-Forwarded-For": "100.64.0.7", "X-Forwarded-Proto": "https"})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.close()
        self.tmp.cleanup()

    def sign_in_phone(self):
        status, body, _ = self.phone.call("POST", "/api/login", {"passcode": self.app.passcode_plain(), "name": "talon"})
        self.assertEqual(status, 200, body)
        return body


class Trust(MoriTest):
    def test_this_pc_is_trusted(self):
        status, body, _ = self.local.call("GET", "/api/whoami")
        self.assertEqual(status, 200)
        self.assertTrue(body["trusted"])
        self.assertEqual(self.local.call("GET", "/api/bootstrap")[0], 200)

    def test_proxied_requests_are_not_trusted(self):
        for extra in ({"X-Forwarded-For": "100.1.2.3"}, {"Tailscale-User-Login": "someone@example.com"}, {"X-Forwarded-Proto": "https"}):
            client = Client(self.port, extra=extra)
            self.assertFalse(client.call("GET", "/api/whoami")[1]["trusted"], extra)
            self.assertEqual(client.call("GET", "/api/bootstrap")[0], 401, extra)

    def test_foreign_host_names_are_not_trusted(self):  # e.g. DNS rebinding
        client = Client(self.port, host="evil.example")
        self.assertFalse(client.call("GET", "/api/whoami")[1]["trusted"])
        self.assertEqual(client.call("GET", "/api/sync")[0], 401)

    def test_writes_need_the_header(self):
        status, body, _ = self.local.call("POST", "/api/timer", {"action": "start"}, csrf=False)
        self.assertEqual(status, 403)

    def test_passcode_only_on_this_pc(self):
        self.assertEqual(self.local.call("GET", "/api/passcode")[1]["passcode"], self.app.passcode_plain())
        self.sign_in_phone()
        self.assertEqual(self.phone.call("GET", "/api/passcode")[0], 403)


class SignIn(MoriTest):
    def test_wrong_then_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.phone.call("POST", "/api/login", {"passcode": "nope nope"})[0], 401)
        status, body, res = self.phone.call("POST", "/api/login", {"passcode": self.app.passcode_plain()})
        self.assertEqual(status, 429)
        self.assertTrue(res.getheader("Retry-After"))

    def test_sign_in_is_forgiving_and_remembered(self):
        messy = "  " + self.app.passcode_plain().upper().replace("-", " ") + " "
        status, body, res = self.phone.call("POST", "/api/login", {"passcode": messy, "name": "talon"})
        self.assertEqual(status, 200, body)
        cookie = res.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)  # came through the https proxy
        status, boot, _ = self.phone.call("GET", "/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(boot["me"]["device"]["name"], "talon")
        self.assertFalse(boot["me"]["trusted"])

    def test_signing_out_a_device_locks_it_out(self):
        device = self.sign_in_phone()["device"]
        self.assertEqual(self.local.call("DELETE", f"/api/devices/{device['id']}")[0], 200)
        self.assertEqual(self.phone.call("GET", "/api/bootstrap")[0], 401)

    def test_changing_the_passcode(self):
        self.sign_in_phone()
        status, body, _ = self.phone.call("POST", "/api/passcode", {"current": "wrong words here", "next": ""})
        self.assertEqual(status, 401)
        status, body, _ = self.local.call("POST", "/api/passcode", {"next": "kumo yama kawa umi", "signOutOthers": True})
        self.assertEqual(body["passcode"], "kumo-yama-kawa-umi")
        self.assertEqual(self.phone.call("GET", "/api/bootstrap")[0], 401)  # signed out
        self.assertEqual(self.phone.call("POST", "/api/login", {"passcode": "Kumo-Yama Kawa umi"})[0], 200)

    def test_your_phone_cant_make_pairing_codes(self):
        self.sign_in_phone()
        self.assertEqual(self.phone.call("POST", "/api/pair")[0], 403)

    def test_pairing_code_works_once(self):
        self.assertEqual(self.phone.call("POST", "/api/pair")[0], 401)  # only the PC can make one
        status, pair, _ = self.local.call("POST", "/api/pair")
        self.assertEqual(status, 200)
        self.assertRegex(pair["code"], r"^\d{6}$")
        spaced = pair["code"][:3] + " " + pair["code"][3:]
        status, body, _ = self.phone.call("POST", "/api/login", {"passcode": spaced, "name": "talon"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.phone.call("GET", "/api/bootstrap")[0], 200)
        other = Client(self.port, host="my-pc.example.ts.net", extra={"X-Forwarded-For": "100.1.1.1"})
        status, body, _ = other.call("POST", "/api/login", {"pair": pair["code"]})
        self.assertEqual(status, 401)  # already used
        self.assertIn("pairing code", body["error"])

    def test_pairing_codes_expire(self):
        code = self.app.new_pair_code()["code"]
        self.app._pairs[code] = (time.time() - 1, "me")
        self.assertEqual(self.phone.call("POST", "/api/login", {"pair": code})[0], 401)


class Timer(MoriTest):
    def start(self, client=None, **body):
        status, data, _ = (client or self.local).call("POST", "/api/timer", {"action": "start", "minutes": 25, **body})
        self.assertEqual(status, 200, data)
        return data["timer"]

    def age(self, ms):
        """Pretend the running timer started `ms` earlier."""
        t = self.app.store.get("timer")
        t["startedAt"] -= ms
        if t["runFrom"] is not None:
            t["runFrom"] -= ms
        self.app.store.set("timer", t)

    def test_start_pause_resume_finish(self):
        t = self.start(tag="CCNA", species="shiro")
        self.assertTrue(t["running"])
        self.assertEqual(t["remaining"], 25 * MINUTE)
        self.age(10 * MINUTE)
        paused = self.local.call("POST", "/api/timer", {"action": "pause"})[1]["timer"]
        self.assertFalse(paused["running"])
        time.sleep(0.05)
        again = self.local.call("GET", "/api/timer")[1]["timer"]
        self.assertEqual(again["elapsed"], paused["elapsed"])
        self.local.call("POST", "/api/timer", {"action": "resume"})
        done = self.local.call("POST", "/api/timer", {"action": "finish"})[1]
        self.assertIsNone(done["timer"])
        self.assertEqual(done["session"]["id"], t["id"])  # the timer's id becomes the session's id
        self.assertEqual(done["session"]["minutes"], 10)
        self.assertEqual(done["session"]["status"], "done")

    def test_one_timer_for_all_devices(self):
        self.start()
        self.sign_in_phone()
        status, body, _ = self.phone.call("POST", "/api/timer", {"action": "start", "minutes": 45})
        self.assertEqual(status, 409)
        self.assertEqual(body["timer"]["planned"], 25 * MINUTE)

    def test_server_finishes_it_by_itself(self):
        t = self.start(minutes=25)
        self.age(26 * MINUTE)
        self.app._check_timers(now_ms())
        self.assertIsNone(self.app.store.get("timer"))
        logged = self.app.store.get_session(t["id"])
        self.assertEqual((logged["minutes"], logged["status"]), (25, "done"))

    def test_giving_up_leaves_a_cold_egg(self):
        self.start()
        self.local.call("POST", "/api/timer", {"action": "cancel"})
        self.assertEqual(self.app.store.sessions(), [])  # under a minute: nothing to keep
        t = self.start()
        self.age(7 * MINUTE)
        session = self.local.call("POST", "/api/timer", {"action": "cancel", "reason": "left"})[1]["session"]
        self.assertEqual((session["status"], session["minutes"], session["id"]), ("withered", 7, t["id"]))
        self.assertIn("deep focus", session["note"])
        self.assertEqual(self.app.summary()["today"], 0)  # cold eggs don't count

    def test_stopwatch(self):
        self.start(mode="stopwatch")
        self.age(42 * MINUTE)
        session = self.local.call("POST", "/api/timer", {"action": "finish"})[1]["session"]
        self.assertEqual(session["minutes"], 42)

    def test_homepage_id_and_offline_start(self):
        t = self.start(id="genkanTimer01", source="genkan", startedAt=now_ms() - 5 * MINUTE)
        self.assertEqual((t["id"], t["source"]), ("genkanTimer01", "genkan"))
        self.assertGreaterEqual(t["elapsed"], 5 * MINUTE - 1000)
        self.local.call("POST", "/api/timer", {"action": "cancel"})
        # Already ran out while offline: logged straight away.
        status, body, _ = self.local.call("POST", "/api/timer", {"action": "start", "minutes": 15, "startedAt": now_ms() - 20 * MINUTE})
        self.assertIsNone(body["timer"])
        self.assertEqual(body["session"]["minutes"], 15)

    def test_a_device_that_went_offline_takes_its_timer_along(self):
        t = self.start()
        self.assertEqual(self.local.call("POST", "/api/timer", {"action": "drop", "id": "someOtherId"})[0], 200)
        self.assertIsNotNone(self.app.store.get("timer"))  # a different timer is left alone
        self.local.call("POST", "/api/timer", {"action": "drop", "id": t["id"]})
        self.assertIsNone(self.app.store.get("timer"))
        self.assertEqual(self.app.store.sessions(), [])  # the device logs it itself when it finishes

    def test_handing_back_a_paused_offline_timer(self):
        status, body, _ = self.local.call("POST", "/api/timer", {"action": "start", "id": "phoneTimer01", "minutes": 25,
                                                                 "startedAt": now_ms() - 30 * MINUTE, "elapsed": 10 * MINUTE, "running": False})
        t = body["timer"]
        self.assertEqual((t["id"], t["elapsed"], t["running"]), ("phoneTimer01", 10 * MINUTE, False))
        self.assertEqual(t["remaining"], 15 * MINUTE)
        # elapsed can't be more than the time since it started
        self.local.call("POST", "/api/timer", {"action": "drop", "id": "phoneTimer01"})
        status, body, _ = self.local.call("POST", "/api/timer", {"action": "start", "minutes": 25, "startedAt": now_ms() - 5 * MINUTE,
                                                                 "elapsed": 60 * MINUTE, "running": True})
        self.assertLessEqual(body["timer"]["elapsed"], 5 * MINUTE + 1000)

    def test_new_tags_are_remembered(self):
        self.start(tag="Subnetting")
        self.assertIn("Subnetting", [t["name"] for t in self.app.settings()["tags"]])


class Sync(MoriTest):
    def test_round_trip(self):
        base = self.local.call("GET", "/api/sync?since=0")[1]
        self.assertEqual(base["sessions"], [])
        cursor = base["cursor"]
        ops = [{"op": "upsert", "session": {"id": "s0000001", "start": now_ms() - 3600_000, "minutes": 30, "tag": "CCNA", "source": "genkan", "updated": now_ms()}}]
        pulled = self.local.call("POST", "/api/sync", {"since": cursor, "ops": ops})[1]
        self.assertEqual(len(pulled["sessions"]), 1)
        first = pulled["sessions"][0]
        self.assertIn(first["species"], logic.species())  # the homepage doesn't pick ducks; the server does
        # The homepage re-sends it without a species: the duck stays the same.
        again = {"op": "upsert", "session": {"id": "s0000001", "minutes": 30, "tag": "CCNA", "updated": now_ms() + 5}}
        after = self.local.call("POST", "/api/sync", {"since": pulled["cursor"], "ops": [again]})[1]
        self.assertEqual(after["sessions"][0]["species"], first["species"])
        # An older edit loses to a newer one.
        stale = {"op": "upsert", "session": {"id": "s0000001", "minutes": 99, "updated": 1}}
        self.local.call("POST", "/api/sync", {"since": 0, "ops": [stale]})
        self.assertEqual(self.app.store.get_session("s0000001")["minutes"], 30)
        # Deletes travel as tombstones.
        gone = self.local.call("POST", "/api/sync", {"since": after["cursor"], "ops": [{"op": "delete", "id": "s0000001", "updated": now_ms() + 10}]})[1]
        self.assertTrue(gone["sessions"][0]["deleted"])
        self.assertEqual(self.app.store.sessions(), [])

    def test_bad_input_is_refused(self):
        for session in ({"id": "x", "start": now_ms(), "minutes": 5}, {"id": "okay1234", "start": 5, "minutes": 5},
                        {"id": "okay1234", "start": now_ms(), "minutes": 5000}):
            status, body, _ = self.local.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": session}]})
            self.assertEqual(status, 400, session)

    def test_settings_are_checked(self):
        s = self.local.call("PUT", "/api/settings", {"goal": 9999, "tags": [{"name": "CCNA"}, {"name": "ccna"}, {"name": "Anki", "color": "red"}],
                                                      "theme": "nope", "reminder": {"enabled": True, "time": "25:00"}})[1]["settings"]
        self.assertEqual(s["goal"], 600)
        self.assertEqual([t["name"] for t in s["tags"]], ["CCNA", "Anki"])
        self.assertTrue(s["tags"][1]["color"].startswith("#"))
        self.assertEqual(s["theme"], "ai")
        self.assertEqual(s["reminder"], {"enabled": True, "time": "20:00", "weekdaysOnly": True})

    def test_new_settings_are_checked(self):
        s = self.local.call("PUT", "/api/settings", {"theme": "halloween", "pondTheme": "christmas", "weeklyRecap": False,
                                                      "decor": ["koi", "nope", "torii", "koi"]})[1]["settings"]
        self.assertEqual((s["theme"], s["pondTheme"], s["weeklyRecap"]), ("halloween", "christmas", False))
        self.assertEqual(s["decor"], ["torii", "koi"])  # known ones only, once each, in their own order
        self.assertEqual(self.local.call("PUT", "/api/settings", {"decor": "torii"})[1]["settings"]["decor"], ["torii", "koi"])

    def test_sunday_recap(self):
        tz = logic.zone(self.app.settings()["timeZone"])
        at = lambda day, hour, minute=0: int(datetime(2026, 10, day, hour, minute, tzinfo=tz).timestamp() * 1000)  # noqa: E731
        ops = [{"op": "upsert", "session": {"id": f"w000000{i}", "start": start, "minutes": m, "tag": "CCNA", "updated": now_ms()}}
               for i, (start, m) in enumerate([(at(21, 10), 60), (at(21, 14), 30), (at(23, 9), 45), (at(18, 9), 50)])]
        self.local.call("POST", "/api/sync", {"since": 0, "ops": ops})
        sunday = at(25, 19, 30)  # Sun 25 Oct 2026, 7:30 in the evening
        self.assertEqual(self.app.recap(now=sunday), "This week: 2h 15m and 3 ducks. Best day: Wednesday, 1h 30m.")
        told = []
        self.app.notify = lambda payload, **kw: told.append(payload)
        self.app.store.pushes = lambda device_id=None, person="me": [{"endpoint": "x"}]
        self.app._check_recaps(at(25, 18, 50))  # not yet
        self.app._check_recaps(sunday)
        self.app._check_recaps(sunday + 60_000)  # once a week
        self.assertEqual([p["body"] for p in told], [self.app.recap(now=sunday)])
        self.assertEqual(told[0]["url"], "/#stats")
        self.local.call("PUT", "/api/settings", {"weeklyRecap": False})
        self.app._check_recaps(sunday + 7 * 86_400_000)
        self.assertEqual(len(told), 1)

    def test_import_a_genkan_backup(self):
        backup = {"app": "genkan", "study": {"goal": 30, "sessions": [
            {"id": "g1abcdef", "start": now_ms() - 86_400_000, "minutes": 25, "label": "CCNA"},
            {"id": "g2abcdef", "start": now_ms() - 3600_000, "minutes": 15, "label": "Anki", "manual": True}]}}
        body = self.local.call("POST", "/api/import", backup)[1]
        self.assertEqual(body["imported"], 2)
        self.assertEqual(sorted(s["minutes"] for s in self.app.store.sessions()), [15, 25])
        csv_text = self.local.call("GET", "/api/export.csv")[1].decode("utf-8-sig")
        self.assertTrue(csv_text.startswith("date,start,minutes,tag,duck,status,source,note,id"))
        self.assertEqual(len(csv_text.strip().splitlines()), 3)

    def test_live_updates(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/events", headers={"Host": f"127.0.0.1:{self.port}"})
        res = conn.getresponse()
        self.assertEqual(res.getheader("Content-Type"), "text/event-stream; charset=utf-8")
        self.assertEqual(res.fp.readline(), b"retry: 4000\n")
        res.fp.readline()
        threading.Timer(0.2, lambda: self.local.call("POST", "/api/timer", {"action": "start", "minutes": 25})).start()
        self.assertEqual(res.fp.readline(), b"event: change\n")
        data = json.loads(res.fp.readline()[len(b"data: "):])
        self.assertEqual(data["timer"]["planned"], 25 * MINUTE)
        conn.close()


class Files(MoriTest):
    def test_app_files(self):
        status, body, res = self.phone.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", res.getheader("Content-Security-Policy"))
        self.assertEqual(self.phone.call("GET", "/forest")[0], 200)  # app pages fall back to index.html
        etag = res.getheader("ETag")
        self.assertEqual(self.phone.call("GET", "/", headers={"If-None-Match": etag})[0], 304)
        gz = self.phone.call("GET", "/", headers={"Accept-Encoding": "gzip"})[2]
        self.assertEqual(gz.getheader("Content-Encoding"), "gzip")
        status, sw, res = self.phone.call("GET", "/sw.js")
        self.assertEqual(res.getheader("Service-Worker-Allowed"), "/")
        self.assertNotIn(b"__BUILD__", sw)  # stamped with a fingerprint of the app's files
        (Path(self.tmp.name) / "web" / "index.html").write_text("<!doctype html><title>Dakku 2</title>")
        self.assertNotEqual(self.phone.call("GET", "/sw.js")[1], sw)  # so an app update reaches phones

    def test_dropped_connections_are_not_errors(self):
        import contextlib, io, socket, struct
        noise = io.StringIO()
        with contextlib.redirect_stderr(noise):
            sock = socket.create_connection(("127.0.0.1", self.port))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            sock.send(b"GET /api/health HTTP/1.1\r\nHo")  # a phone that went to sleep mid-request
            sock.close()  # closing with linger 0 resets the connection
            time.sleep(0.3)
            self.assertEqual(self.phone.call("GET", "/api/health")[0], 200)
        self.assertNotIn("Traceback", noise.getvalue())

    def test_no_escaping_the_web_folder(self):
        for path in ("/../mori/app.py", "/%2e%2e/data/passcode.txt", "/../data/passcode.txt", "/missing.js"):
            self.assertEqual(self.phone.call("GET", path)[0], 404, path)


class Push(MoriTest):
    def test_subscriptions_are_checked(self):
        self.sign_in_phone()
        ua = ec.generate_private_key()
        good = {"endpoint": "https://web.push.apple.com/QGuQ", "keys": {"p256dh": webpush.b64u(ec.encode_point(ec.public_key(ua))),
                                                                         "auth": webpush.b64u(b"0123456789abcdef")}}
        self.assertEqual(self.phone.call("POST", "/api/push/subscribe", {"subscription": dict(good, endpoint="https://evil.example/x")})[0], 400)
        self.assertEqual(self.phone.call("POST", "/api/push/subscribe", {"subscription": dict(good, keys={"p256dh": "AAAA", "auth": "AAAA"})})[0], 400)
        status, body, _ = self.phone.call("POST", "/api/push/subscribe", {"subscription": good}, headers={"Origin": "https://my-pc.example.ts.net"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.app.store.pushes()[0]["origin"], "https://my-pc.example.ts.net")
        plain = Client(self.port, host="192.168.1.20")  # plain http on the home network
        plain.cookie = self.phone.cookie
        self.assertEqual(plain.call("POST", "/api/push/subscribe", {"subscription": good})[0], 400)


class Limits(MoriTest):
    def raw(self, data, port=None):
        s = socket.create_connection(("127.0.0.1", port or self.port))
        s.settimeout(5)
        s.sendall(data)
        try:
            return s.recv(200)
        finally:
            s.close()

    def test_bad_and_big_bodies(self):
        # a negative length used to keep the server reading (and holding it all) for as long as the sender kept sending
        self.assertIn(b" 400 ", self.raw(b"POST /api/login HTTP/1.0\r\nHost: x\r\nX-Mori: 1\r\nContent-Length: -1\r\n\r\n" + b"x" * 4096))
        self.assertIn(b" 400 ", self.raw(b"POST /api/login HTTP/1.0\r\nHost: x\r\nX-Mori: 1\r\nContent-Length: lots\r\n\r\n"))
        stranger = Client(self.port, host="phone.example")
        self.assertEqual(stranger.call("POST", "/api/login", {"passcode": "x" * 100_000})[0], 413)  # before signing in: small
        self.assertEqual(self.local.call("POST", "/api/sync", {"ops": [], "since": 0, "pad": "x" * 100_000})[0], 200)  # signed in: fine

    def test_idle_connections_are_dropped(self):
        handler = make_handler(self.app)
        handler.timeout = 0.5
        server = Server(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        try:
            started = time.time()
            self.raw(b"GET /api/health HTTP/1.0\r\n", server.server_address[1])  # never finishes its request
            self.assertLess(time.time() - started, 3)
        finally:
            server.shutdown()
            server.server_close()

    def test_only_your_own_push_subscription_can_be_removed(self):
        self.app.store.add_push("https://web.push.apple.com/mine", "k", "a", "https://x", "local", now_ms(), "me")
        self.app.store.save_person({"id": "friend01", "name": "Kai", "color": "#E9A100", "mark": "K", "created": 0, "updated": 0})
        token, _ = self.app._new_device(Ctx(ip="203.0.113.9"), "friend01", "Kai's phone")
        friend = Client(self.port, host="phone.example", extra={"Authorization": f"Bearer {token}"})
        self.assertEqual(friend.call("POST", "/api/push/unsubscribe", {"endpoint": "https://web.push.apple.com/mine"})[0], 200)
        self.assertEqual(len(self.app.store.pushes()), 1)  # still yours
        self.local.call("POST", "/api/push/unsubscribe", {"endpoint": "https://web.push.apple.com/mine"})
        self.assertEqual(self.app.store.pushes(), [])

    def test_live_updates_are_capped(self):
        held = [self.app.subscribe("me") for _ in range(LIVE_PER_PERSON)]
        with self.assertRaises(ApiError) as err:
            self.app.subscribe("me")
        self.assertEqual(err.exception.status, 429)
        self.app.subscribe("friend01")  # someone else's are their own
        self.app.unsubscribe(held.pop())
        self.app.subscribe("me")


class Rules(unittest.TestCase):
    def test_weekday_streak_rule(self):
        # Tue 13 Oct 2026: Mon 12, Fri 9, Thu 8 met; the weekend is empty; Wed 7 fell short.
        by_day = {date(2026, 10, 12): 40, date(2026, 10, 9): 30, date(2026, 10, 8): 45, date(2026, 10, 7): 10}
        self.assertEqual(logic.streaks(by_day, 30, date(2026, 10, 13)), (3, 3))
        by_day[date(2026, 10, 13)] = 30  # today done
        self.assertEqual(logic.streaks(by_day, 30, date(2026, 10, 13)), (4, 4))
        by_day[date(2026, 10, 10)] = 60  # a Saturday session adds a day
        self.assertEqual(logic.streaks(by_day, 30, date(2026, 10, 13))[0], 5)

    def test_streak_freezes(self):
        # Mon 5 to Tue 13 Oct 2026 all met: 7 days in a row earn a freeze, which covers Wed 14
        by_day = {date(2026, 10, 5) + timedelta(days=i): 30 for i in range(9)}
        r = logic.run(by_day, 30, date(2026, 10, 15))
        self.assertEqual((r["current"], r["best"], r["freezes"], r["frozen"]), (9, 9, 0, [date(2026, 10, 14)]))
        # without 7 days first, the same miss breaks it
        short = {d: m for d, m in by_day.items() if d >= date(2026, 10, 8)}
        self.assertEqual(logic.run(short, 30, date(2026, 10, 15))["current"], 0)
        # 28 days earn four, but only two are kept: they cover Tue 29 and Wed 30 Sep, and then there are none
        long = {date(2026, 9, 1) + timedelta(days=i): 30 for i in range(28)}
        r = logic.run(long, 30, date(2026, 10, 1))
        self.assertEqual((r["current"], r["freezes"], len(r["frozen"])), (28, 0, 2))
        self.assertEqual(logic.run(long, 30, date(2026, 10, 2))["current"], 0)  # a third missed weekday breaks it

    def test_every_duck_from_the_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = App(Path(tmp) / "data", Path(tmp) / "web", start_threads=False)
            try:
                self.assertEqual(app.species_for("anyId01", "astro"), "astro")  # no hours needed
                self.assertIn(app.species_for("anyId02"), logic.species())
            finally:
                app.close()



class Backups(MoriTest):
    def test_daily_backup(self):
        day = self.app.backup(force=True)
        folder = Path(self.tmp.name) / "backups"
        self.assertTrue((folder / f"dakku-{day}.db").exists())
        exported = json.loads((folder / f"dakku-{day}.json").read_text())
        self.assertEqual(exported["app"], "mori")  # (the format's name, which imports look for)
        self.assertIsNone(self.app.backup())  # once a day

    def test_old_backups_are_pruned_by_date_whatever_their_name(self):
        folder = Path(self.tmp.name) / "backups"
        folder.mkdir(exist_ok=True)
        for i in range(40):  # from before they were called dakku-…
            (folder / f"mori-2025-{1 + i // 28:02d}-{1 + i % 28:02d}.json").write_text("{}")
        day = self.app.backup(force=True)
        kept = sorted(p.name for p in folder.glob("*.json"))
        self.assertEqual(len(kept), 30)
        self.assertIn(f"dakku-{day}.json", kept)  # the newest stays
        self.assertNotIn("mori-2025-01-01.json", kept)  # the oldest go



class Upgrade(MoriTest):
    def test_trees_from_before_become_ducks(self):
        self.app.store.set("settings", dict(self.app.settings(), species="sakura", theme="washi"))
        self.app.store.upsert({"id": "oldTree01", "start": now_ms() - 24 * 60 * MINUTE, "minutes": 25, "species": "momiji", "updated": now_ms()})
        rev = self.app.store.rev()
        self.app.close()
        self.app = App(Path(self.tmp.name) / "data", Path(self.tmp.name) / "web", start_threads=False)
        self.assertEqual((self.app.settings()["species"], self.app.settings()["theme"]), ("neko", "ai"))
        self.assertEqual(self.app.store.get_session("oldTree01")["species"], "super")
        self.assertGreater(self.app.store.rev(), rev)  # so every device hears about it
        self.assertEqual(logic.kind("ume"), "yukata")  # and old names sent by a stale page are understood


if __name__ == "__main__":
    unittest.main()
