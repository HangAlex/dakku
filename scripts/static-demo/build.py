#!/usr/bin/env python3
"""Builds the demo Dakku as a website on its own, for GitHub Pages: no PC needed.

    python3 scripts/static-demo/build.py OUT_DIR

It runs a copy of the demo (demo/, as the demo service has it) on 127.0.0.1, takes a snapshot of
what it shows right now (your sessions, Mina and Kai, the group, Anki), and writes the app's files
with that snapshot and fake-server.js, which answers the app's /api calls in the browser. The site
works from any folder (like hangalex.github.io/dakku/), so its paths are made relative. The
PC's addresses aren't in it, and there's no service worker or push.
"""
import json
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mori.app import App  # noqa: E402
from mori.web import Server, make_handler  # noqa: E402

HERE = Path(__file__).resolve().parent
WEB = ROOT / "web"
GROUP = "demo-club"
RELATIVE = re.compile(r"""(["'`])/(?!api/)([A-Za-z_][\w./-]*)""")  # "/app.js" → "app.js" (the /api calls are answered in the page)


def snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "demo"
        shutil.copytree(ROOT / "demo", data)
        app = App(data_dir=data, web_dir=WEB, demo=True)  # its background loop fills in today's sessions, and who's studying
        server = Server(("127.0.0.1", 0), make_handler(app))
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        try:
            time.sleep(2.5)
            get = lambda path: json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}"))  # noqa: E731
            snap = {"bootstrap": get("/api/bootstrap"), "group": get(f"/api/groups/{GROUP}"), "anki": get("/api/anki")}
        finally:
            server.shutdown()
            server.server_close()
            app.close()
    b = snap["bootstrap"]
    snap["at"] = b["now"]
    b["vapidKey"] = None
    b["settings"]["name"] = ""  # "Your pond", not "You's pond" (in Together you're still "You")
    b["server"]["addresses"] = {"lan": [], "tailnet": None, "https": None, "friends": None}
    return snap


def build(out):
    snap = snapshot()
    if out.exists():
        for child in out.iterdir():
            if child.name not in (".git", "README.md"):
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for path in WEB.rglob("*"):
        rel = path.relative_to(WEB)
        if path.is_dir() or rel.name in ("sw.js", "README.md"):
            continue
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in (".html", ".webmanifest") or rel.as_posix() in ("art.js", "lofi.js", "ducks/ducks.json"):
            text = path.read_text(encoding="utf-8")
            text = RELATIVE.sub(r"\1\2", text)
            if rel.name == "manifest.webmanifest":
                text = text.replace('"id": "/"', '"id": "dakku-demo"').replace('"start_url": "/"', '"start_url": "./"').replace('"scope": "/"', '"scope": "./"')
            if rel.name == "index.html":
                first = text.index("<script")
                text = text[:first] + '<script src="demo/snapshot.js"></script>\n  <script src="demo/fake-server.js"></script>\n  <script src="demo/tip.js" defer></script>\n  ' + text[first:]
                text = text.replace("<title>", "<title>Demo · ", 1)
            target.write_text(text, encoding="utf-8")
        elif rel.as_posix() == "app.js":
            text = path.read_text(encoding="utf-8")
            old = "  function registerWorker() {\n"
            assert old in text
            target.write_text(text.replace(old, old + "    return; // the demo on its own works without one\n"), encoding="utf-8")
        else:
            shutil.copy2(path, target)
    (out / "demo").mkdir(exist_ok=True)
    (out / "demo" / "snapshot.js").write_text("window.DAKKU_SNAPSHOT = " + json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    shutil.copy2(HERE / "fake-server.js", out / "demo" / "fake-server.js")
    shutil.copy2(HERE / "tip.js", out / "demo" / "tip.js")
    (out / ".nojekyll").write_text("")
    leaks = [p for p in out.rglob("*") if p.is_file() and p.suffix in (".js", ".json", ".html") and re.search(r"ts\.net|192\.168\.|taild", p.read_text(errors="ignore"))]
    assert not leaks, f"addresses left in {leaks}"
    rooms = snap["bootstrap"]["together"]["rooms"]
    print(f"Built {out}: {len(snap['bootstrap']['sessions'])} sessions, {len(snap['group']['pond'])} in the group pond, "
          f"{'someone studying now' if rooms else 'nobody studying now'}, at {time.strftime('%Y-%m-%d %H:%M', time.localtime(snap['at'] / 1000))}")


if __name__ == "__main__":
    build(Path(sys.argv[1]).expanduser().resolve())
