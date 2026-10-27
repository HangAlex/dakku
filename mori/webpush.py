"""Web Push: encrypt a notification (RFC 8291) and deliver it with a VAPID signature (RFC 8292).

This is what lets your iPhone show "Your duck hatched" on the lock screen while Dakku
is closed. It needs the app opened over https and added to the Home Screen.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import aesgcm, ec

RECORD_SIZE = 4096
# Browsers' push services. Anything else is refused, so Dakku never posts to arbitrary hosts.
PUSH_HOSTS = ("push.apple.com", "googleapis.com", "mozilla.com", "notify.windows.com")


def b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hmac(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()


def encrypt(plaintext, ua_public, auth_secret, as_private=None, salt=None):
    """aes128gcm content coding for one Web Push message (a single record)."""
    ua_point = ec.decode_point(ua_public)
    as_private = as_private or ec.generate_private_key()
    as_public = ec.encode_point(ec.public_key(as_private))
    salt = salt or secrets.token_bytes(16)
    if len(plaintext) + 17 > RECORD_SIZE:
        raise ValueError("notification payload is too large")
    prk_key = _hmac(auth_secret, ec.ecdh(as_private, ua_point))
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    record = aesgcm.encrypt(cek, nonce, plaintext + b"\x02")  # 0x02 marks the final record
    return salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public + record


def valid_endpoint(endpoint):
    try:
        url = urllib.parse.urlsplit(endpoint)
    except ValueError:
        return False
    host = (url.hostname or "").lower()
    return url.scheme == "https" and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


class Vapid:
    """The server's push identity: a P-256 key kept in data/vapid.json."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._tokens = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            self.private = int.from_bytes(unb64u(saved["private"]), "big")
        else:
            self.private = ec.generate_private_key()
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"private": b64u(self.private.to_bytes(32, "big"))}, f)
        self.public_point = ec.public_key(self.private)
        self.public_b64 = b64u(ec.encode_point(self.public_point))

    def authorization(self, endpoint, subject):
        """`vapid t=…, k=…`. Tokens last 12 h and are reused (Apple asks for at most one new token an hour)."""
        parts = urllib.parse.urlsplit(endpoint)
        audience = f"{parts.scheme}://{parts.netloc}"
        now = int(time.time())
        with self._lock:
            cached = self._tokens.get((audience, subject))
            if cached and cached[1] - now > 3600:
                return cached[0]
            expires = now + 12 * 3600
            header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
            claims = b64u(json.dumps({"aud": audience, "exp": expires, "sub": subject}, separators=(",", ":")).encode())
            signing_input = f"{header}.{claims}".encode()
            token = f"{header}.{claims}.{b64u(ec.sign(self.private, signing_input))}"
            value = f"vapid t={token}, k={self.public_b64}"
            self._tokens[(audience, subject)] = (value, expires)
            return value


def send(subscription, payload, vapid, subject, ttl=600, urgency="normal", topic=None, timeout=12):
    """Deliver one notification. Returns (HTTP status, detail); 404/410 mean the subscription is gone."""
    endpoint = subscription["endpoint"]
    if not valid_endpoint(endpoint):
        return 400, "not a known push service"
    body = encrypt(json.dumps(payload, ensure_ascii=False).encode(), unb64u(subscription["p256dh"]), unb64u(subscription["auth"]))
    headers = {
        "TTL": str(ttl),
        "Urgency": urgency,
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "Authorization": vapid.authorization(endpoint, subject),
    }
    if topic:
        headers["Topic"] = topic
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, ""
    except urllib.error.HTTPError as err:
        return err.code, err.read(300).decode(errors="replace")
    except OSError as err:
        return 0, str(err)
