"""How Dakku speaks HTTP: connections kept open between requests, and let go cleanly when it stops."""
import gzip
import http.client
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from dakku.app import App
from dakku.web import Server, make_handler
from tests.test_api import DakkuTest


def response(conn):
    """One whole response from a raw connection: its headers and, by their Content-Length, its body."""
    got = b""
    while b"\r\n\r\n" not in got:
        got += conn.recv(4096)
    head, body = got.split(b"\r\n\r\n", 1)
    length = next((int(line.split(b":")[1]) for line in head.split(b"\r\n") if line.lower().startswith(b"content-length:")), 0)
    while len(body) < length:
        body += conn.recv(4096)
    return head + b"\r\n\r\n" + body


class KeptConnections(DakkuTest):
    def test_one_connection_serves_request_after_request(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        for path in ("/api/health", "/", "/api/whoami", "/sw.js"):
            conn.request("GET", path)
            res = conn.getresponse()
            res.read()
            self.assertEqual(res.status, 200, path)
            self.assertEqual(res.getheader("Connection"), "keep-alive")
            self.assertEqual(res.getheader("Keep-Alive"), f"timeout={int(self.server.headers_in)}")
        self.assertEqual(conn.sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY), 1)  # (the server's side is set too)

    def test_a_304_keeps_the_connection_too(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/")
        res = conn.getresponse()
        res.read()
        conn.request("GET", "/", headers={"If-None-Match": res.getheader("ETag")})
        res = conn.getresponse()
        self.assertEqual((res.status, res.read(), res.getheader("Connection")), (304, b"", "keep-alive"))
        conn.request("GET", "/api/health")
        self.assertEqual(conn.getresponse().status, 200)

    def test_an_http_1_0_client_gets_its_connection_closed(self):
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.sendall(b"GET /api/health HTTP/1.0\r\nHost: x\r\n\r\n")
        conn.settimeout(5)
        got = b""
        while chunk := conn.recv(4096):
            got += chunk
        self.assertIn(b"Connection: close", got)

    def test_a_body_that_was_turned_away_unread_closes_the_connection(self):
        # a signed-out sender may post 64 KB at most: a bigger body is refused before it's read, and would
        # otherwise be taken for the next request on the connection
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/login")
        conn.putheader("Host", "my-pc.example.ts.net")
        conn.putheader("X-Forwarded-For", "100.64.0.7")
        conn.putheader("X-Dakku", "1")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(100_000))
        conn.endheaders()
        res = conn.getresponse()
        res.read()
        self.assertEqual((res.status, res.getheader("Connection")), (413, "close"))

    def test_a_chunked_body_is_asked_for_a_length(self):
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.sendall(b"POST /api/login HTTP/1.1\r\nHost: localhost\r\nX-Dakku: 1\r\nTransfer-Encoding: chunked\r\n\r\n")
        conn.settimeout(5)
        got = conn.recv(4096)
        self.assertIn(b" 411 ", got)
        self.assertIn(b"Connection: close", got)

    def test_live_updates_close_their_connection(self):
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.sendall(b"GET /api/events HTTP/1.1\r\nHost: localhost\r\n\r\n")
        conn.settimeout(5)
        got = b""
        while b"retry:" not in got:
            got += conn.recv(4096)
        self.assertIn(b"Connection: close", got)
        self.assertNotIn(b"Content-Length", got)

    def test_a_name_no_file_could_have_is_not_found(self):
        self.assertEqual(self.phone.call("GET", "/" + "x" * 300 + ".js")[0], 404)  # (too long for any file system)
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.sendall(b"GET /a\x00b.js HTTP/1.1\r\nHost: localhost\r\n\r\n")  # a NUL byte, which no path can hold
        conn.settimeout(5)
        self.assertIn(b" 404 ", conn.recv(4096))

    def test_the_browser_is_told_what_the_page_never_uses(self):
        for path in ("/", "/api/health"):
            res = self.phone.call("GET", path)[2]
            self.assertIn("camera=()", res.getheader("Permissions-Policy"))


class IdleConnections(unittest.TestCase):
    """A kept connection that sends nothing more is let go after HEADERS_IN seconds, like one that never
    sent anything: so idle ones can't hold a door's threads."""

    class Door(Server):
        headers_in = 0.6

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "web").mkdir()
        (root / "web" / "index.html").write_text("<!doctype html>")
        self.app = App(root / "data", root / "web", anki_url=None, start_threads=False)
        self.door = self.Door(("127.0.0.1", 0), make_handler(self.app))
        threading.Thread(target=self.door.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.port = self.door.server_address[1]

    def tearDown(self):
        self.door.shutdown()
        self.door.server_close()
        self.app.close()
        self.tmp.cleanup()

    def open(self, request=b"GET /api/health HTTP/1.1\r\nHost: localhost\r\n\r\n"):
        conn = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(conn.close)
        conn.settimeout(5)
        conn.sendall(request)
        self.assertIn(b" 200 ", response(conn))
        return conn

    def closed_within(self, conn, seconds):
        start = time.monotonic()
        try:
            while conn.recv(4096):
                pass
        except (ConnectionResetError, socket.timeout):
            pass
        self.assertLess(time.monotonic() - start, seconds)

    def test_a_connection_that_falls_silent_after_a_request_is_let_go(self):
        conn = self.open()
        self.closed_within(conn, 2.5)
        for _ in range(20):  # (its thread is finishing)
            if not self.door.busy:
                break
            time.sleep(0.05)
        self.assertEqual(self.door.busy, 0)

    def test_a_request_that_comes_in_time_keeps_it(self):
        conn = self.open()
        time.sleep(0.3)
        conn.sendall(b"GET /api/health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertIn(b" 200 ", response(conn))

    def test_stopping_lets_waiting_connections_go_and_finishes_the_rest(self):
        idle = self.open()
        live = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(live.close)
        live.settimeout(5)
        live.sendall(b"GET /api/events HTTP/1.1\r\nHost: localhost\r\n\r\n")
        got = b""
        while b"retry:" not in got:
            got += live.recv(4096)
        self.assertEqual(self.door.busy, 2)
        self.app.stop()  # what serve() does when told to stop...
        self.door.cut_waiting()
        start = time.monotonic()
        self.assertTrue(self.door.drain(3))  # ...and the door is empty within a moment
        self.assertLess(time.monotonic() - start, 2)
        self.closed_within(idle, 0.5)
        self.closed_within(live, 0.5)


class Compressing(DakkuTest):
    def test_the_apps_files_are_compressed_once_ahead_of_time(self):
        web = Path(self.tmp.name) / "web"
        (web / "app.js").write_text("const APP_BUILD = '__BUILD__';" + "// " + "y" * 3000)
        handler = self.server.RequestHandlerClass
        handler.compressed.warm(self.app)
        kept = {t.name for t in handler.compressed._files}
        self.assertEqual(kept, {"index.html", "app.js"})  # (sw.js is under the size that's worth compressing)
        status, body, res = self.phone.call("GET", "/app.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual((status, res.getheader("Content-Encoding")), (200, "gzip"))
        # a changed file is compressed afresh, and its old version isn't kept
        (web / "app.js").write_text("const APP_BUILD = '__BUILD__';" + "// " + "z" * 3000)
        time.sleep(1.05)  # (the build fingerprint is looked at again after a second)
        status, body, res = self.phone.call("GET", "/app.js", headers={"Accept-Encoding": "gzip"})
        self.assertIn(b"zzz", gzip.decompress(body))
        self.assertEqual(len(handler.compressed._files), 2)
