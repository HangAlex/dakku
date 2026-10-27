#!/usr/bin/env python3
"""The lofi playlist on Dakku's Hatch screen: Spotify tracks, played from YouTube.

Spotify only plays whole songs to someone signed in to Spotify in that very browser, so Dakku
finds each song on YouTube instead and plays them there, shuffled. Put the Spotify track links in
art/lofi.txt (one per line, or however Spotify copies them), then run

    python3 scripts/lofi.py

It looks up each track's title, artists and length on Spotify, finds the same recording on
YouTube (the same title, within a few seconds of the same length, preferring the artist's own
upload or their "- Topic" channel, never a sped-up, slowed or hour-long version), checks YouTube
lets it play inside other sites, and writes web/lofi.json. Songs already found keep their match,
so running it again only looks up new ones. Reload Dakku.

    python3 scripts/lofi.py --redo     looks every song up again
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "art" / "lofi.txt"
OUT = ROOT / "web" / "lofi.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
NOT_THE_SONG = ("sped up", "speed up", "slowed", "reverb", "1 hour", "hour loop", "loop", "8d", "nightcore", "remix",
                "cover", "karaoke", "tutorial")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")


def spotify(track_id):
    """A track's title, artists and length, from its public embed page."""
    html = get(f"https://open.spotify.com/embed/track/{track_id}")
    data = json.loads(re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S).group(1))
    entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    return {"title": entity["name"], "artists": [a["name"] for a in entity.get("artists") or []],
            "seconds": round((entity.get("duration") or 0) / 1000)}


def youtube(query):
    """YouTube's search results for `query`: (video id, title, channel, seconds)."""
    html = get("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query, "hl": "en", "gl": "US"}))
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "videoRenderer" in node:
                v = node["videoRenderer"]
                secs = 0
                for part in v.get("lengthText", {}).get("simpleText", "").split(":"):
                    secs = secs * 60 + int(part) if part.isdigit() else secs
                found.append((v.get("videoId"), "".join(r.get("text", "") for r in v.get("title", {}).get("runs", [])),
                              "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])), secs))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    if m:
        walk(json.loads(m.group(1)))
    return found


def plain(s):
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def score(track, video):
    """How sure we are a YouTube video is this track (None: it isn't)."""
    _, title, channel, secs = video
    want = plain(track["title"].split(" - ")[0].split(" (")[0])
    if not want or want not in plain(title):
        return None
    words = title.lower()
    for name in (*track["artists"], channel):  # an artist called Mondo Loops isn't a loop
        words = words.replace(name.lower(), " ")
    if any(w in words and w not in track["title"].lower() for w in NOT_THE_SONG):
        return None
    off = abs(secs - track["seconds"]) if secs else 99
    if off > 6:
        return None
    artists, owner = [plain(a) for a in track["artists"]], plain(channel.replace(" - Topic", ""))
    s = 10 - off
    if channel.endswith(" - Topic") and any(a and a in owner for a in artists):
        s += 6  # the official audio, made from the release itself
    elif any(a and len(owner) > 2 and (a == owner or a in owner or owner in a) for a in artists):
        s += 5  # the artist's own channel
    elif any(a and a in plain(title) for a in artists):
        s += 2
    return s


def find(track):
    for query in (f"{' '.join(track['artists'][:2])} {track['title']}", f"{track['artists'][0]} - {track['title']} topic",
                  f"{track['title']} {track['artists'][0]} lofi"):
        for attempt in range(3):
            try:
                results = youtube(query)
            except (urllib.error.URLError, OSError, ValueError):
                results = []
            if results:
                break
            time.sleep(3)
        scored = [(score(track, v), v) for v in results[:15]]
        scored = [(s, v) for s, v in scored if s is not None]
        if scored:
            return max(scored)[1]
        time.sleep(1)
    return None


def embeddable(video_id):
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"})
    try:
        get(url)
        return True
    except urllib.error.HTTPError:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--redo", action="store_true", help="look every song up again")
    args = ap.parse_args(argv)
    ids = list(dict.fromkeys(re.findall(r"(?:track[/:])([A-Za-z0-9]{22})", LINKS.read_text()) if LINKS.exists() else []))
    if not ids:
        raise SystemExit(f"No Spotify track links in {LINKS}.")
    known = {} if args.redo or not OUT.exists() else {t["spotify"]: t for t in json.loads(OUT.read_text()).get("tracks", [])}
    tracks, missing = [], []
    for n, tid in enumerate(ids, 1):
        if tid in known:
            tracks.append(known[tid])
            continue
        try:
            info = spotify(tid)
        except Exception as e:  # noqa: BLE001  (a page that changed or a hiccup: say so, carry on)
            missing.append(f"{tid} (Spotify: {str(e)[:60]})")
            continue
        video = find(info)
        if not video or not embeddable(video[0]):
            missing.append(f"{info['title']} by {', '.join(info['artists'])}")
            continue
        tracks.append({"spotify": tid, "yt": video[0], **info})
        print(f"  {n:3d}. {info['title']} — {', '.join(info['artists'])}  →  {video[1]} ({video[2]})", flush=True)
        time.sleep(0.6)
    text = json.dumps({"tracks": tracks}, ensure_ascii=False, indent=1)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(f"{len(tracks)} songs in web/lofi.json.")
    if missing:
        print("Couldn't find these on YouTube (they're left out):\n  " + "\n  ".join(missing))


if __name__ == "__main__":
    sys.exit(main())
