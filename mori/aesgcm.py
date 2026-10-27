"""AES-128-GCM in plain Python (the standard library has no AES).

Only used to encrypt small Web Push payloads, so it is written to be easy to check
against the published test vectors (see tests/test_crypto.py), not to be fast.
"""
import hmac


def _rotl8(x, shift):
    return ((x << shift) | (x >> (8 - shift))) & 0xFF


def _make_sbox():
    # Walk the multiplicative group of GF(2^8): p * q == 1 throughout, then apply the affine map.
    sbox = [0] * 256
    p = q = 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)  # p * 3
        q ^= q << 1  # q / 3
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        sbox[p] = q ^ _rotl8(q, 1) ^ _rotl8(q, 2) ^ _rotl8(q, 3) ^ _rotl8(q, 4) ^ 0x63
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


SBOX = _make_sbox()
RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(b):
    b <<= 1
    return b ^ 0x11B if b & 0x100 else b


def expand_key(key):
    if len(key) != 16:
        raise ValueError("AES-128 needs a 16-byte key")
    words = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        t = list(words[i - 1])
        if i % 4 == 0:
            t = [SBOX[b] for b in t[1:] + t[:1]]
            t[0] ^= RCON[i // 4 - 1]
        words.append([a ^ b for a, b in zip(words[i - 4], t)])
    return [sum(words[4 * r:4 * r + 4], []) for r in range(11)]


def encrypt_block(round_keys, block):
    # State is column-major: byte (row r, column c) lives at index r + 4c.
    s = [b ^ k for b, k in zip(block, round_keys[0])]
    for rnd in range(1, 11):
        s = [SBOX[b] for b in s]
        s = [s[r + 4 * ((c + r) % 4)] for c in range(4) for r in range(4)]  # ShiftRows
        if rnd != 10:
            mixed = []
            for c in range(4):
                a0, a1, a2, a3 = s[4 * c:4 * c + 4]
                mixed += [
                    _xtime(a0) ^ _xtime(a1) ^ a1 ^ a2 ^ a3,
                    a0 ^ _xtime(a1) ^ _xtime(a2) ^ a2 ^ a3,
                    a0 ^ a1 ^ _xtime(a2) ^ _xtime(a3) ^ a3,
                    _xtime(a0) ^ a0 ^ a1 ^ a2 ^ _xtime(a3),
                ]
            s = mixed
        s = [b ^ k for b, k in zip(s, round_keys[rnd])]
    return bytes(s)


_R = 0xE1 << 120


def _gf_mul(x, y):
    z, v = 0, y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        v = (v >> 1) ^ _R if v & 1 else v >> 1
    return z


def _pad16(data):
    return data + b"\x00" * (-len(data) % 16)


def _ghash(h, aad, ciphertext):
    data = _pad16(aad) + _pad16(ciphertext) + (len(aad) * 8).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big")
    y = 0
    for i in range(0, len(data), 16):
        y = _gf_mul(y ^ int.from_bytes(data[i:i + 16], "big"), h)
    return y.to_bytes(16, "big")


def _ctr(round_keys, j0, data):
    out = bytearray()
    counter = int.from_bytes(j0, "big")
    for i in range(0, len(data), 16):
        counter = (counter & ~0xFFFFFFFF) | ((counter + 1) & 0xFFFFFFFF)  # inc32
        stream = encrypt_block(round_keys, counter.to_bytes(16, "big"))
        out += bytes(a ^ b for a, b in zip(data[i:i + 16], stream))
    return bytes(out)


def encrypt(key, nonce, plaintext, aad=b""):
    """Returns ciphertext || 16-byte tag. The nonce must be 12 bytes."""
    if len(nonce) != 12:
        raise ValueError("GCM nonce must be 12 bytes")
    rk = expand_key(key)
    h = int.from_bytes(encrypt_block(rk, bytes(16)), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    ciphertext = _ctr(rk, j0, plaintext)
    tag = bytes(a ^ b for a, b in zip(encrypt_block(rk, j0), _ghash(h, aad, ciphertext)))
    return ciphertext + tag


def decrypt(key, nonce, data, aad=b""):
    if len(nonce) != 12 or len(data) < 16:
        raise ValueError("bad GCM input")
    rk = expand_key(key)
    h = int.from_bytes(encrypt_block(rk, bytes(16)), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    ciphertext, tag = data[:-16], data[-16:]
    expected = bytes(a ^ b for a, b in zip(encrypt_block(rk, j0), _ghash(h, aad, ciphertext)))
    if not hmac.compare_digest(tag, expected):
        raise ValueError("authentication failed")
    return _ctr(rk, j0, ciphertext)
