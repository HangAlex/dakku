"""♪ Lofi: the songs Dakku plays on the Hatch screen, and how scripts/lofi.py finds them on YouTube."""
import json
import re
import sys
import unittest
from pathlib import Path

from mori import web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lofi  # noqa: E402


class ThePlaylist(unittest.TestCase):
    def setUp(self):
        self.tracks = json.loads((ROOT / "web" / "lofi.json").read_text())["tracks"]

    def test_every_song_has_its_video(self):
        self.assertTrue(self.tracks)
        for t in self.tracks:
            self.assertRegex(t["yt"], r"^[\w-]{11}$")
            self.assertRegex(t["spotify"], r"^[A-Za-z0-9]{22}$")
            self.assertTrue(t["title"] and t["artists"], t)
        self.assertEqual(len({t["yt"] for t in self.tracks}), len(self.tracks))

    def test_only_songs_from_the_playlist(self):
        links = list(dict.fromkeys(re.findall(r"track[/:]([A-Za-z0-9]{22})", (ROOT / "art" / "lofi.txt").read_text())))
        played = [t["spotify"] for t in self.tracks]
        self.assertEqual(played, [i for i in links if i in played])  # in the playlist's order, nothing extra

    def test_the_page_may_hold_youtubes_player(self):
        self.assertIn("frame-src https://www.youtube-nocookie.com;", web.CSP)


class FindingTheSong(unittest.TestCase):
    track = {"title": "Snow & Sand", "artists": ["j'san", "Epektase"], "seconds": 172}

    def test_the_same_recording(self):
        self.assertIsNotNone(lofi.score(self.track, ("a", "Snow & Sand", "j'san - Topic", 173)))

    def test_not_another_version(self):
        for title, secs in (("Snow & Sand (sped up)", 172), ("Snow & Sand slowed + reverb", 172), ("Snow & Sand 1 hour", 3600),
                            ("Snow & Sand", 140), ("Sand Dunes", 172)):
            self.assertIsNone(lofi.score(self.track, ("a", title, "someone", secs)), title)

    def test_the_artists_own_upload_first(self):
        topic = lofi.score(self.track, ("a", "Snow & Sand", "j'san - Topic", 172))
        reupload = lofi.score(self.track, ("b", "j'san - Snow & Sand", "Lofi Girl", 172))
        self.assertGreater(topic, reupload)

    def test_an_artist_called_loops_is_no_loop(self):
        t = {"title": "Drifting Far Away", "artists": ["Mondo Loops"], "seconds": 150}
        self.assertIsNotNone(lofi.score(t, ("a", "Drifting Far Away", "Mondo Loops", 150)))
