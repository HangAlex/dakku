"""HTTP for Dakku: the app's files, the JSON API, and live updates (server-sent events).

Who counts as "this PC" (no sign-in needed): a request that arrives on the loopback
interface, addressed to a loopback host name, with no proxy headers. Anything relayed by
Tailscale's https proxy carries forwarding headers, so it must sign in like any phone.

Dakku listens twice. Your door (port 8640) has everything, for you; it's only reachable from
your own devices. The friends' door (port 8643, on this PC only) is what Tailscale Funnel opens
to the internet, so friends can join without Tailscale: it has only what friends need, never
trusts anyone as this PC, and won't take your passcode.
"""
import gzip
import json
import queue
import re
import select
import signal
import socket
import sys
import threading
import time
import traceback
from email.utils import formatdate
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .app import ApiError, Ctx, log

LOOPBACK_IPS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
PROXY_HEADERS = ("X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "Forwarded", "X-Real-IP",
                 "Tailscale-User-Login", "Tailscale-User-Name", "Tailscale-Funnel-Request")
MAX_BODY = 8 * 1024 * 1024  # signed in (an import, a big sync)
MAX_BODY_ANYONE = 64 * 1024  # before signing in: a passcode, a code, a name
IDLE_TIMEOUT = 75  # seconds a read or write may block: so a connection that went quiet can't hold a thread for ever
# A connection is kept open between requests (a page's scripts, pictures and API calls share a few), and waits
# this long for the next one (Keep-Alive says so). Your door, which only your own devices reach, keeps one for
# longer: a phone's next tap then rarely needs a new connection. At the friends' door, on the internet,
# strangers holding connections open would cost it a thread each, so it lets go sooner.
KEEP_ALIVE = 60
KEEP_ALIVE_PUBLIC = 15
STOP_WITHIN = 5  # seconds the requests being served get to finish when Dakku is told to stop
LIVE_BEAT = 20  # seconds between the pings live updates send when nothing's happening (the page starts afresh without them)
# Someone sending a request a byte at a time could still hold a thread for ever, a minute per byte, and
# enough of them would take a door down (the friends' door is on the internet). So a request has to send
# its first line and headers within HEADERS_IN seconds (counted from when the connection opened, or from
# the end of its last request), and its body at BODY_RATE bytes a second at least (after BODY_GRACE
# seconds); and each door serves at most MAX_CONNECTIONS at once, so trouble at the friends' door can't
# reach yours.
HEADERS_IN = KEEP_ALIVE_PUBLIC  # (a Server's headers_in; your door's is KEEP_ALIVE, see serve)
BODY_GRACE, BODY_RATE = 20, 50_000
MAX_CONNECTIONS = 128
COOKIE = "dakku"
# The friends' door signs people in with a cookie of its own: browsers share cookies between ports
# of the same host, and a friend's sign-in must never reach your door (or yours theirs).
FRIENDS_COOKIE = "dakku_friend"
# what those were called before Dakku had its name: a sign-in from then still works, and is moved over
OLD_COOKIES = {COOKIE: "mori", FRIENDS_COOKIE: "mori_friend"}
SIGN_IN_FOR = 34_560_000  # seconds a sign-in lasts: 400 days, as long as browsers allow
# frame-src: the lofi on the Hatch screen plays through YouTube's player (web/lofi.js)
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
       "manifest-src 'self'; worker-src 'self'; frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'; object-src 'none'")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".json": "application/json", ".webmanifest": "application/manifest+json", ".png": "image/png",
        ".svg": "image/svg+xml", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8", ".woff2": "font/woff2",
        ".webp": "image/webp", ".jpg": "image/jpeg"}
COMPRESSIBLE = {".html", ".js", ".css", ".json", ".webmanifest", ".svg", ".txt"}
GZIP_OVER = 1024  # bytes: anything smaller goes as it is
PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"  # (nothing here uses them)
STAMPED = ("sw.js", "app.js")  # served with the fingerprint of the app's files in place of __BUILD__ (see App.build_id)
BUILD_RE = re.compile(r"^[0-9a-f]{6,32}$")

ID = r"([A-Za-z0-9_-]{4,64})"
PID = r"(me|[A-Za-z0-9_-]{4,64})"  # a person: "me" is you
# (method, path pattern, handler name, who may call it, open at the friends' door too).
# "member": anyone signed in; "owner": you (the person whose Dakku it is); "this-pc": this PC only.
ROUTES = [
    ("GET", r"/api/health", "health", "anyone", True),
    ("GET", r"/api/whoami", "whoami", "anyone", True),
    ("POST", r"/api/login", "login", "anyone", True),  # at the friends' door: a friend's pairing code only
    ("POST", r"/api/join", "join", "anyone", True),
    ("POST", r"/api/invite", "invite_peek", "anyone", True),
    ("POST", r"/api/logout", "logout", "member", True),
    ("GET", r"/api/bootstrap", "bootstrap", "member", True),
    ("GET", r"/api/sync", "sync_get", "member", True),
    ("POST", r"/api/sync", "sync_post", "member", True),
    ("GET", r"/api/timer", "timer_get", "member", True),
    ("POST", r"/api/timer", "timer_post", "member", True),
    ("PUT", r"/api/settings", "settings_put", "member", True),
    ("GET", r"/api/summary", "summary_get", "member", True),
    ("GET", r"/api/anki", "anki_get", "owner", False),
    ("GET", r"/api/devices", "devices_get", "member", True),
    ("PATCH", rf"/api/devices/{ID}", "device_patch", "member", True),
    ("DELETE", rf"/api/devices/{ID}", "device_delete", "member", True),
    ("GET", r"/api/passcode", "passcode_get", "this-pc", False),
    ("POST", r"/api/pair", "pair_post", "member", True),  # yours from this PC only; a friend's for themselves
    ("POST", r"/api/passcode", "passcode_post", "owner", False),
    ("GET", r"/api/push/key", "push_key", "member", True),
    ("POST", r"/api/push/subscribe", "push_subscribe", "member", True),
    ("POST", r"/api/push/unsubscribe", "push_unsubscribe", "member", True),
    ("POST", r"/api/push/test", "push_test", "member", True),
    ("GET", r"/api/events", "events", "member", True),
    ("GET", r"/api/export\.json", "export_json", "member", True),
    ("GET", r"/api/export\.csv", "export_csv", "member", True),
    ("POST", r"/api/import", "import_post", "owner", False),
    ("GET", r"/api/together", "together", "member", True),
    ("POST", r"/api/cheer", "cheer", "member", True),
    ("GET", r"/api/shop", "shop_get", "member", True),
    ("POST", r"/api/shop/buy", "shop_buy", "member", True),
    ("POST", r"/api/shop/mystery", "shop_mystery", "member", True),
    ("POST", r"/api/shop/requests", "shop_request", "member", True),
    ("POST", rf"/api/shop/requests/{ID}", "shop_answer", "owner", False),  # yours: hand over a custom duck, or refund it
    ("GET", rf"/api/groups/{ID}", "group_get", "member", True),
    ("PATCH", rf"/api/groups/{ID}", "group_patch", "member", True),
    ("DELETE", rf"/api/groups/{ID}/members/{PID}", "member_delete", "member", True),  # you, or someone leaving
    ("POST", r"/api/groups", "group_post", "owner", False),
    ("DELETE", rf"/api/groups/{ID}", "group_delete", "owner", False),
    ("POST", rf"/api/groups/{ID}/members", "member_post", "owner", False),
    ("PATCH", rf"/api/people/{PID}", "person_patch", "member", True),  # your own profile (or anyone's, for you)
    ("GET", rf"/api/people/{PID}/pond", "person_pond", "member", True),  # someone's pond: theirs, yours, or a groupmate's
    ("GET", r"/api/people", "people_get", "owner", False),
    ("DELETE", rf"/api/people/{PID}", "person_delete", "owner", False),
    ("POST", r"/api/invites", "invite_post", "owner", False),
    ("DELETE", rf"/api/invites/{ID}", "invite_delete", "owner", False),
]
ROUTES = [(m, re.compile(p + "$"), h, who, public) for m, p, h, who, public in ROUTES]
# What the demo Dakku leaves out: there's nothing to sign in to, pair, notify, import into or invite to.
DEMO_OFF = {"login", "logout", "join", "invite_peek", "passcode_get", "pair_post", "passcode_post", "push_subscribe", "push_unsubscribe",
            "push_test", "import_post", "device_patch", "device_delete", "group_post", "group_delete", "member_post",
            "member_delete", "person_delete", "invite_post", "invite_delete"}
DEMO_DEVICE = {"id": "demo", "name": "Demo"}


def _not_json(word):
    raise ValueError(f"{word} isn't JSON")


def make_handler(app, public=False):
    """The request handler for your door, or (public) the friends' door."""
    cookie_name = FRIENDS_COOKIE if public else COOKIE
    old_cookie = OLD_COOKIES[cookie_name]

    class Handler(BaseHTTPRequestHandler):
        server_version = "Dakku/" + __version__
        sys_version = ""
        protocol_version = "HTTP/1.1"  # connections are kept open between requests (see KEEP_ALIVE)
        timeout = IDLE_TIMEOUT  # (live updates send something every 20 seconds, so they stay open)
        disable_nagle_algorithm = True  # a response's headers and body go out at once, not an ACK apart
        compressed = None  # the app's text files, gzipped once each (see Compressed)

        def log_message(self, fmt, *args):  # quiet: errors are logged where they happen
            pass

        def version_string(self):
            return self.server_version  # (no Python version, and no trailing space)

        def do_GET(self):
            self._dispatch("GET")

        def do_HEAD(self):
            self._dispatch("HEAD")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        def do_PATCH(self):
            self._dispatch("PATCH")

        def do_DELETE(self):
            self._dispatch("DELETE")

        def do_OPTIONS(self):
            self._cookies = []
            origin = self.headers.get("Origin")
            self._send(204 if origin in app.allowed_origins else 403, b"", "text/plain")

        # ── plumbing ──────────────────────────────────────────────────────
        def handle_one_request(self):
            # each request, the first or the next on a kept connection, has HEADERS_IN seconds to arrive
            self.server.due(self.connection, self.server.headers_in)
            super().handle_one_request()

        def finish(self):
            self.server.due(self.connection, None)
            super().finish()

        def _dispatch(self, method):
            self.server.due(self.connection, None)  # its headers are in
            self._cookies = []
            self._signed_in = False
            self._body_read = False
            try:
                if self.headers.get("Transfer-Encoding"):  # (a body of unknown length: the next request couldn't be told apart)
                    raise ApiError(411, "Send a Content-Length.")
                url = urlsplit(self.path)
                if url.path.startswith("/api/"):
                    self._api(method, url.path, parse_qs(url.query))
                elif method in ("GET", "HEAD"):
                    self._static(url.path, url.query)
                else:
                    raise ApiError(405, "Method not allowed.")
            except ApiError as err:
                self._done_with_body()
                self._json(err.status, {"error": err.message, **err.extra},
                           {"Retry-After": str(err.extra["retryAfter"])} if "retryAfter" in err.extra else None)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):  # the other end went away: not an error
                self.close_connection = True
            except Exception:
                traceback.print_exc()
                self._done_with_body()
                try:
                    self._json(500, {"error": "Something went wrong on the server."})
                except OSError:
                    pass
            finally:
                self._done_with_body()

        def _done_with_body(self):
            """A body that was never read (the request was turned away first) would be read as the next
            request on a kept connection: so that connection closes once this response is sent."""
            if not self._body_read and (self.headers.get("Content-Length") or "0").strip() not in ("", "0"):
                self.close_connection = True
            if self.headers.get("Transfer-Encoding"):
                self.close_connection = True

        def _context(self):
            ip = self.client_address[0]
            host = (self.headers.get("Host") or "").strip().lower()
            hostname = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
            proxied = any(self.headers.get(h) for h in PROXY_HEADERS)
            local = ip in LOOPBACK_IPS and hostname in LOOPBACK_HOSTS and not proxied
            https = (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"
            token, old = None, False
            auth = self.headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                token = auth[7:].strip()
            elif self.headers.get("Cookie"):
                try:
                    jar = SimpleCookie(self.headers["Cookie"])
                except CookieError:
                    jar = {}
                if cookie_name in jar:
                    token = jar[cookie_name].value
                elif old_cookie in jar:
                    token, old = jar[old_cookie].value, True
            origin = self.headers.get("Origin") or (("https://" if https else "http://") + host if host else "")
            if app.demo:  # everyone is let in, as the same made-up device
                return Ctx(ip=ip, device=DEMO_DEVICE, https=https or origin.startswith("https://"), origin=origin,
                           user_agent=self.headers.get("User-Agent") or "")
            device = app.device_for_token(token)
            if public:  # Funnel relays the internet from this PC itself: nobody here is "this PC"
                ip = (self.headers.get("X-Forwarded-For") or ip).split(",")[-1].strip()  # the address Tailscale saw
                local = False
                if device and (device.get("person") or "me") == "me":
                    device = None  # your own devices sign in at your door only: here, their sign-in is no one's
            if old and device:  # signed in before the cookie had its new name: moved over to it
                self._sign_in(token, https or origin.startswith("https://"))
                self._cookies.append(f"{old_cookie}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
            return Ctx(ip=ip, local=local, device=device, https=https or origin.startswith("https://"),
                       origin=origin, user_agent=self.headers.get("User-Agent") or "", public=public)

        def _body(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad Content-Length.")
            if length < 0:  # (read(-1) would read for as long as the sender keeps sending)
                raise ApiError(400, "Bad Content-Length.")
            if length > (MAX_BODY if getattr(self, "_signed_in", False) else MAX_BODY_ANYONE):
                raise ApiError(413, "That's too large.")
            if not length:
                return {}
            self.server.due(self.connection, self.server.body_grace + length / BODY_RATE)
            raw = self.rfile.read(length)
            self.server.due(self.connection, None)
            if len(raw) < length:
                raise ApiError(400, "The request ended early.")
            self._body_read = True
            try:
                data = json.loads(raw, parse_constant=_not_json)  # (no NaN or Infinity)
            except (ValueError, RecursionError):
                raise ApiError(400, "Expected JSON.")
            if not isinstance(data, dict):
                raise ApiError(400, "Expected a JSON object.")
            return data

        def _common_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Permissions-Policy", PERMISSIONS)
            if self.close_connection:
                self.send_header("Connection", "close")
            else:
                self.send_header("Connection", "keep-alive")
                self.send_header("Keep-Alive", f"timeout={int(self.server.headers_in)}")
            origin = self.headers.get("Origin")
            if origin and origin in app.allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Dakku, X-Mori, Authorization")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
                self.send_header("Access-Control-Max-Age", "600")

        def _send(self, status, body, ctype, extra=None, cache="no-store"):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self._common_headers()
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            for cookie in getattr(self, "_cookies", ()):
                self.send_header("Set-Cookie", cookie)
            # headers and body in one write (one packet, for most responses), not two
            self._headers_buffer.append(b"\r\n")
            data = b"".join(self._headers_buffer)
            self._headers_buffer = []
            self.wfile.write(data + body if self.command != "HEAD" else data)

        def _json(self, status, data, extra=None):
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
            if len(body) > GZIP_OVER and self._gzip_ok():  # (your history grows, and the friends' door is slow)
                body = gzip.compress(body, 6)
                extra = {**(extra or {}), "Content-Encoding": "gzip", "Vary": "Accept-Encoding"}
            self._send(status, body, "application/json; charset=utf-8", extra)

        def _gzip_ok(self):
            return "gzip" in (self.headers.get("Accept-Encoding") or "").lower()

        # ── the API ───────────────────────────────────────────────────────
        def _api(self, method, path, query):
            for m, pattern, name, who, open_to_friends in ROUTES:
                match = pattern.match(path)
                if match and (m == method or (m == "GET" and method == "HEAD")) and (open_to_friends or not public):
                    break
            else:
                raise ApiError(404, "Not found.")
            if app.demo and name in DEMO_OFF:
                raise ApiError(403, "That's switched off in the demo.")
            ctx = self._context()
            self._signed_in = ctx.signed_in
            if who in ("member", "owner") and not ctx.signed_in:
                raise ApiError(401, "Please sign in.", needsLogin=True)
            if who == "owner" and not ctx.owner:
                raise ApiError(403, "Only the person whose Dakku this is can do that.")
            if who == "this-pc" and not ctx.local:
                raise ApiError(403, "Only available on the PC that runs Dakku.")
            # stops other websites posting here (a page elsewhere can't add a header without asking first);
            # X-Mori is what the Genkan homepage sends, from before Dakku had its name
            if method not in ("GET", "HEAD") and "1" not in (self.headers.get("X-Dakku"), self.headers.get("X-Mori")):
                raise ApiError(403, "Missing the X-Dakku header.")
            # which build of the app is asking (a header; live updates, which can't send one, say it in the address)
            build = self.headers.get("X-Dakku-Build") or (query.get("build") or [""])[0]
            ctx.build = build if BUILD_RE.match(build) else ""
            app.touch(ctx)
            getattr(self, "api_" + name)(ctx, query, *match.groups())

        def api_health(self, ctx, q):
            self._json(200, {"ok": True, "app": "dakku", "version": __version__, "uptime": int(time.time() - app.started)})

        def api_whoami(self, ctx, q):
            self._json(200, app.whoami(ctx))

        def _sign_in(self, token, https):
            self._cookies.append(f"{cookie_name}={token}; Path=/; Max-Age={SIGN_IN_FOR}; HttpOnly; SameSite=Lax" + ("; Secure" if https else ""))

        def api_login(self, ctx, q):
            token, device = app.login(ctx, self._body())
            self._sign_in(token, ctx.https)
            self._json(200, {"ok": True, "device": device})

        def api_logout(self, ctx, q):
            app.logout(ctx)
            self._cookies = [f"{name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax" for name in (cookie_name, old_cookie)]
            self._json(200, {"ok": True})

        def api_invite_peek(self, ctx, q):
            self._json(200, app.peek_invite(ctx, self._body()))

        def api_join(self, ctx, q):
            token, person = app.join(ctx, self._body())
            if token:
                self._sign_in(token, ctx.https)
            self._json(200, {"ok": True, "person": person})

        def api_bootstrap(self, ctx, q):
            self._json(200, app.bootstrap(ctx))

        def api_sync_get(self, ctx, q):
            try:
                since = max(0, min(int((q.get("since") or ["0"])[0] or 0), 2 ** 62))
            except ValueError:
                raise ApiError(400, "since must be a number.")
            self._json(200, app.pull(since, ctx.person))

        def api_sync_post(self, ctx, q):
            self._json(200, app.push(self._body(), ctx.person))

        def api_timer_get(self, ctx, q):
            self._json(200, {"timer": app.timer(ctx.person)})

        def api_timer_post(self, ctx, q):
            self._json(200, app.timer_action(ctx, self._body()))

        def api_settings_put(self, ctx, q):
            body = self._body()
            self._json(200, {"settings": app.put_settings(body.get("settings", body), ctx.person)})

        def api_summary_get(self, ctx, q):
            self._json(200, app.summary(ctx.person))

        def api_anki_get(self, ctx, q):
            self._json(200, app.anki_view(refresh=(q.get("refresh") or ["0"])[0] == "1"))

        def api_devices_get(self, ctx, q):
            devices = app.store.devices(ctx.person)
            for d in devices:
                d["current"] = d["id"] == ctx.device_id
            self._json(200, {"devices": devices, "current": ctx.device_id, "build": app.build_id()})

        def api_device_patch(self, ctx, q, device_id):
            name = str(self._body().get("name") or "").strip()[:40]
            if not name or not app.store.rename_device(device_id, name, ctx.person):
                raise ApiError(404, "No such device.")
            self._json(200, {"ok": True})

        def api_device_delete(self, ctx, q, device_id):
            if not app.store.remove_device(device_id, ctx.person):
                raise ApiError(404, "No such device.")
            self._json(200, {"ok": True})

        def api_passcode_get(self, ctx, q):
            self._json(200, {"passcode": app.passcode_plain()})

        def api_pair_post(self, ctx, q):
            found = app.addresses()
            if ctx.owner:
                if not ctx.local:
                    raise ApiError(403, "Pairing codes for your devices come from the PC that runs Dakku.")
                url = found["https"] or found["tailnet"] or (found["lan"] or [None])[0]
            else:  # a friend signing in their own other device (say, their Home Screen app)
                url = found["friends"] or (f"https://{self.headers.get('Host')}" if ctx.public else None)
            self._json(200, dict(app.new_pair_code(ctx.person), url=url))

        def api_passcode_post(self, ctx, q):
            self._json(200, app.change_passcode(ctx, self._body()))

        def api_push_key(self, ctx, q):
            self._json(200, {"publicKey": app.vapid.public_b64})

        def api_push_subscribe(self, ctx, q):
            self._json(200, app.push_subscribe(ctx, self._body()))

        def api_push_unsubscribe(self, ctx, q):
            app.store.remove_push(str(self._body().get("endpoint") or ""), person=ctx.person)  # only your own
            self._json(200, {"ok": True})

        def api_push_test(self, ctx, q):
            results = app.notify({"title": "鴨 · Dakku", "body": "Notifications are on. Your ducks will tell you when they hatch.",
                                  "tag": "dakku-test", "url": "/"}, device_id=ctx.device_id, wait=True, person=ctx.person)
            if not results:
                raise ApiError(404, "This device hasn't turned on notifications yet.")
            self._json(200, {"results": results})

        def api_export_json(self, ctx, q):
            stamp = time.strftime("%Y-%m-%d")
            self._send(200, json.dumps(app.export(ctx.person), ensure_ascii=False, indent=1).encode(), "application/json; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="dakku-{stamp}.json"'})

        def api_export_csv(self, ctx, q):
            stamp = time.strftime("%Y-%m-%d")
            self._send(200, ("﻿" + app.export_csv(ctx.person)).encode(), "text/csv; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="dakku-{stamp}.csv"'})

        def api_import_post(self, ctx, q):
            self._json(200, app.import_data(self._body()))

        # ── together ──────────────────────────────────────────────────────
        def api_together(self, ctx, q):
            self._json(200, app.together(ctx.person))

        def api_cheer(self, ctx, q):
            self._json(200, app.cheer(ctx, self._body()))

        def api_shop_get(self, ctx, q):
            self._json(200, app.shop(ctx.person))

        def api_shop_buy(self, ctx, q):
            self._json(200, app.buy(ctx, self._body()))

        def api_shop_mystery(self, ctx, q):
            self._json(200, app.mystery(ctx))

        def api_shop_request(self, ctx, q):
            self._json(200, app.request_duck(ctx, self._body()))

        def api_shop_answer(self, ctx, q, rid):
            self._json(200, app.answer_request(ctx, rid, self._body()))

        def api_group_get(self, ctx, q, gid):
            self._json(200, app.group_view(ctx, gid))

        def api_group_patch(self, ctx, q, gid):
            self._json(200, app.update_group(ctx, gid, self._body()))

        def api_group_post(self, ctx, q):
            self._json(200, app.create_group(self._body()))

        def api_group_delete(self, ctx, q, gid):
            self._json(200, app.remove_group(gid))

        def api_member_post(self, ctx, q, gid):
            self._json(200, app.add_member(gid, str(self._body().get("person") or "")))

        def api_member_delete(self, ctx, q, gid, pid):
            self._json(200, app.remove_member(ctx, gid, pid))

        def api_people_get(self, ctx, q):
            self._json(200, app.people_view())

        def api_person_patch(self, ctx, q, pid):
            self._json(200, app.update_person(ctx, pid, self._body()))

        def api_person_pond(self, ctx, q, pid):
            self._json(200, app.person_pond(ctx, pid))

        def api_person_delete(self, ctx, q, pid):
            self._json(200, app.remove_person(pid))

        def api_invite_post(self, ctx, q):
            self._json(200, app.create_invite(self._body()))

        def api_invite_delete(self, ctx, q, iid):
            if not app.store.remove_invite(iid):
                raise ApiError(404, "No such invite.")
            self._json(200, {"ok": True})

        def api_events(self, ctx, q):
            client = app.subscribe(ctx.person)
            self.close_connection = True  # a stream has no length: the connection ends with it
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Accel-Buffering", "no")
                self._common_headers()
                self.end_headers()
                self.wfile.write(b"retry: 4000\n\n")
                self.wfile.flush()
                until, beat = time.time() + 30 * 60, time.time() + LIVE_BEAT  # browsers reconnect on their own
                # every second: is the page still there? (else its thread waits for the next write to find out)
                while time.time() < until and app.still_wanted(client) and not self._hung_up():
                    try:
                        event = client.get(timeout=1)
                        if event is None:  # Dakku is stopping
                            break
                        self.wfile.write(f"event: change\ndata: {event}\n\n".encode())
                    except queue.Empty:
                        if time.time() < beat:
                            continue
                        # a ping the page can see: one that hears nothing for a while knows its connection died
                        # without a word (a phone changing networks) and starts afresh; and which build of the
                        # app is out, so an open page hears of an update
                        self.wfile.write(f"event: ping\ndata: {json.dumps({'build': app.build_id()})}\n\n".encode())
                        app.touch(ctx)  # (open, so seen)
                    beat = time.time() + LIVE_BEAT
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                app.unsubscribe(client)

        def _hung_up(self):
            """The other end has closed the connection (it sends nothing more once it's asked)."""
            try:
                readable = select.select([self.connection], [], [], 0)[0]
                return bool(readable) and not self.connection.recv(1, socket.MSG_PEEK)
            except (OSError, ValueError):
                return True

        # ── the app's files ───────────────────────────────────────────────
        def _static(self, path, query=""):
            rel = path.lstrip("/") or "index.html"
            try:
                target = (app.web_dir / rel).resolve()
                if target != app.web_dir and app.web_dir not in target.parents:
                    raise ApiError(404, "Not found.")
                if not target.is_file():
                    if "." in Path(rel).name:
                        raise ApiError(404, "Not found.")
                    target = app.web_dir / "index.html"  # app pages such as /forest
                stat = target.stat()
            except (OSError, ValueError):  # a name no file could have (too long, a NUL byte)
                raise ApiError(404, "Not found.")
            etag, modified, build = file_version(app, target, stat)
            extra = {"ETag": etag}
            if not build:  # (these change with the other files, not when they're saved)
                extra["Last-Modified"] = modified
            if target.suffix == ".html":
                extra["Content-Security-Policy"] = CSP
            if target.name == "sw.js":
                extra["Service-Worker-Allowed"] = "/"
            # A picture's address ends in its version (?v=, see scripts/import_art.py), so it can be kept for good;
            # everything else is checked each time (it's usually unchanged: a quick 304).
            cache = "public, max-age=31536000, immutable" if rel.startswith("ducks/") and "v=" in query else "no-cache"
            # (the date too: some caches keep an ETag only from a server that always speaks HTTP/1.1, and this one once didn't)
            if self.headers.get("If-None-Match") == etag or (not build and "If-None-Match" not in self.headers
                                                             and self.headers.get("If-Modified-Since") == modified):
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", cache)
                self._common_headers()
                self.end_headers()
                return
            data = file_bytes(target, build)
            if target.suffix in COMPRESSIBLE and len(data) > GZIP_OVER and self._gzip_ok():
                data = Handler.compressed.get(target, etag, data)
                extra.update({"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
            self._send(200, data, MIME.get(target.suffix, "application/octet-stream"), extra, cache=cache)

    Handler.compressed = Compressed()
    return Handler


def file_version(app, target, stat=None):
    """How a file of the app is told apart from its last version: its ETag, its Last-Modified date, and the
    build it's stamped with (sw.js and app.js: see STAMPED)."""
    stat = stat or target.stat()
    modified = formatdate(stat.st_mtime, usegmt=True)
    build = app.build_id() if target.name in STAMPED and target.parent == app.web_dir else None
    # the service worker changes whenever any app file does, so phones update themselves; and the app
    # knows which build it is, so it can say (Settings → People & groups shows who has the newest)
    etag = f'"{target.stem}-{build}"' if build else f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    return etag, modified, build


def file_bytes(target, build=None):
    data = target.read_bytes()
    return data.replace(b"__BUILD__", build.encode()) if build else data


class Compressed:
    """The app's text files, gzipped once each: the current version of each file is kept, so no request
    compresses app.js again, and nothing piles up as files change."""

    def __init__(self):
        self._files, self._lock = {}, threading.Lock()

    def get(self, target, etag, data):
        with self._lock:
            hit = self._files.get(target)
        if hit and hit[0] == etag:
            return hit[1]
        gz = gzip.compress(data, 7)
        with self._lock:
            self._files[target] = (etag, gz)
        return gz

    def warm(self, app):
        """Compresses the app's files ahead of the first request for them (a moment after starting)."""
        for target in sorted(app.web_dir.rglob("*")):
            if target.is_file() and target.suffix in COMPRESSIBLE and not target.is_relative_to(app.web_dir / "ducks"):
                try:
                    etag, _, build = file_version(app, target)
                    data = file_bytes(target, build)
                    if len(data) > GZIP_OVER:
                        self.get(target, etag, data)
                except OSError:
                    pass
        for target in (app.web_dir / "ducks" / "ducks.json",):  # (the pictures themselves are already small)
            if target.is_file():
                etag, _, _ = file_version(app, target)
                self.get(target, etag, file_bytes(target))


class Server(ThreadingHTTPServer):
    """A door: each connection gets a thread, up to max_connections at once (see MAX_CONNECTIONS), and one
    that's too slow to send its request is cut off (see HEADERS_IN)."""
    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = True
    # (wait_for_slot: how long a new connection waits for a free thread when they're all busy. The door's
    # accept loop waits with it, so it's short: slots free up in milliseconds unless something's wrong.)
    max_connections, headers_in, body_grace, wait_for_slot = MAX_CONNECTIONS, HEADERS_IN, BODY_GRACE, 1

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(self.max_connections)
        self._busy = 0  # connections being served right now
        self._due, self._due_lock, self._closed = {}, threading.Lock(), threading.Event()
        super().__init__(*args, **kwargs)
        threading.Thread(target=self._cut_off_late, name="dakku-deadlines", daemon=True).start()

    def process_request(self, request, client_address):
        if not self._slots.acquire(timeout=self.wait_for_slot):  # every thread busy: it waits its turn, then is turned away
            self.shutdown_request(request)
            return
        with self._due_lock:
            self._busy += 1
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._let_go()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._let_go()

    def _let_go(self):
        with self._due_lock:
            self._busy -= 1
        self._slots.release()

    @property
    def busy(self):
        return self._busy

    def cut_waiting(self):
        """Closes the connections that are only waiting for their next request (stopping: the ones in the
        middle of one finish it)."""
        with self._due_lock:
            waiting = list(self._due)
        for conn in waiting:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def drain(self, seconds):
        """Waits, up to `seconds`, for the connections being served to finish."""
        until = time.monotonic() + seconds
        while self._busy and time.monotonic() < until:
            time.sleep(0.05)
        return not self._busy

    def due(self, conn, seconds):
        """`conn` must have sent what it's sending within `seconds` (None: it has)."""
        with self._due_lock:
            if seconds is None:
                self._due.pop(conn, None)
            else:
                self._due[conn] = time.monotonic() + seconds

    def _cut_off_late(self):
        while not self._closed.wait(0.5):
            now = time.monotonic()
            with self._due_lock:
                late = [conn for conn, until in self._due.items() if until < now]
                for conn in late:
                    del self._due[conn]
            for conn in late:
                try:
                    conn.shutdown(socket.SHUT_RDWR)  # its thread's read ends, and so does the request
                except OSError:
                    pass

    def server_close(self):
        self._closed.set()
        super().server_close()

    def handle_error(self, request, client_address):
        # Phones drop idle connections all the time (locking the screen, switching apps): not an error.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def serve(app, host, port, friends_port=None):
    handler = make_handler(app)
    httpd = Server((host, port), handler)
    httpd.headers_in = KEEP_ALIVE  # (yours: only your own devices come in here)
    app.port = httpd.server_address[1]
    log(f"鴨 Dakku {__version__} listening on http://{host}:{app.port}")
    doors = [httpd]
    if friends_port:  # the friends' door: this PC only, for Tailscale Funnel to open up
        friends = Server(("127.0.0.1", friends_port), make_handler(app, public=True))
        doors.append(friends)
        threading.Thread(target=friends.serve_forever, kwargs={"poll_interval": 0.5}, name="dakku-friends", daemon=True).start()
        log(f"the friends' door is on http://127.0.0.1:{friends.server_address[1]}")
    threading.Thread(target=handler.compressed.warm, args=(app,), name="dakku-gzip", daemon=True).start()

    # Told to stop (systemctl restart, Ctrl-C): no new requests are taken, the ones being served finish (live
    # updates end on their own within a second), and only then does the database close.
    def stop(signum, frame):
        log(f"stopping ({signal.Signals(signum).name})")
        threading.Thread(target=httpd.shutdown, name="dakku-stop", daemon=True).start()

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
    except ValueError:  # (not the main thread: tests)
        pass
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        app.stop()
        for door in doors[1:]:
            door.shutdown()
        for door in doors:
            door.cut_waiting()
        for door in doors:
            door.drain(STOP_WITHIN)
        for door in doors:
            door.server_close()
        app.close()
        log("stopped")
