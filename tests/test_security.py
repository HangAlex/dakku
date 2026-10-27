"""What a friend at the internet door must never be able to do, from the security review."""
import os
import socket
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path

from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from dakku import ec, webpush
from dakku.app import App, now_ms
from dakku.web import Server, make_handler
from tests.test_together import TogetherTest


class Sessions(TogetherTest):
    def test_a_friend_cant_take_a_running_session_by_its_id(self):
        # Mina sees your running session in Together, with its id, and tries to log one under it first
        group = self.group()
        mina = self.friend(group)  # (an invite to the group makes her a member)
        mine = self.start(self.me, minutes=25)
        self.rewind("me", 1)
        self.app._check_timers(now_ms())  # (friends hear of it once it's past its first seconds)
        status, together, _ = mina.call("GET", "/api/together")
        self.assertIn(mine["id"], str(together))  # she can see its id
        now = now_ms()
        status, _, _ = mina.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": {
            "id": mine["id"], "start": now - 60_000, "minutes": 1, "tag": "squat", "updated": now + 60_000}}]})
        self.assertEqual(status, 200)
        self.assertIsNone(self.app.store.get_session(mine["id"]))  # not made
        self.rewind("me", 24)
        self.app._check_timers(now_ms())
        mine_now = [s for s in self.app.store.sessions(person="me") if s["minutes"] == 25]
        self.assertEqual(len(mine_now), 1)  # your duck hatched, in your pond
        self.assertEqual([s["tag"] for s in self.app.store.sessions(person=mina.person)], [])

    def test_a_session_whose_id_was_taken_still_hatches_for_you(self):
        mine = self.start(self.me, minutes=25)
        # (as if someone had got a session in under that id anyway)
        self.app.store.upsert({"id": mine["id"], "start": now_ms() - 60_000, "minutes": 1, "updated": now_ms() + 60_000, "person": "someone"})
        self.rewind("me", 25)
        self.app._check_timers(now_ms())
        self.assertEqual([s["minutes"] for s in self.app.store.sessions(person="me")], [25])
        self.assertEqual(self.app.store.get_session(mine["id"])["person"], "someone")  # theirs stays theirs

    def test_the_store_never_moves_a_session_to_someone_else(self):
        self.app.store.upsert({"id": "abcd1234", "start": now_ms(), "minutes": 5, "updated": 1, "person": "me"})
        self.app.store.upsert({"id": "abcd1234", "start": now_ms(), "minutes": 50, "updated": 2, "person": "mallory"})
        row = self.app.store.get_session("abcd1234")
        self.assertEqual((row["person"], row["minutes"]), ("me", 5))


class TheFriendsDoor(TogetherTest):
    def test_a_friend_never_hears_your_pcs_addresses(self):
        self.app._addresses_cache = (9e18, {"lan": ["http://192.168.1.20:8640"], "tailnet": "http://pc.tail1234.ts.net:8640",
                                            "https": "https://pc.tail1234.ts.net", "friends": "https://pc.example.ts.net:8443"})
        mina = self.friend(self.group())
        status, body, _ = mina.call("GET", "/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(body["server"]["addresses"], {"friends": "https://pc.example.ts.net:8443"})
        self.assertNotIn("192.168", str(body))
        self.assertNotIn("tail1234", str(body))
        status, body, _ = self.me.call("GET", "/api/bootstrap")
        self.assertEqual(body["server"]["addresses"]["https"], "https://pc.tail1234.ts.net")  # you still do

    def test_your_own_sign_in_counts_for_nothing_at_the_friends_door(self):
        status, body, _ = self.me.call("POST", "/api/pair")
        phone = __import__("tests.test_api", fromlist=["Client"]).Client(self.port, host="pc.tail1234.ts.net",
                                                                      extra={"X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https"})
        status, _, _ = phone.call("POST", "/api/login", {"pair": body["code"]})
        self.assertEqual(status, 200)  # your phone, signed in at your door
        door = self.door()
        door.cookie = phone.cookie.replace("dakku=", "dakku_friend=")
        for path in ("/api/bootstrap", "/api/export.json", "/api/devices"):
            self.assertEqual(door.call("GET", path)[0], 401, path)


class Odds(TogetherTest):
    def test_numbers_that_arent_numbers_are_a_bad_request_not_a_crash(self):
        mina = self.friend(self.group())
        conn_body = [("PUT", "/api/settings", '{"goal": Infinity}'), ("PUT", "/api/settings", '{"goal": 1e400}'),
                     ("POST", "/api/sync", '{"ops": [{"op": "upsert", "session": {"id": "abcd1234", "start": 1e400, "minutes": 5}}]}'),
                     ("POST", "/api/sync", '{"ops": [{"op": "upsert", "session": {"id": "abcd1234", "start": %d, "minutes": 5, "updated": 1e400}}]}' % now_ms()),
                     ("POST", "/api/sync", '{"ops": [], "since": NaN}')]
        for method, path, text in conn_body:
            status = self._send_raw(mina, method, path, text)
            self.assertIn(status, (200, 400), (path, text))
        self.assertEqual(mina.call("GET", "/api/sync?since=abc")[0], 400)
        self.assertEqual(mina.call("GET", "/api/sync?since=" + "9" * 40)[0], 200)

    def _send_raw(self, client, method, path, text):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.friends_port, timeout=10)
        conn.request(method, path, text.encode(), {"Host": client.host, **client.extra, "Cookie": client.cookie,
                                                   "X-Dakku": "1", "Content-Type": "application/json"})
        status = conn.getresponse().status
        conn.close()
        return status

    def test_pairing_codes_dont_pile_up(self):
        mina = self.friend(self.group())
        codes = [mina.call("POST", "/api/pair")[1]["code"] for _ in range(50)]
        self.assertLessEqual(sum(1 for c, v in self.app._pairs.items() if v[1] == mina.person), 3)
        phone = self.door()
        self.assertEqual(phone.call("POST", "/api/login", {"pair": codes[-1]})[0], 200)  # the newest still works

    def test_a_guest_sees_the_hosts_clock_not_their_device(self):
        mina = self.friend(self.group())
        mine = self.start(self.me, 60)
        self.rewind("me", 1)
        status, joined, _ = mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})
        self.assertEqual(status, 200, joined)
        host = joined["timer"]["hostTimer"]
        self.assertEqual(host["id"], mine["id"])
        for private in ("device", "source", "deep", "announced", "tag"):
            self.assertNotIn(private, host)


class Notifications(TogetherTest):
    def subscription(self, **change):
        key = webpush.b64u(ec.encode_point(ec.public_key(ec.generate_private_key())))
        sub = {"endpoint": "https://web.push.apple.com/" + os.urandom(6).hex(), "keys": {"p256dh": key, "auth": webpush.b64u(b"0123456789abcdef")}}
        sub.update(change)
        return {"subscription": sub}

    def test_a_subscription_is_the_size_of_a_real_one(self):
        mina = self.friend(self.group())
        self.assertEqual(mina.call("POST", "/api/push/subscribe", self.subscription())[0], 200)
        big = self.subscription()
        big["subscription"]["keys"]["auth"] = webpush.b64u(os.urandom(200_000))
        self.assertEqual(mina.call("POST", "/api/push/subscribe", big)[0], 400)
        self.assertEqual(mina.call("POST", "/api/push/subscribe", self.subscription(endpoint="https://web.push.apple.com/" + "x" * 5000))[0], 400)
        self.assertEqual(mina.call("POST", "/api/push/subscribe", self.subscription(), headers={"Origin": "https://" + "a" * 4000})[0], 400)
        self.assertEqual(len(self.app.store.pushes(person=mina.person)), 1)

    def test_one_per_device_and_ten_per_person(self):
        mina = self.friend(self.group())
        for _ in range(5):
            self.assertEqual(mina.call("POST", "/api/push/subscribe", self.subscription())[0], 200)
        self.assertEqual(len(self.app.store.pushes(person=mina.person)), 1)  # the same phone, again and again
        for n in range(15):
            self.app.store.add_push(f"https://web.push.apple.com/{n}", "k", "a", "https://x", f"device{n}", now_ms() + n, mina.person)
        self.assertEqual(len(self.app.store.pushes(person=mina.person)), 10)

    def test_a_push_service_redirecting_elsewhere_is_not_followed(self):
        hits = []

        class Inside(BaseHTTPRequestHandler):  # something on your network that must never hear from Dakku
            def do_POST(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()

            do_GET = do_POST

            def log_message(self, *args):
                pass

        inside = HTTPServer(("127.0.0.1", 0), Inside)
        target = f"http://127.0.0.1:{inside.server_address[1]}/secret"

        class Redirect(Inside):
            def do_POST(self):
                self.send_response(302)  # (which urllib would follow, as a GET)
                self.send_header("Location", target)
                self.end_headers()

        outside = HTTPServer(("127.0.0.1", 0), Redirect)
        for server in (inside, outside):
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        sub = self.subscription()["subscription"]
        sub = {"endpoint": f"http://127.0.0.1:{outside.server_address[1]}/push", "p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]}
        with mock.patch.object(webpush, "valid_endpoint", lambda e: True):
            status, _ = webpush.send(sub, {"title": "hi"}, self.app.vapid, "https://x")
        self.assertEqual(status, 302)
        self.assertEqual(hits, [])


class SlowSenders(unittest.TestCase):
    """Someone at the friends' door sending a request a byte at a time can't keep a thread for long,
    and a door only serves so many at once."""

    class Door(Server):
        max_connections, headers_in, body_grace, wait_for_slot = 3, 0.6, 0.6, 0.3

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "web").mkdir()
        self.app = App(root / "data", root / "web", anki_url=None, start_threads=False)
        self.door = self.Door(("127.0.0.1", 0), make_handler(self.app, public=True))
        threading.Thread(target=self.door.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.port = self.door.server_address[1]

    def tearDown(self):
        self.door.shutdown()
        self.door.server_close()
        self.app.close()
        self.tmp.cleanup()

    def stalled(self, sent):
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.sendall(sent)
        conn.settimeout(5)
        return conn

    def cut_off_within(self, conn, seconds):
        start = time.monotonic()
        try:
            while conn.recv(4096):
                pass
        except (ConnectionResetError, socket.timeout):
            pass
        self.assertLess(time.monotonic() - start, seconds)

    def test_headers_that_never_finish_are_cut_off(self):
        self.cut_off_within(self.stalled(b"GET /api/health HTTP/1.1\r\nHost: x\r\n"), 2.5)

    def test_a_body_that_trickles_is_cut_off(self):
        conn = self.stalled(b"POST /api/login HTTP/1.1\r\nHost: x\r\nX-Dakku: 1\r\nContent-Length: 30000\r\n\r\n{")
        self.cut_off_within(conn, 3)

    def test_a_door_serves_so_many_at_once(self):
        held = [self.stalled(b"GET /api/health HTTP/1.1\r\n") for _ in range(3)]
        time.sleep(0.1)
        turned_away = self.stalled(b"GET /api/health HTTP/1.0\r\nHost: x\r\n\r\n")
        self.assertEqual(turned_away.recv(4096), b"")  # no thread for it: closed, unanswered
        for conn in held:
            self.cut_off_within(conn, 2.5)
        time.sleep(0.6)
        answered = self.stalled(b"GET /api/health HTTP/1.0\r\nHost: x\r\n\r\n")
        self.assertIn(b"200", answered.recv(4096))  # once they're gone, a door serves again


class LiveUpdates(TogetherTest):
    def test_a_page_thats_gone_lets_go_of_its_connection_at_once(self):
        mina = self.friend(self.group())
        conn = socket.create_connection(("127.0.0.1", self.friends_port))
        conn.sendall(f"GET /api/events HTTP/1.1\r\nHost: {mina.host}\r\nCookie: {mina.cookie}\r\n"
                     "X-Forwarded-For: 203.0.113.9\r\nX-Forwarded-Proto: https\r\n\r\n".encode())
        conn.settimeout(5)
        got = b""
        while b"retry:" not in got:
            got += conn.recv(4096)
        self.assertEqual(len(self.app._clients), 1)
        conn.close()  # the page closes (or the phone locks)
        for _ in range(30):
            if not self.app._clients:
                break
            time.sleep(0.1)
        self.assertEqual(self.app._clients, {})  # within a second or two, not at the next heartbeat


class Files(unittest.TestCase):
    def test_the_data_and_its_backups_are_only_yours(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            (root / "backups").mkdir(mode=0o775)
            (root / "backups" / "mori-2026-01-01.json").write_text("{}")  # an old one, readable by anyone
            os.chmod(root / "backups" / "mori-2026-01-01.json", 0o644)
            app = App(root / "data", root / "web", backup_dir=root / "backups", anki_url=None, start_threads=False)
            try:
                self.assertEqual(app.backup(force=True) is not None, True)
                mode = lambda p: stat.S_IMODE(p.stat().st_mode)  # noqa: E731
                self.assertEqual(mode(root / "data"), 0o700)
                self.assertEqual(mode(root / "backups"), 0o700)
                for path in [*(root / "backups").iterdir(), *(p for p in (root / "data").iterdir() if p.is_file())]:
                    self.assertEqual(mode(path), 0o600, path.name)
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
