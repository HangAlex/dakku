# What's new in Dakku

← [Back to the tour](README.md)

Every version, newest first. The numbers go up by a middle digit for something new to use, and by the last digit for a
fix or a touch-up. The demo at [hangalex.github.io/dakku](https://hangalex.github.io/dakku/) always runs the newest one.

## 1.19.4 · 2026-11-04

- **"Focus", not "study", across the menus.** Dakku is for work, focus and study alike, so the app says *Focusing now*,
  *Focus with friends*, *time focused*, *What everyone works on*. The ducks keep their own lines.

## 1.19.3 · 2026-11-04

- **The Dragon redrawn clean.** Same kigurumi dragon (the hood's little face and teeth, the horns, the mane, the
  pom-pom ties, the spikes, the wing and the tail), drawn again with one even line and fuller colors.

## 1.19.2 · 2026-11-04

- **Gohan** gets his angry eyebrow and a new line: *Chi-Chi said study. The universe can wait.* The eyebrow is drawn
  onto his picture by a small script (`scripts/eyebrow.py`) in the outline's own charcoal, rather than redrawn.

## 1.19.1 · 2026-11-04

- **Gustave** is the picture with the mustache above the beak and the beard under it.
- **Wittier blurbs.** Sixteen ducks' lines rewritten so none opens with who the character is: one witty line each,
  like Sonic's *Gotta study fast.*
- **The gallery keeps your place.** Back from a duck's page returns to where the grid was, with that duck in view, and
  a duck's ‹ › keep the page's scroll so the buttons stay put.

## 1.19.0 · 2026-11-03

- **Thirty-two character ducks**, each approved on its review sheet: Okabe, Hachiman, Geralt, Moogle, Leon, Taiko,
  Sciel, Harry, Gandalf, Spider-Man, Natsu, Tsuna, Nagito, Chiaki, Crono, Gohan, Estelle, Shadowheart, Astarion, 2B,
  Sakura Shinguji, Majima, Gustave, Lune, Maelle, Verso, Monoco, and the whole K-On band: Yui, Mio, Ritsu, Mugi and
  Azusa. That's over a hundred ducks.
- A duck whose outfit covers its eye (2B's blindfold, Majima's eyepatch) is drawn and checked with no eye at all.
- The review tooling that gated each candidate is in `scripts/`: `intake.sh`, `sheet.py`, `colordepth.py`.

## 1.18.2 · 2026-11-01

- A new duck's picture shows on the first visit after an update. The app used to hand the page last visit's copy of
  the picture list and refresh it only in the background, so new ducks were placeholders until the next visit.

## 1.18.1 · 2026-11-01

- **Six Final Fantasy ducks**: Tidus, Squall, Noctis, Zidane, Lightning and Terra, each redrawn until the sword lay
  across the back like Cloud's and the colors ran deep.
- **Cheers that stay on the screen.** A cheer used to pop over the egg for eight seconds and vanish, so anyone locked in
  missed it. The cheers for a session now also stay under the clock until the duck hatches: *応援 · 3 cheers for you*,
  the latest six as chips, a new one glowing as it lands.

## 1.18.0 · 2026-10-30

- **The Golden duck shines.** The rarest duck (500 hours of focus) comes with its own light wherever it's drawn: a soft
  gold glow and twinkling stars on the pond, on its tile, on its page, around the egg while it's on its way, and at
  the hatching: slow gold rays, shimmering gold letters and a fall of gold feathers and stars. The moment the hours
  reach it is marked once: *The Golden duck is yours*, straight to hatching with it.

## 1.17.0 · 2026-10-29

- **Faster and steadier doors.** Connections are kept open between requests (HTTP keep-alive, with the same deadline
  for every request so an idle one can't hold a door), headers and body go out in one write, and the app's text files
  are gzipped once ahead of the first request.
- **A clean stop.** Stopping the server takes no new requests, finishes the ones being served, ends the live updates
  and then closes the database.
- **The app opens before the PC answers**: the saved copy of the page shows at once and a fresh one loads behind it.
- Security headers, a tidy 404 for impossible paths, a write timeout treated like a dropped connection, and
  `tests/test_http.py` for all of it.

## 1.16.0 · 2026-10-28

- **Sort the ducks.** The gallery and *Choose a duck* can be sorted by shelf, recently used, yours first, by price,
  most hatched, or A to Z, each remembering its own choice on the device. A duck's ‹ › follow the order you see.
- **Read about a duck before you hatch it.** Tapping a duck in *Choose a duck* opens its page (its line, how many you've
  hatched) with *Hatch with this duck*, instead of choosing it at once. The Surprise tile still chooses at once.

## 1.15.3 · 2026-10-28

- Every duck is drawn the same size on its card. A card used to widen for a duck that reached past it (Monika's
  ponytail, Ike's sword, Denji's chainsaw), which drew that duck smaller than the rest.

## 1.15.2 · 2026-10-28

- Every duck's outline in Shiro's charcoal: a reddish-brown line had cast many ducks brown. The touched-up ducks got
  their earlier colors back, and Kuromi's hood and the Scholar's gown are a real black.

## 1.15.1 · 2026-10-28

- A duck's ‹ › go through the gallery in its order, shelf by shelf.

## 1.15.0 · 2026-10-28

- **Fifteen new ducks.** Dakku's own ducks for hours of focus, each grander than the last: the Scholar at 75 hours,
  the Knight at 100, the Dragon at 200, the Angel at 300, the Phoenix at 400 and the Golden duck at 500. A Sanrio
  shelf (Hello Kitty, Kuromi, Cinnamoroll, Pompompurin) and Totoro.
- **A fairer shop.** Dakku's own ducks cost less, and a character costs more the more there is to it: a hood or a hat,
  an outfit, or a detailed one with a sword. A mystery egg is characters only.
- **Every duck held to Shiro.** `scripts/duckgate.py` measures a duck at the size Dakku draws it against all the
  others (size, eye and beak heights, the bottom, the wing, the crayon line's grain and thickness, the white, and
  how far a redraw drifted); every duck went through it, and eleven were redrawn.

## 1.14.1 · 2026-10-28

- Settings → People & groups shows whose phone has the newest Dakku, and which devices are up to date.
- An event's painted ring lies over the timer's line, with the knob on top to grab.

## 1.14.0 · 2026-10-28

- **Friends' sessions stay live.** The PC pings every 20 seconds and a page that hears nothing reconnects; coming back
  to the app fetches friends' sessions too. Friends' pomodoros show which round and what's left of it, ticking.
- **Each other's ponds.** Tap a name or badge for someone's pond, rank, streak, hours and tags.
- **A restart prompt for updates** (*Dakku has been updated · Restart*) instead of reloading under you.
- A bigger egg: the whole inside of the dial starts it. One sign-in per phone. On iPhone, how to add Dakku to the
  Home Screen after joining in Safari.

## 1.13.0 · 2026-10-27

- **Fifty ducks**, shelved by category and series, with wittier lines.
- **Lunar New Year**, a lighter Christmas, and a painted ring around the timer for every event.
- **The duck shop, for friends**: grain for focus, spent on ducks, a mystery egg, themes, ponds and decorations.
- **Tap the egg to start.** The egg is the Hatch button.
- A note on each duck you hatch, kept with it in the log.

Older versions are in the [releases](https://github.com/HangAlex/dakku/releases).
