"""Run Dakku: python3 -m mori   (settings come from environment variables, see SETUP.md).
The demo, with made-up ducks: python3 -m mori --demo   (or scripts/demo.sh)."""
import os
import sys
from pathlib import Path

from .app import App
from .web import serve

ROOT = Path(__file__).resolve().parent.parent


def build(argv, env):
    """The Dakku to run, and where to listen."""
    if "--demo" in argv:
        # The demo (see demo.py) always has its own data folder, whatever MORI_DATA says, so it can
        # never open your real one, and no backups or Anki.
        app = App(data_dir=ROOT / "demo", web_dir=ROOT / "web", demo=True)
        return app, env.get("MORI_HOST", "0.0.0.0"), int(env.get("MORI_DEMO_PORT", "8642"))
    backups = env.get("MORI_BACKUPS", str(Path.home() / "Documents" / "Homepage" / "Dakku backups"))
    app = App(
        data_dir=env.get("MORI_DATA", str(ROOT / "data")),
        web_dir=ROOT / "web",
        backup_dir=backups or None,
        anki_url=env.get("MORI_ANKI", "http://127.0.0.1:8765") or None,
        dev_origins=env.get("MORI_DEV_ORIGINS", "").split(","),
        friends_url=env.get("MORI_FRIENDS_URL"),  # only if friends reach their door some other way than Funnel
    )
    return app, env.get("MORI_HOST", "0.0.0.0"), int(env.get("MORI_PORT", "8640"))


def main():
    app, host, port = build(sys.argv[1:], os.environ)
    # the friends' door (see web.py); the demo has none, and MORI_FRIENDS_PORT=0 turns it off
    friends = 0 if app.demo else int(os.environ.get("MORI_FRIENDS_PORT", "8643") or 0)
    serve(app, host, port, friends_port=friends or None)


if __name__ == "__main__":
    main()
