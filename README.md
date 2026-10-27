<p align="center"><img src="media/hero.webp" alt="Dakku: a study timer where every focus session hatches a little duck into your pond"></p>

<p align="center">
  <img src="media/hatch.webp" width="290" alt="An egg cracking open and hatching into a witch duck as the timer runs out">
  &nbsp;
  <img src="media/pond-phone.png" width="290" alt="A month of ducks floating on the pond">
</p>

I study a lot (networking certs, Japanese, whatever else I'm into that month), and every focus app I tried was either
a subscription or a wall of charts. So I made my own. Start a timer and an egg sits in its nest. Stay focused and it
wobbles, cracks at half time, peeks out near the end, then hatches. Give up and the egg goes cold. Every duck you hatch
floats on your pond, so after a few weeks of studying there's a whole crowd of them bobbing around.

It runs on my own PC at home and I use it every day as an app on my iPhone. Playing around with the idea of having others use it too

My goal is to build long term study habits one duck at a time!

> **Status:** a personal project I'm still building. The code is all here; [SETUP.md](SETUP.md) explains how to run it
> and how it works.

---

## On a computer

<p align="center"><img src="media/desk-pond.png" alt="Dakku in a browser on a computer: a month of ducks on the pond"></p>

It's the same app on my laptop, in the browser or installed as an app, and it stays in sync with my phone: start a
session on one and it's running on the other. The big screen is where the pond really shines.

<p align="center"><img src="media/desk-together.png" alt="Together on a computer: Mina studying now, with Cheer and Join, and the study club's pond with everyone's ducks"></p>

## The pond

<p align="center"><img src="media/pond.webp" alt="A month of ducks bobbing on the garden pond, with a torii gate, koi, floating lanterns and lotus"></p>

Every session is a duck. The pond shows a day, week, month or year of them, spread out across the open water and
gently bobbing, with ripples that swell as they dip. The more ducks there are, the smaller they get, so a whole year
still fits. Tap any duck to see the session it came from.

### Ten ponds to choose from

<p align="center"><img src="media/ponds.webp" width="760" alt="The same ducks on each pond in turn"></p>

Classic, spring, sakura, autumn, winter, night, a Japanese garden, and three holiday ponds: Halloween, Thanksgiving and
Christmas. There's also a seasonal option that changes with the month and turns into the holiday ponds around the
holidays.

<p align="center"><img src="media/ponds.png" alt="All ten ponds side by side"></p>

### Decorations

<p align="center"><img src="media/decorations.png" width="720" alt="A torii gate, stone lantern, koi, floating lanterns and lotus on the garden pond"></p>

A torii gate standing in the water, a stone lantern, koi swimming under the surface, floating paper lanterns and lotus.
Turn on as many as you like. Each one finds its own spot on the water and the ducks float around it.

## Forty ducks

<p align="center">
  <img src="media/gallery.png" width="290" alt="The duck gallery">
  &nbsp;
  <img src="media/godzilla.png" width="290" alt="The Godzilla duck enlarged in the gallery: King of the Monsters, and of the pond.">
</p>

Pick a duck before you start, or let it be a surprise. There are forty of them: Dakku's own ten (a sailor, a ninja, a
fox mask from the shrine festival, an astronaut…), fan-art outfits of characters I like from games and anime, and
holiday ones like a witch, a pilgrim and Santa. The gallery shows how many of each you've hatched, with a little line
about every one.

## Holiday events

<p align="center">
  <img src="media/event-halloween.webp" width="260" alt="Halloween: bats flying past the Halloween pond">
  <img src="media/event-thanksgiving.webp" width="260" alt="Thanksgiving: leaves falling over the harvest pond">
  <img src="media/event-christmas.webp" width="260" alt="Christmas: snow falling over the timer">
</p>

Halloween, Thanksgiving and Christmas each change the colours and the pond together, with bats, falling leaves or snow
drifting past. You can turn one on any time of year, and tap it again to go back.

## Themes

<p align="center"><img src="media/themes.png" alt="The Ai, Sumi, Yozakura and Sakura themes"></p>

Named after traditional Japanese colours: 藍 Ai (indigo), 墨 Sumi (ink), 夜桜 Yozakura (cherry blossoms at night) and
桜 Sakura, a soft pink light theme with petals drifting down.

## Studying together

<p align="center">
  <img src="media/join.webp" width="260" alt="Joining Mina's session halfway through with a Kirby duck">
  <img src="media/send-cheer.webp" width="260" alt="Sending Mina a cheer: quick picks like Proud of you and 頑張って！, or your own words">
  <img src="media/cheer.webp" width="260" alt="A cheer from Mina popping up over the egg while studying">
</p>

My friends get their own Dakku on my PC through a link, with nothing to install and no account. When one of us is
studying, the others can **join** halfway through with any duck and leave whenever they like, and everyone keeps a duck
for the time they put in. You can also send a **cheer** that pops up over their egg and on their phone. Each group has
its own pond of the ducks we hatched together, with a little badge on each saying whose it is, plus a weekly
leaderboard.

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

- **Timer, pomodoro or stopwatch.** Drag the ring to pick a time, or use a quick pick.
- **♪ Lofi.** One tap shuffles my lofi playlist while I study: just the music and the song's name, with play/pause,
  skip and volume.
- **Notifications** when a duck hatches, a nudge if I haven't hit my goal yet, friends starting to study, and a
  Sunday-evening recap of the week: time studied, ducks and my best day.
- **Offline first.** Log a session on the train and it syncs when I'm back online.
- **My browser homepage** shows the same timer and streak, so starting a session on my phone shows up on my PC too.

## How it runs

Dakku is self-hosted: a small server on my home PC with my phone and laptop talking to it, so my data stays mine. The
server is plain Python with no dependencies, and the app is a progressive web app added to my iPhone's home screen.
Friends reach it through an invite link.

## Run it yourself

You need Python 3 and nothing else (I run it on 3.14). To try it with a pond full of made-up ducks (that's what all the
screenshots here are from):

```bash
python3 -m mori --demo
```

Then open http://localhost:8642. For the real thing, on your own PC with your phone, see [SETUP.md](SETUP.md).

## What's in here

| Folder | What's in it |
|---|---|
| [`web/`](web) | The app you see on your phone and computer |
| [`mori/`](mori) | The server, in plain Python (the folder still has Dakku's old name) |
| [`art/`](art) | The duck art, the prompts that made it, and the lofi playlist |
| [`scripts/`](scripts) | Setup scripts, and the tools that make the art |
| [`tests/`](tests) | The tests |
| [`systemd/`](systemd) | The background services that keep it running |
| [`media/`](media) | The screenshots and animations on this page |

---

<sub>Dakku is a personal, non-commercial project. The character outfits are fan art: those characters belong to their
creators and owners.</sub>
