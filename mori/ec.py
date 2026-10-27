"""Just enough NIST P-256 for Web Push, in plain Python: keys, ECDH and ES256 signatures.

A notification needs a handful of these operations, all on this computer, so this
favours being short and checkable over speed or constant-time tricks.
"""
import hashlib
import secrets

P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
     0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    (x1, y1), (x2, y2) = p1, p2
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None  # the point at infinity
        slope = (3 * x1 * x1 + A) * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(k, point=G):
    result, addend = None, point
    while k:
        if k & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        k >>= 1
    return result


def on_curve(point):
    x, y = point
    return 0 <= x < P and 0 <= y < P and (y * y - (x * x * x + A * x + B)) % P == 0


def encode_point(point):
    x, y = point
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def decode_point(data):
    if len(data) != 65 or data[0] != 4:
        raise ValueError("expected an uncompressed P-256 point")
    point = (int.from_bytes(data[1:33], "big"), int.from_bytes(data[33:], "big"))
    if not on_curve(point):
        raise ValueError("point is not on P-256")
    return point


def generate_private_key():
    return secrets.randbelow(N - 1) + 1


def public_key(private):
    return multiply(private)


def ecdh(private, peer_point):
    shared = multiply(private, peer_point)
    if shared is None:
        raise ValueError("bad peer key")
    return shared[0].to_bytes(32, "big")


def sign(private, message):
    """ES256 signature (raw r || s, as JWT wants)."""
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    while True:
        k = secrets.randbelow(N - 1) + 1
        r = multiply(k)[0] % N
        if not r:
            continue
        s = pow(k, -1, N) * (z + r * private) % N
        if s:
            return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def verify(public_point, message, signature):
    if len(signature) != 64:
        return False
    r, s = int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    if not (1 <= r < N and 1 <= s < N):
        return False
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    w = pow(s, -1, N)
    point = _add(multiply(z * w % N), multiply(r * w % N, public_point))
    return point is not None and point[0] % N == r
