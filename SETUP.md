# 鴨 Dakku: setting it up, and how it works

A focus timer that runs on your own PC. While you focus, an egg warms in its nest; when the
session ends, a chibi call duck hatches into your pond. It's a web app, so there's nothing to buy and no Apple developer
account: open the link on your iPhone, add it to your Home Screen, and it behaves like an app. Everything you log on the
phone, the Mac or the Genkan homepage lands in one place, on this PC.

- **孵 Hatch**: pick a time on the ring (5–180 min) or a quick pick, a tag and a duck (or a surprise), and start. Or use the
  stopwatch. The egg wobbles, cracks at half time, and peeks out near the end. The timer is shared: start it on your phone
  and the homepage shows it too. Give up and the egg goes cold. Tap ♪ for lofi while you study.
- **池 Pond**: your ducks floating on a pond, by day, week, month or year. They spread out across the water and bob
  gently; the more there are, the smaller they're drawn. Tap a duck to see its session. Pick the pond in Settings:
  the classic one, spring, autumn, winter, night, a Japanese garden, sakura, Halloween, Thanksgiving, Christmas, or one
  that follows the seasons (with the holiday ponds around their days). Add decorations if you like: a torii gate, a
  stone lantern, koi, floating lanterns and lotus. The ducks float around them.
- **共 Together**: study with friends, with nothing for them to install. Join someone's session halfway through with any
  duck, leave whenever you like, and everyone keeps a duck for the time they put in. Each group has its own pond of the
  ducks you hatched together, with a small badge on each duck saying whose it is, and a weekly leaderboard, hours,
  streaks and what everyone studied.
- **記録 Stats**: your rank seal (卵 egg up to 鴨仙 duck sage), hours, ducks, streaks, the week, daily bars, a year of
  consistency, tags, time of day, the duck collection, your year so far, achievements and Anki.
  **Share** makes a picture for friends, of your stats or of your year.
- **履歴 Log**: every session by day. Log time you studied without the timer, edit or delete anything.
- **設定 Settings**: your name, colour and badge, daily goal, quick picks, tags and colours, the theme, the pond and its
  decorations, events, notifications, devices, people & groups, passcode, export and import.
- **行事 Events**: Halloween, Thanksgiving and Christmas, any time of year. Each one sets the colours and the pond together,
  with bats, falling leaves or snow drifting past. Tap it again to go back to your own theme and pond.
- **Sunday recap**: on Sunday evening, a notification with your week: time studied, ducks and your best day. Turn it off
  in Settings → Notifications.

## The streak rule

A day counts once you reach your daily goal. Missing a **weekday** breaks the streak; weekends never do, and studying on
one still adds a day. Today never breaks it, because it isn't over yet. Days are counted in your home time zone
(Settings), so travelling doesn't scramble them.

**Streak freezes:** every 7 days in a row earn one, and you can hold 2. A missed weekday uses one up instead of breaking
the streak (it doesn't add a day). The streak in Hatch and Stats shows ❄ when you have one, and the consistency chart marks
the days a freeze covered. Genkan's own streak doesn't count freezes yet.

## Where to open it

| Where you are | Address |
|---|---|
| On this PC | http://localhost:8640 (no sign-in needed) |
| Anywhere, with Tailscale on | http://your-pc.your-tailnet.ts.net:8640 |
| Anywhere, secure (after running the script below) | https://your-pc.your-tailnet.ts.net |
| At home on Wi-Fi | http://192.168.1.20:8640 |
| Friends you invite (after `enable-friends.sh`, below) | https://your-pc.your-tailnet.ts.net:8443 |

Tailscale is already set up on this PC. Your iPhone and Mac need the Tailscale app switched on to reach Dakku from
outside home. Traffic stays inside your private tailnet; nothing is open to the internet, except the friends' door if
you open it, which only lets in people you invite.

Dakku is only reachable while this PC is awake, so it shouldn't suspend: `~/mori/scripts/always-on.sh` switches suspend
off for good, turns the screens off after 5 idle minutes instead, and adds **Ctrl+Super+Page Down** (the GMMK Pro's Page Down key
sends End, so the shortcut is Ctrl+Super+End) and a **Screens off** app that darken them right away (`… undo` brings suspend back).

On this PC, Dakku is on the dock: it opens in its own Brave window, and right-clicking it offers the Pond, your Stats
and the demo. `~/mori/scripts/install-shortcut.sh` puts it back if it's ever gone (`… remove` takes it off).

### Add your iPhone

1. Switch on the Tailscale app on the phone.
2. Open the address in Safari (on the PC: Settings → **Add a device** shows a QR code to scan).
3. Share → **Add to Home Screen**, then open Dakku from the Home Screen.
4. Type the 6-digit pairing code from the PC (Settings → Add a device). Codes work once, for 10 minutes.
   The five-word passcode works too (Settings → Show passcode, on this PC). It's also in `data/passcode.txt`.

### The secure address (recommended)

Notifications on iPhone ("your duck hatched", the daily reminder) and opening Dakku with no connection both need https.
Run this once on the PC. It asks you to switch on HTTPS certificates in the Tailscale admin page (one click) and for
your password once:

```bash
~/mori/scripts/enable-https.sh
```

Then use https://your-pc.your-tailnet.ts.net on your devices, and turn on notifications in Settings. To undo it, run
`tailscale serve --https=443 off`.

## Studying together

Friends get their own Dakku on your PC: their own pond, stats and settings, next to yours. They don't need Tailscale or
an account, just a link from you.

1. Once, on the PC (it may ask you to switch Funnel on in Tailscale: one click):

   ```bash
   ~/mori/scripts/enable-friends.sh
   ```

   It opens a separate door for friends at https://your-pc.your-tailnet.ts.net:8443 with Tailscale Funnel. Your own
   address stays private.
2. In Dakku: 共 **Together** → **New group**, then **Invite**, and send the link (or show the QR code).
3. They open it and pick a name, a colour and a badge (a letter or an emoji), and they're in. On iPhone they can add
   it to the Home Screen too; there it asks for the 6-digit code from Dakku in Safari (Settings → Add a device).

Then:

- **Join in the middle.** Your sessions are open to your groups ("Friends can join this session", under the timer).
  Anyone in a group with you sees it live on their Hatch tab with a **Join** button, picks any duck and a tag, and
  studies along. They can leave whenever they like and keep a duck for the time they put in (giving up leaves a cold
  egg); if they stay to the end, everyone's duck hatches when yours does. Start a 2-hour session, have someone join an
  hour in, and you get your 2-hour duck while they get their 1-hour one. Friends' sessions can be joined the same way.
  Notifications say when a friend starts studying (Settings → Notifications) and when someone joins you.
- **Cheers.** Tap **Cheer** next to someone studying (on Hatch or Together) and send a quick cheer or your own words.
  It pops up over their egg and on their phone (Settings → Notifications → Cheers from friends switches that off),
  and the card for their duck says who cheered them on. Anyone who could join a session can cheer it.
- **A pond for each group**: only the ducks from sessions you studied together, each with a small round badge in its
  owner's colour and mark, and a legend. Your own pond is still all yours. Each group can have its own pond picture.
- **The group's stats**: a leaderboard for the week, month or all time, with today, streaks, ducks and time spent
  together, and the tags everyone studied.
- **What friends see**: their own sessions, and in a group, its pond and stats. Never your settings, devices, passcode,
  Anki or data. Your passcode and pairing codes don't work at the friends' door, and nobody there counts as this PC.
- **Keeping an eye on it**: Settings → **People & groups** lists everyone with their devices, when they were last seen
  and how much they studied; make a sign-in link for a friend's new phone, take back unused invites, or remove someone
  (which signs them out; their ducks are kept). `journalctl --user -u mori -f` logs every sign-in and join.
  `~/mori/scripts/enable-friends.sh off` closes the friends' door again.

## Running it

Install it once as a user service. It then starts with the PC (even before you log in) and restarts itself if it
ever stops:

```bash
~/mori/scripts/install-service.sh
```

After that:

```bash
systemctl --user status mori      # is it running?
journalctl --user -u mori -f      # its log
systemctl --user restart mori     # after changing the code
```

To run it by hand instead: `cd ~/mori && python3 -m mori`.

Settings come from the environment: `MORI_PORT` (8640), `MORI_HOST` (0.0.0.0), `MORI_DATA` (`./data`),
`MORI_BACKUPS` (`~/Documents/Homepage/Dakku backups`), `MORI_ANKI` (http://127.0.0.1:8765), `MORI_FRIENDS_PORT` (8643,
the friends' door, only reachable from this PC itself) and `MORI_FRIENDS_URL` (the friends' address in invite links,
if it isn't Tailscale Funnel's).

## Your data

- Everything lives in `data/mori.db` (SQLite). `data/` is private (folder mode 700) and stays out of git.
- Every day Dakku saves `dakku-YYYY-MM-DD.db` and a readable `.json` to `~/Documents/Homepage/Dakku backups` and keeps the
  last 30.
- Settings → Your data downloads everything as JSON or CSV, and imports a Dakku export or a Genkan backup.

## The Genkan homepage

Genkan syncs its study timer with Dakku: sessions you log on the homepage go to Dakku, sessions from your phone show up in
Genkan's streak and history, and a timer started on either one shows on both. If Dakku is ever down, Genkan times and logs
on its own and catches up later. The study panel shows the sync state and an **Open Dakku ↗** link.

## A demo, for showing people

Your real pond starts empty, so there's a second Dakku full of made-up ducks for showing people what a full one looks
like: about five months of sessions with every duck, a long streak and Anki numbers. It has its own data (`demo/`),
never touches yours, and opens without signing in. Its ducks are made from each day's date, so they come out the same
every time, and new ones hatch through the day, so "this week" is always full.

```bash
~/mori/scripts/demo.sh             # run it now, until Ctrl+C
~/mori/scripts/demo.sh install     # keep it running all the time, so your phone can always open it
~/mori/scripts/demo.sh uninstall   # switch that off again
~/mori/scripts/demo.sh reset       # start over with fresh made-up ducks
```

It's at http://localhost:8642 on this PC, and `http://<this-pc>.<your-tailnet>.ts.net:8642` on your phone with
Tailscale on (the script prints the exact address). It says **Demo** at the top, and leaves out devices, the passcode,
notifications and importing.

## The ducks

Forty kinds of duck, all available from the start. Each one is a single picture in `art/ducks/` (`sonic.png`,
`kirby.png`, …), finished and in Dakku's style, and a line in `art/ducks.json` with its name, kanji, colour, blurb,
face and outfit. The app and the server both take the list from there, so adding a duck needs no code changes.

### Making a new duck

```bash
python3 ~/mori/scripts/duck.py new goku "spiky black hair and an orange gi with a blue belt" --name Goku --kanji 悟
```

That adds Goku to the list and prints the exact prompt for ChatGPT (also saved in `art/prompts/goku.txt`). Add
`--angry` for Dakku's angry eyebrow. In ChatGPT, start a new chat in the **Dakku ducks** project (it has the style
rules), pick **Create image**, attach `art/reference.png` (six finished ducks to match; after the first upload it's
under + → Add from library), paste the prompt, and save the picture as `~/mori/art/incoming/goku.png`. Then:

```bash
python3 ~/mori/scripts/import_art.py
```

It finishes the picture and checks it: it takes out a white or painted-in checkerboard background, cuts out the duck,
turns it to face left if it faces right, brings the beak to Dakku's peach (`#FBBE7A`) if ChatGPT drifted, sizes it
from its body (or from its beak, when long hair or something it carries makes the outline wide), and warns about
anything it can't fix (no eye or beak found, an odd size, a nearly black outline, a body drawn lower and longer than
the others', which makes a duck look short: have ChatGPT redraw that one). The finished picture goes to
`art/ducks/goku.png` (ChatGPT's own stays in `art/originals/`), it's put in Dakku, and `art/review/goku.png` shows it
on the water next to a few other ducks, with a close-up of the face. Reload Dakku. To change a duck, open its picture
in ChatGPT and use the picture's own **Describe edits** box, save it as `art/incoming/<id>.png` again, and run the
import.

```bash
python3 ~/mori/scripts/duck.py list        # every duck
python3 ~/mori/scripts/duck.py check       # every picture against Dakku's style
python3 ~/mori/scripts/duck.py review      # all the ducks side by side, at Dakku's size (art/review/all.png)
python3 ~/mori/scripts/duck.py prompt goku # a duck's prompt again
python3 ~/mori/scripts/duck.py reference   # remakes art/reference.png from some finished ducks
```

A duck can be sized up or down with `"scale": 1.05` in `art/ducks.json` (then `duck.py publish`).

## The other pictures

The eggs (`eggs`), the pond (`pond-wide`, and optionally `pond-tall` for phones), the ripple rings (`ripples`) and the
icon (`icon`) are painted with ChatGPT from the prompts in `art/chatgpt-prompts.md`, saved in `art/incoming/` and
brought in with the same `import_art.py`. The pond is kept whole, with a map of its open water, so ducks are only ever
put where they can float: not on the bank or a lily pad. The ripple rings go under the ducks; Dakku makes them swell as
a duck bobs and sends one spreading out now and then. More ponds to choose from are `pond-spring-wide`,
`pond-autumn-wide`, `pond-winter-wide`, `pond-night-wide`, `pond-garden-wide`, `pond-sakura-wide`, `pond-halloween-wide`,
`pond-thanksgiving-wide` and `pond-christmas-wide` (each with an optional `-tall`); Settings → Pond offers whichever have
been imported. The decorations are `deco-torii`, `deco-lantern`, `deco-koi`, `deco-lanterns` and `deco-lotus`, one
picture each: Dakku finds each one a spot on the open water and keeps the ducks clear of it. Dakku decides where each duck goes and how big
it is, because that changes with every session; the pictures decide how everything looks. The first ten ducks are
drawn from simple shapes when their pictures are missing.

## Lofi

Tap ♪ by the timer and a lofi playlist plays, shuffled, with the song's name under the clock and buttons to go back,
pause and skip, and a volume slider (phones that keep the volume to their own buttons, like iPhones, don't show it).
Tap ♪ again to stop. The songs are a Spotify playlist's, but Spotify only plays whole songs to someone signed in to Spotify in
that very browser, so `scripts/lofi.py` finds each one on YouTube (the same recording, preferring the artist's own
upload, never a sped-up, slowed or hour-long version) and Dakku plays it through YouTube's player, out of sight.
iPhones only let a video make sound once it has been tapped, so there the player shows the first time, for one tap on
play, and hides again. On a phone the music may stop when the screen locks or you switch apps.

To change the songs, put Spotify track links in `art/lofi.txt` (one per line, or pasted however Spotify copies them),
then:

```bash
python3 ~/mori/scripts/lofi.py
```

It writes `web/lofi.json` and lists any song it couldn't find. Songs it found before keep their match (`--redo` looks
them all up again). Reload Dakku.

## How it's built

No dependencies, just Python's standard library and plain JavaScript.

- `mori/`: the server. `app.py` (sign-in, the shared timer, sync, notifications, backups), `web.py` (HTTP, live
  updates), `store.py` (SQLite), `logic.py` (days and streaks), `webpush.py` + `ec.py` + `aesgcm.py` (Web Push with
  its encryption, written from the RFCs), `anki.py` (AnkiConnect).
- `web/`: the app. `app.js` (everything on screen, offline-first sync), `art.js` (the ducks, eggs and the pond),
  `kinds.js` (the duck list, written by `scripts/duck.py`), `lofi.js` (♪ lofi, through YouTube's player, steered with
  messages so no YouTube script runs in Dakku), `qr.js` (QR codes), `sw.js` (offline and notifications).
- `tests/`: `python3 -m unittest discover -s tests -t .` (the API end to end, plus the crypto against the RFC 8291 and
  NIST test vectors).

Sign-in: requests from this PC itself (loopback address and host name, no proxy headers) are trusted. Everything else
signs in with the passcode or a one-time pairing code and gets a long-lived, HttpOnly cookie. Sign-in attempts are
rate-limited, and Settings → Devices signs out any device.

Friends: each person has their own sessions, settings and timer (yours are "me"). The friends' door is a second server
on 127.0.0.1:8643, which Tailscale Funnel relays from the internet. It serves only the routes friends need, never
treats anyone as this PC, has its own cookie (browsers share cookies between ports), and only accepts invites and
friends' own pairing codes. Wrong codes are limited separately at each door, so strangers can't lock you out of yours.
A session someone joins is a room: the host's session id, which each guest's session points to.
