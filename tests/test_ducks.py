"""The ducks: the list, their pictures, the app and the server all agree, and the duck maker keeps
new pictures in Dakku's style."""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from dakku import logic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import duck  # noqa: E402


class TheList(unittest.TestCase):
    def setUp(self):
        self.ducks = duck.load()
        self.manifest = json.loads((ROOT / "web" / "ducks" / "ducks.json").read_text())
        # a duck just added waits for its picture from ChatGPT, and isn't in Dakku until it has one
        self.pictured = [did for did in self.ducks if (duck.PICTURES / f"{did}.png").is_file()]

    def test_every_duck_with_a_picture_is_in_dakku(self):
        for did in logic.BUILT_IN:
            self.assertIn(did, self.pictured)
        self.assertEqual(list(self.manifest["kinds"]), self.pictured)  # published, in the list's order
        for did, entry in self.manifest["kinds"].items():
            self.assertTrue((ROOT / "web" / entry["src"].split("?")[0].lstrip("/")).is_file(), did)
            self.assertIn("small", entry, did)  # its small copy, for everywhere it isn't shown big

    def test_every_picture_address_names_its_version(self):
        # phones keep pictures for good, so an address must change whenever its picture does
        addresses = re.findall(r'"(/ducks/[^"]+)"', (ROOT / "web" / "ducks" / "ducks.json").read_text())
        self.assertGreater(len(addresses), 100)
        for address in addresses:
            path, _, version = address.partition("?v=")
            data = (ROOT / "web" / path.lstrip("/")).read_bytes()
            self.assertEqual(version, hashlib.sha256(data).hexdigest()[:10], address)

    def test_the_app_and_the_server_know_the_same_ducks(self):
        js = (ROOT / "web" / "kinds.js").read_text()
        listed = json.loads(js[js.index("{"):js.rindex("}") + 1])
        self.assertEqual(list(listed), self.pictured)
        logic.use_ducks(ROOT / "web" / "ducks" / "ducks.json")
        self.assertEqual(logic.species()[:10], logic.BUILT_IN)
        self.assertEqual(set(logic.species()), set(self.pictured) | set(logic.BUILT_IN))
        self.assertEqual(logic.noun("sonic"), "Sonic duck")
        self.assertEqual(logic.kind("ume"), "yukata")  # old tree names still mean their duck

    def test_ids_and_details(self):
        art = (ROOT / "web" / "art.js").read_text()
        built_in = re.findall(r"^    (\w+): \{ kanji:", art, re.M)
        self.assertEqual(tuple(built_in), logic.BUILT_IN)
        for did, d in self.ducks.items():
            self.assertRegex(did, duck.ID_RE)
            self.assertNotIn(did, logic.OLD_SPECIES)
            self.assertTrue(d["name"] and d["kanji"] and d["look"], did)
            self.assertIn(d.get("face", "calm"), duck.FACES)

    def test_every_picture_is_in_style(self):
        self.assertEqual(duck.check(say=lambda line: None), 0)


class TheDuckMaker(unittest.TestCase):
    def setUp(self):
        self.shiro = Image.open(duck.PICTURES / "shiro.png").convert("RGBA")
        self.body = duck.load()["shiro"]["body"]

    def test_finds_the_eye_and_beak(self):
        eye = duck.find_eye(self.shiro, self.body)
        beak = duck.find_beak(self.shiro, self.body, eye)
        self.assertTrue(eye and beak)
        self.assertLess(sum(x for x, _ in beak) / len(beak), eye["x"])  # in front of the eye: it faces left

    def test_an_orange_beak_is_made_peach(self):
        img = self.shiro.copy()
        beak = duck.find_beak(img, self.body, duck.find_eye(img, self.body))
        px = img.load()
        for x, y in beak:  # make it the strong orange ChatGPT sometimes paints
            px[x, y] = (252, 160, 70, 255)
        notes = []
        done, facts = duck.finish(img, body=self.body, notes=notes)
        self.assertTrue(any("peach" in n for n in notes), notes)
        self.assertFalse(duck.off(duck.hsv_median(done, duck.find_beak(done, self.body, duck.find_eye(done, self.body)))))

    def test_a_duck_facing_right_is_turned_round(self):
        notes = []
        done, _ = duck.finish(self.shiro.transpose(Image.FLIP_LEFT_RIGHT), body=self.body, notes=notes)
        self.assertTrue(any("face left" in n for n in notes), notes)
        eye = duck.find_eye(done, self.body)
        beak = duck.find_beak(done, self.body, eye)
        self.assertLess(sum(x for x, _ in beak) / len(beak), eye["x"])

    def test_golden_hair_by_the_eye_isnt_the_beak(self):
        # light golden-brown hair just behind the eye, nearer to it than the beak (Link's): it's not taken for the beak
        img = self.shiro.copy()
        eye = duck.find_eye(img, self.body)
        b = self.body
        img.paste((213, 158, 92, 255), (round(eye["x"] + 0.06 * b), round(eye["y"] - 0.2 * b), round(eye["x"] + 0.22 * b), round(eye["y"] - 0.04 * b)))
        notes = []
        done, _ = duck.finish(img, body=self.body, notes=notes)
        self.assertFalse(any("face left" in n for n in notes), notes)  # not turned round
        beak = duck.find_beak(done, self.body, duck.find_eye(done, self.body))
        self.assertLess(sum(x for x, _ in beak) / len(beak), eye["x"])

    def test_a_squashed_duck_is_sent_back(self):
        # the way ChatGPT sometimes draws them: the body lower and longer, so the duck looks short
        flat = self.shiro.resize((round(self.shiro.width * 1.15), round(self.shiro.height * 0.8)), Image.LANCZOS)
        done, facts = duck.finish(flat)
        self.assertTrue(any("redraw it" in p for p in facts["problems"]), facts["problems"])
        self.assertEqual(done.size, flat.size)  # flagged, not stretched
        _, facts = duck.finish(self.shiro.copy(), body=self.body)
        self.assertEqual(facts["problems"], [])
        self.assertAlmostEqual(facts["eye_height"], duck.EYE_HEIGHT, delta=0.04)

    def test_long_hair_doesnt_make_a_duck_small(self):
        # a long pale-blue ponytail falling behind it, out past its tail: the outline measures wide
        img = Image.new("RGBA", (self.shiro.width + 260, self.shiro.height), (0, 0, 0, 0))
        img.alpha_composite(self.shiro, (0, 0))
        hair = Image.new("RGBA", (330, round(self.shiro.height * 0.5)), (120, 200, 210, 255))
        img.alpha_composite(hair, (self.shiro.width - 70, round(self.shiro.height * 0.48)))
        notes = []
        _, facts = duck.finish(img, notes=notes)
        self.assertTrue(any("sized from its beak" in n for n in notes), notes)
        self.assertLess(abs(facts["body"] - self.body) / self.body, 0.12, facts)
        self.assertEqual(facts["problems"], [])

    def test_a_chatgpt_picture_with_a_checkerboard(self):
        # one duck on a painted-in gray checkerboard, the way ChatGPT sometimes "does" transparency
        w, h = self.shiro.width + 200, self.shiro.height + 200
        board = Image.new("RGBA", (w, h))
        bp = board.load()
        for y in range(h):
            for x in range(w):
                bp[x, y] = (191, 192, 196, 255) if (x // 6 + y // 6) % 2 else (145, 145, 149, 255)
        board.alpha_composite(self.shiro, (100, 100))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.png"
            board.convert("RGB").save(path)
            piece, notes = duck.from_chatgpt(path)
        self.assertTrue(any("transparent" in n for n in notes), notes)
        self.assertLess(abs(piece.width - self.shiro.width), 6)  # the duck alone, without the board
        self.assertLess(abs(piece.height - self.shiro.height), 6)

    def test_the_prompt_says_it_all(self):
        text = duck.prompt({"look": "a chef hat and apron", "face": "angry"})
        for must in ("attached reference", "as round and tall as the plain white duck", duck.beak_hex(), "No feet, legs, arms or hands", "facing left",
                     "transparent background", "a chef hat and apron", "angry eyebrow"):
            self.assertIn(must, text)
