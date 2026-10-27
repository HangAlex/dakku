# The server

Plain Python with no dependencies. It runs on my PC and everything else talks to it. (The folder is still called
`mori`, Dakku's old name.)

- `app.py`: the rules: sign-in, sessions, the shared timer, studying together, cheers, notifications and backups
- `web.py`: HTTP: the app's files, the JSON API and live updates, through two doors (mine, and the friends' door)
- `store.py`: storage, in SQLite
- `logic.py`: days, streaks (with streak freezes) and totals
- `demo.py`: the demo, a Dakku full of made-up ducks
- `webpush.py`, `ec.py`, `aesgcm.py`: push notifications, with the encryption written out in plain Python
- `anki.py`: reads my Anki progress
- `words.py`: the words passcodes are made of
- `__main__.py`: starts it all: `python3 -m mori`, or `python3 -m mori --demo` for the demo
