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
import sys
import threading
import time
import traceback
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
IDLE_TIMEOUT = 60  # seconds a connection may sit without sending: so idle ones can't pile up and hold threads
COOKIE = "mori"
# The friends' door signs people in with a cookie of its own: browsers share cookies between ports
# of the same host, and a friend's sign-in must never reach your door (or yours theirs).
FRIENDS_COOKIE = "mori_friend"
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
    ("GET", rf"/api/groups/{ID}", "group_get", "member", True),
    ("PATCH", rf"/api/groups/{ID}", "group_patch", "member", True),
    ("DELETE", rf"/api/groups/{ID}/members/{PID}", "member_delete", "member", True),  # you, or someone leaving
    ("POST", r"/api/groups", "group_post", "owner", False),
    ("DELETE", rf"/api/groups/{ID}", "group_delete", "owner", False),
    ("POST", rf"/api/groups/{ID}/members", "member_post", "owner", False),
    ("PATCH", rf"/api/people/{PID}", "person_patch", "member", True),  # your own profile (or anyone's, for you)
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


def make_handler(app, public=False):
    """The request handler for your door, or (public) the friends' door."""
    gz_cache = {}
    cookie_name = FRIENDS_COOKIE if public else COOKIE

    class Handler(BaseHTTPRequestHandler):
        server_version = "Dakku/" + __version__
        sys_version = ""
        protocol_version = "HTTP/1.0"
        timeout = IDLE_TIMEOUT  # (live updates send something every 20 seconds, so they stay open)

        def log_message(self, fmt, *args):  # quiet: errors are logged where they happen
            pass

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
            self._cookie = None
            origin = self.headers.get("Origin")
            self._send(204 if origin in app.allowed_origins else 403, b"", "text/plain")

        # ── plumbing ──────────────────────────────────────────────────────
        def _dispatch(self, method):
            self._cookie = None
            self._signed_in = False
            try:
                url = urlsplit(self.path)
                if url.path.startswith("/api/"):
                    self._api(method, url.path, parse_qs(url.query))
                elif method in ("GET", "HEAD"):
                    self._static(url.path)
                else:
                    raise ApiError(405, "Method not allowed.")
            except ApiError as err:
                self._json(err.status, {"error": err.message, **err.extra},
                           {"Retry-After": str(err.extra["retryAfter"])} if "retryAfter" in err.extra else None)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc()
                try:
                    self._json(500, {"error": "Something went wrong on the server."})
                except OSError:
                    pass

        def _context(self):
            ip = self.client_address[0]
            host = (self.headers.get("Host") or "").strip().lower()
            hostname = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
            proxied = any(self.headers.get(h) for h in PROXY_HEADERS)
            local = ip in LOOPBACK_IPS and hostname in LOOPBACK_HOSTS and not proxied
            https = (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"
            token = None
            auth = self.headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                token = auth[7:].strip()
            elif self.headers.get("Cookie"):
                try:
                    jar = SimpleCookie(self.headers["Cookie"])
                    token = jar[cookie_name].value if cookie_name in jar else None
                except CookieError:
                    token = None
            origin = self.headers.get("Origin") or (("https://" if https else "http://") + host if host else "")
            if app.demo:  # everyone is let in, as the same made-up device
                return Ctx(ip=ip, device=DEMO_DEVICE, https=https or origin.startswith("https://"), origin=origin,
                           user_agent=self.headers.get("User-Agent") or "")
            if public:  # Funnel relays the internet from this PC itself: nobody here is "this PC"
                ip = (self.headers.get("X-Forwarded-For") or ip).split(",")[-1].strip()  # the address Tailscale saw
                local = False
            return Ctx(ip=ip, local=local, device=app.device_for_token(token), https=https or origin.startswith("https://"),
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
            try:
                data = json.loads(self.rfile.read(length))
            except ValueError:
                raise ApiError(400, "Expected JSON.")
            if not isinstance(data, dict):
                raise ApiError(400, "Expected a JSON object.")
            return data

        def _common_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            origin = self.headers.get("Origin")
            if origin and origin in app.allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Mori, Authorization")
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
            if self._cookie:
                self.send_header("Set-Cookie", self._cookie)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status, data, extra=None):
            self._send(status, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(),
                       "application/json; charset=utf-8", extra)

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
            if method not in ("GET", "HEAD") and self.headers.get("X-Mori") != "1":
                raise ApiError(403, "Missing the X-Mori header.")  # stops other websites posting here
            app.touch(ctx)
            getattr(self, "api_" + name)(ctx, query, *match.groups())

        def api_health(self, ctx, q):
            self._json(200, {"ok": True, "app": "mori", "version": __version__, "uptime": int(time.time() - app.started)})

        def api_whoami(self, ctx, q):
            self._json(200, app.whoami(ctx))

        def api_login(self, ctx, q):
            token, device = app.login(ctx, self._body())
            self._cookie = f"{cookie_name}={token}; Path=/; Max-Age=34560000; HttpOnly; SameSite=Lax" + ("; Secure" if ctx.https else "")
            self._json(200, {"ok": True, "device": device})

        def api_logout(self, ctx, q):
            app.logout(ctx)
            self._cookie = f"{cookie_name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            self._json(200, {"ok": True})

        def api_invite_peek(self, ctx, q):
            self._json(200, app.peek_invite(ctx, self._body()))

        def api_join(self, ctx, q):
            token, person = app.join(ctx, self._body())
            if token:
                self._cookie = f"{cookie_name}={token}; Path=/; Max-Age=34560000; HttpOnly; SameSite=Lax" + ("; Secure" if ctx.https else "")
            self._json(200, {"ok": True, "person": person})

        def api_bootstrap(self, ctx, q):
            self._json(200, app.bootstrap(ctx))

        def api_sync_get(self, ctx, q):
            self._json(200, app.pull(int((q.get("since") or ["0"])[0] or 0), ctx.person))

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
            self._json(200, {"devices": devices, "current": ctx.device_id})

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
                                  "tag": "mori-test", "url": "/"}, device_id=ctx.device_id, wait=True, person=ctx.person)
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
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Accel-Buffering", "no")
                self._common_headers()
                self.end_headers()
                self.wfile.write(b"retry: 4000\n\n")
                self.wfile.flush()
                until = time.time() + 30 * 60  # browsers reconnect on their own
                while time.time() < until:
                    try:
                        event = client.get(timeout=20)
                        self.wfile.write(f"event: change\ndata: {event}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": still here\n\n")
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                app.unsubscribe(client)

        # ── the app's files ───────────────────────────────────────────────
        def _static(self, path):
            rel = path.lstrip("/") or "index.html"
            target = (app.web_dir / rel).resolve()
            if target != app.web_dir and app.web_dir not in target.parents:
                raise ApiError(404, "Not found.")
            if not target.is_file():
                if "." in Path(rel).name:
                    raise ApiError(404, "Not found.")
                target = app.web_dir / "index.html"  # app pages such as /forest
            stat = target.stat()
            etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
            build = app.build_id() if target.name == "sw.js" else None
            if build:  # the service worker changes whenever any app file does, so phones update themselves
                etag = f'"sw-{build}"'
            extra = {"ETag": etag}
            if target.suffix == ".html":
                extra["Content-Security-Policy"] = CSP
            if target.name == "sw.js":
                extra["Service-Worker-Allowed"] = "/"
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            data = target.read_bytes()
            if build:
                data = data.replace(b"__BUILD__", build.encode())
            if target.suffix in COMPRESSIBLE and len(data) > 1024 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
                key = (str(target), etag)
                if key not in gz_cache:
                    gz_cache[key] = gzip.compress(data, 7)
                data = gz_cache[key]
                extra.update({"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
            self._send(200, data, MIME.get(target.suffix, "application/octet-stream"), extra, cache="no-cache")

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # Phones drop idle connections all the time (locking the screen, switching apps): not an error.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def serve(app, host, port, friends_port=None):
    httpd = Server((host, port), make_handler(app))
    app.port = httpd.server_address[1]
    log(f"鴨 Dakku {__version__} listening on http://{host}:{app.port}")
    friends = None
    if friends_port:  # the friends' door: this PC only, for Tailscale Funnel to open up
        friends = Server(("127.0.0.1", friends_port), make_handler(app, public=True))
        threading.Thread(target=friends.serve_forever, kwargs={"poll_interval": 0.5}, name="mori-friends", daemon=True).start()
        log(f"the friends' door is on http://127.0.0.1:{friends.server_address[1]}")
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        httpd.server_close()
        if friends:
            friends.shutdown()
            friends.server_close()
        app.close()
