"""The Web Push crypto, checked against published test vectors and against openssl."""
import base64
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from dakku import aesgcm, ec, webpush
from dakku.webpush import b64u, unb64u


class AES(unittest.TestCase):
    def test_sbox_spot_values(self):
        self.assertEqual([aesgcm.SBOX[i] for i in (0x00, 0x01, 0x53, 0xFF)], [0x63, 0x7C, 0xED, 0x16])

    def test_fips197_appendix_c1(self):
        rk = aesgcm.expand_key(bytes.fromhex("000102030405060708090a0b0c0d0e0f"))
        out = aesgcm.encrypt_block(rk, bytes.fromhex("00112233445566778899aabbccddeeff"))
        self.assertEqual(out.hex(), "69c4e0d86a7b0430d8cdb78070b4c55a")


class GCM(unittest.TestCase):
    def test_nist_case_2(self):
        out = aesgcm.encrypt(bytes(16), bytes(12), bytes(16))
        self.assertEqual(out[:16].hex(), "0388dace60b6a392f328c2b971b2fe78")
        self.assertEqual(out[16:].hex(), "ab6e47d42cec13bdf53a67b21257bddf")

    def test_nist_case_3(self):
        key = bytes.fromhex("feffe9928665731c6d6a8f9467308308")
        iv = bytes.fromhex("cafebabefacedbaddecaf888")
        pt = bytes.fromhex(
            "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
            "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255")
        out = aesgcm.encrypt(key, iv, pt)
        self.assertEqual(out[:-16].hex(),
                         "42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e"
                         "21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091473f5985")
        self.assertEqual(out[-16:].hex(), "4d5c2af327cd64a62cf35abd2ba6fab4")

    def test_round_trip_and_tamper(self):
        key, nonce = bytes(range(16)), bytes(range(12))
        sealed = aesgcm.encrypt(key, nonce, b"a duck for every session")
        self.assertEqual(aesgcm.decrypt(key, nonce, sealed), b"a duck for every session")
        broken = bytes([sealed[0] ^ 1]) + sealed[1:]
        with self.assertRaises(ValueError):
            aesgcm.decrypt(key, nonce, broken)


class RFC8291(unittest.TestCase):
    """The worked example from RFC 8291 section 5 / appendix A."""
    PLAIN = "V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24"
    AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
    AS_PUBLIC = "BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
    UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
    UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
    AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
    SALT = "DGv6ra1nlYgDCS1FRnbzlw"
    ECDH = "kyrL1jIIOHEzg3sM2ZWRHDRB62YACZhhSlknJ672kSs"
    BODY = ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_"
            "yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")

    def test_keys_match(self):
        as_private = int.from_bytes(unb64u(self.AS_PRIVATE), "big")
        self.assertEqual(b64u(ec.encode_point(ec.public_key(as_private))), self.AS_PUBLIC)
        ua_private = int.from_bytes(unb64u(self.UA_PRIVATE), "big")
        self.assertEqual(b64u(ec.encode_point(ec.public_key(ua_private))), self.UA_PUBLIC)

    def test_ecdh_both_ways(self):
        as_private = int.from_bytes(unb64u(self.AS_PRIVATE), "big")
        ua_private = int.from_bytes(unb64u(self.UA_PRIVATE), "big")
        one = ec.ecdh(as_private, ec.decode_point(unb64u(self.UA_PUBLIC)))
        two = ec.ecdh(ua_private, ec.decode_point(unb64u(self.AS_PUBLIC)))
        self.assertEqual(b64u(one), self.ECDH)
        self.assertEqual(one, two)

    def test_full_message(self):
        body = webpush.encrypt(unb64u(self.PLAIN), unb64u(self.UA_PUBLIC), unb64u(self.AUTH),
                               as_private=int.from_bytes(unb64u(self.AS_PRIVATE), "big"), salt=unb64u(self.SALT))
        self.assertEqual(b64u(body), self.BODY)

    def test_rejects_points_off_the_curve(self):
        bad = bytearray(unb64u(self.UA_PUBLIC))
        bad[-1] ^= 1
        with self.assertRaises(ValueError):
            ec.decode_point(bytes(bad))


def _der_int(value):
    raw = value.to_bytes(32, "big").lstrip(b"\x00") or b"\x00"
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def _der_signature(raw):
    body = _der_int(int.from_bytes(raw[:32], "big")) + _der_int(int.from_bytes(raw[32:], "big"))
    return b"\x30" + bytes([len(body)]) + body


def _spki_pem(point):
    der = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200") + ec.encode_point(point)
    b64 = base64.b64encode(der).decode()
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64)) + "\n-----END PUBLIC KEY-----\n"


class Signatures(unittest.TestCase):
    def test_sign_verify(self):
        d = ec.generate_private_key()
        sig = ec.sign(d, b"hello")
        self.assertTrue(ec.verify(ec.public_key(d), b"hello", sig))
        self.assertFalse(ec.verify(ec.public_key(d), b"hellp", sig))

    @unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
    def test_openssl_accepts_our_signatures(self):
        d = ec.generate_private_key()
        message = b"eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJtb3JpIn0"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pub.pem").write_text(_spki_pem(ec.public_key(d)))
            Path(tmp, "msg").write_bytes(message)
            for _ in range(5):  # different random k each time
                Path(tmp, "sig").write_bytes(_der_signature(ec.sign(d, message)))
                result = subprocess.run(["openssl", "dgst", "-sha256", "-verify", "pub.pem", "-signature", "sig", "msg"],
                                        cwd=tmp, capture_output=True, text=True)
                self.assertIn("Verified OK", result.stdout, result.stderr)

    def test_vapid_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            vapid = webpush.Vapid(str(Path(tmp, "vapid.json")))
            header = vapid.authorization("https://web.push.apple.com/QGuQyavXutnMH...", "https://my-pc.example.ts.net")
            self.assertTrue(header.startswith("vapid t="))
            token, key = header[len("vapid t="):].split(", k=")
            self.assertEqual(key, vapid.public_b64)
            head, claims, sig = token.split(".")
            self.assertEqual(json.loads(unb64u(head)), {"typ": "JWT", "alg": "ES256"})
            body = json.loads(unb64u(claims))
            self.assertEqual(body["aud"], "https://web.push.apple.com")
            self.assertEqual(body["sub"], "https://my-pc.example.ts.net")
            self.assertLess(body["exp"] - time.time(), 24 * 3600)  # Apple refuses more than a day
            self.assertTrue(ec.verify(vapid.public_point, f"{head}.{claims}".encode(), unb64u(sig)))
            # Same key after a restart, and the token is reused rather than re-signed.
            again = webpush.Vapid(str(Path(tmp, "vapid.json")))
            self.assertEqual(again.public_b64, vapid.public_b64)
            self.assertEqual(vapid.authorization("https://web.push.apple.com/other", "https://my-pc.example.ts.net"), header)

    def test_only_known_push_services(self):
        self.assertTrue(webpush.valid_endpoint("https://web.push.apple.com/abc"))
        self.assertTrue(webpush.valid_endpoint("https://fcm.googleapis.com/fcm/send/abc"))
        self.assertFalse(webpush.valid_endpoint("http://web.push.apple.com/abc"))
        self.assertFalse(webpush.valid_endpoint("https://evil.example/push.apple.com"))
        self.assertFalse(webpush.valid_endpoint("https://192.168.1.1/"))


if __name__ == "__main__":
    unittest.main()
