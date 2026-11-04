<p align="center"><img src="media/hero.webp" alt="Dakku: a focus timer where every session hatches a little duck into your pond"></p>

<p align="center"><a href="https://hangalex.github.io/dakku/"><b>▶ Try the demo</b></a> · runs in your browser, nothing to install · <a href="CHANGELOG.md">What's new</a></p>

<p align="center">
  <img src="media/hatch.webp" width="290" alt="The last three seconds of a session on Halloween: the egg hatches into a witch duck, with jack-o'-lanterns and bats around the timer">
  &nbsp;
  <img src="media/pond-phone.png" width="290" alt="A month of ducks floating on the Lunar New Year pond">
</p>

I study a lot (networking certs, Japanese, whatever else I'm into that month), and every focus app I tried was either
a subscription or a wall of charts. So I made my own. Start a timer and an egg sits in its nest. Stay focused and it
wobbles, cracks at half time, peeks out near the end, then hatches. Give up and the egg goes cold. Every duck you hatch
floats on your pond, so after a few weeks there's a whole crowd of them bobbing around.

It runs on my own PC at home and I use it every day as an app on my iPhone, for work and for study alike. Playing
around with the idea of having others use it too.

My goal is to build long-term focus habits one duck at a time!

## Try it

**[hangalex.github.io/dakku](https://hangalex.github.io/dakku/)**: a playable demo, full of made-up ducks, that runs
right in your browser, on your phone or your computer. Start a timer and hatch a duck, join Mina while she focuses,
switch on Halloween. Everything is unlocked there: every duck, theme, pond and event, any day of the year. Nothing
you do leaves your device. On a computer, just open the link; on a phone, scan the code below.

**On a phone, for the best experience:** open the link in **Safari** (iPhone) or **Chrome** (Android), not inside another app like Instagram or Discord, then add it to your Home Screen: on iPhone tap Share → **Add to Home Screen**, on Android tap ⋮ → **Add to Home screen**. It then opens full-screen from its own icon, like an app.

<p align="center"><img src="media/demo-qr.png" width="240" alt="QR code for the demo: hangalex.github.io/dakku"></p>

> **Status:** a personal project I'm still building. The code is all here; [SETUP.md](SETUP.md) explains how to run it
> and how it works, and [CHANGELOG.md](CHANGELOG.md) says what changed in each version.

---

## On a computer

<p align="center"><img src="media/desk-pond.png" alt="Dakku in a browser on a computer: a month of ducks on the sakura pond, in the Sakura theme"></p>

It's the same app on my laptop, in the browser or installed as an app, and it stays in sync with my phone: start a
session on one and it's running on the other. The big screen is where the pond really shines.

<p align="center"><img src="media/desk-together.png" alt="Together on a computer: Mina focusing now, with Cheer and Join, and the club's pond with everyone's ducks"></p>

## The pond

<p align="center"><img src="media/pond.webp" alt="A month of ducks bobbing on the garden pond, with a torii gate, koi, floating lanterns and lotus"></p>

Every session is a duck. The pond shows a day, week, month or year of them, spread out across the open water and
gently bobbing, with ripples that swell as they dip. The more ducks there are, the smaller they get, so a whole year
still fits. Tap any duck to see the session it came from.

### Eleven ponds to choose from

<p align="center"><img src="media/ponds.webp" width="760" alt="The same ducks on each pond in turn"></p>

Classic, spring, sakura, autumn, winter, night, a Japanese garden, and four holiday ponds: Halloween, Thanksgiving,
Christmas and Lunar New Year. There's also a seasonal option that changes with the seasons by itself, and more ponds
are on the way.

<p align="center"><img src="media/ponds.png" alt="All eleven ponds side by side"></p>

### Decorations

<p align="center"><img src="media/decorations.png" width="720" alt="A torii gate, stone lantern, koi, floating lanterns and lotus on the garden pond"></p>

A torii gate standing in the water, a stone lantern, koi swimming under the surface, floating paper lanterns and lotus.
Turn on as many as you like. Each one finds its own spot on the water and the ducks float around it.

## Over a hundred ducks

<p align="center"><img src="media/ducks.png" alt="Every duck, shelf by shelf: Dakku's own, the holidays, Sanrio and friends, anime, games, film and TV, and music"></p>

Pick a duck before you start, or let it be a surprise. There are over a hundred of them now, all drawn by the same
hand as the plain white duck at the top: Dakku's own (a sailor, a ninja, a fox mask from the shrine festival, an
astronaut, a scholar, a knight, a dragon, an angel, a phoenix…), fan-art outfits of characters I like from games
and anime (Goku, Cloud, Link, Geralt, 2B, the whole K-On band, the Final Fantasy heroes, the Clair Obscur
expedition…), Sanrio, and holiday ones like a witch, a pilgrim and Santa. Every new duck goes through the same
check before it's let in (`scripts/duckgate.py` measures it against all the others: size, the height of its eye and
beak, the crayon line, the colors), so the pond stays one picture.

<p align="center">
  <img src="media/gallery.png" width="290" alt="The duck gallery at the anime shelf">
  &nbsp;
  <img src="media/duck-page.png" width="290" alt="Gohan's page in the gallery: his line, how many you've hatched, Hatch with this duck, and arrows to the next duck">
</p>

The gallery is shelved by category and series, with a little line about every duck and how many of each you've
hatched. Tap one to read about it, flip through its neighbours with ‹ ›, and hatch with it from right there.

<p align="center">
  <img src="media/gallery-az.png" width="290" alt="The gallery sorted A to Z">
  &nbsp;
  <img src="media/picker.png" width="290" alt="Choose a duck before you start, or the Surprise tile for a new one each time">
</p>

Sort the ducks by shelf, recently used, most hatched or A to Z (and, with the shop on, yours first or by price).
Before a session, *Choose a duck* shows the same shelves with a Surprise tile on top.

### The Golden duck

<p align="center">
  <img src="media/golden.webp" width="290" alt="The Golden duck hatching: slow gold rays, shimmering gold letters and a fall of gold feathers and stars">
  &nbsp;
  <img src="media/golden-page.png" width="290" alt="The Golden duck's page in the gallery, with its rays">
</p>

The rarest duck comes with five hundred hours of focus, and it brings its own light wherever it's drawn: a soft gold
glow and twinkling stars on the pond, on its tile, around the egg while it's on its way, and at the hatching, with
gold rays and a fall of gold feathers.

## Holiday events

<p align="center">
  <img src="media/event-halloween.webp" width="200" alt="Halloween: thorny vines, jack-o'-lanterns and bats around the timer, then bats flying past the Halloween pond">
  <img src="media/event-thanksgiving.webp" width="200" alt="Thanksgiving: a harvest wreath around the timer, then leaves falling over the harvest pond">
  <img src="media/event-christmas.webp" width="200" alt="Christmas: a wreath with lights around the timer on a snowy light theme, then the Christmas pond">
  <img src="media/event-lunar.webp" width="200" alt="Lunar New Year: red lanterns and plum blossoms around the timer, then the Lunar New Year pond">
</p>

Halloween, Thanksgiving, Christmas and Lunar New Year each change the colors, the pond and the timer together. A
painted ring goes around the timer (thorny vines with jack-o'-lanterns, a harvest wreath, a wreath strung with
Christmas lights, red lanterns and plum blossoms), and bats, falling leaves, snow or plum petals drift past. Christmas
is a light, snowy theme. Each one comes on by itself when its holiday starts (Lunar New Year from a week before it
until the Lantern Festival) and goes when it ends, and you can turn one on any time of year and tap it again to go
back.

## Themes

<p align="center"><img src="media/themes.png" alt="The Ai, Sumi, Yozakura and Sakura themes"></p>

Named after traditional Japanese colors: 藍 Ai (indigo), 墨 Sumi (ink), 夜桜 Yozakura (cherry blossoms at night) and
桜 Sakura, a soft pink light theme with petals drifting down.

## Focusing together

<p align="center">
  <img src="media/join.webp" width="260" alt="Joining Mina's session halfway through with a Kirby duck">
  <img src="media/send-cheer.webp" width="260" alt="Sending Mina a cheer: quick picks like Proud of you and 頑張って！, or your own words">
  <img src="media/cheer.webp" width="260" alt="A cheer from Mina popping up over the egg, then settling into the tray under the clock">
</p>

My friends get their own Dakku on my PC through a link, with nothing to install and no account. When one of us is
focusing, the others can **join** halfway through with any duck and leave whenever they like, and everyone keeps a
duck for the time they put in. You can also send a **cheer** that pops up over their egg and on their phone, and
stays under their clock until the duck hatches, so nobody locked in misses one. Each group has its own pond of the
ducks we hatched together, with a little badge on each saying whose it is, plus a weekly leaderboard, and you can
tap anyone's name for their pond, rank, streak and hours.

<p align="center">
  <img src="media/together.png" width="290" alt="Together: who's focusing now, the club's pond and the week's leaderboard">
  &nbsp;
  <img src="media/cheers.png" width="290" alt="The cheers for a session, kept under the clock until the duck hatches">
</p>

Friends' sessions stay live: a pomodoro shows which round and what's left of it, ticking, and the app tells you when
someone starts so you can join them.

## The duck shop

My friends earn their ducks, so their collection grows with the hours they put in. Every session they finish with the
timer earns grain 🌾: more a minute the longer the session, a little extra for focusing together, and a bonus for each
day they reach their goal. The plain ducks come with hours of focus, and the rest are in the gallery's shop with a
mystery egg, the themes, the ponds and the pond decorations: a hood or a hat costs less than a full outfit, and a
detailed one with a sword costs the most. Holiday ducks are free in their month, and a season's pond is free while
that season lasts. For a big pile of grain a friend can ask me for a brand-new duck: I paint it, they get it, and it
joins the shop for everyone. It's a switch in Settings (on for friends, and for me too if I want to earn mine), and
the demo has none of it: everything's unlocked there. The rates and prices are in [SETUP.md](SETUP.md).

## Stats

<p align="center">
  <img src="media/stats.png" width="290" alt="Stats: rank seal, hours, ducks, streaks, this week and daily focus">
  &nbsp;
  <img src="media/year.png" width="290" alt="This year so far, with a bar for each month">
</p>

- A rank seal that grows with your hours, from 卵 egg to 鴨仙 duck sage
- Streaks with a weekday rule: weekends never break one, and every 7 days in a row earns a **streak freeze** that covers
  a missed weekday
- The week, daily focus, a year of consistency, tags, time of day, achievements and my Anki reviews
- **Your year so far**, with a picture of it to share

<p align="center"><img src="media/year-card.png" width="360" alt="The shareable year picture"></p>

## Little things

- **Timer, pomodoro or stopwatch.** Drag the ring to pick a time, or use a quick pick, then tap the egg to start.
- **♪ Lofi.** One tap shuffles my lofi playlist while I focus: just the music and the song's name, with play/pause,
  skip and volume.
- **Notifications** when a duck hatches, a nudge if I haven't hit my goal yet, friends starting to focus, and a
  Sunday-evening recap of the week: time focused, ducks and my best day.
- **Offline first.** Log a session on the train and it syncs when I'm back online. The app opens from its saved copy
  at once and fetches a fresh one behind it.
- **Updates ask first.** When the PC has a newer Dakku, the app says so and offers a restart instead of reloading
  under you, and Settings shows which of your devices (and which friends) have it.
- **My browser homepage** shows the same timer and streak, so starting a session on my phone shows up on my PC too.

## How it runs

Dakku is self-hosted: a small server on my home PC with my phone and laptop talking to it, so my data stays mine. The
server is plain Python with no dependencies (it keeps connections open between requests, gzips the app once ahead of
time and stops cleanly), and the app is a progressive web app added to my iPhone's home screen. Friends reach it
through an invite link.

## Run it yourself

You need Python 3 and nothing else (I run it on 3.14). To try it with a pond full of made-up ducks (that's what all the
screenshots here are from):

```bash
python3 -m dakku --demo
```

Then open http://localhost:8642. For the real thing, on your own PC with your phone, see [SETUP.md](SETUP.md).

## What's in here

| Folder | What's in it |
|---|---|
| [`web/`](web) | The app you see on your phone and computer |
| [`dakku/`](dakku) | The server, in plain Python |
| [`art/`](art) | The duck art, the prompts that made it, and the lofi playlist |
| [`scripts/`](scripts) | Setup scripts, the art tools and the demo builder |
| [`tests/`](tests) | The tests |
| [`systemd/`](systemd) | The background services that keep it running |
| [`media/`](media) | The screenshots and animations on this page |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed in each version |

---

<sub>Dakku is a personal, non-commercial project. The character outfits are fan art: those characters belong to their
creators and owners.</sub>
