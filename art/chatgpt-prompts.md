# Prompts for Dakku's ducks

**New ducks are made one at a time with `scripts/duck.py`** (see SETUP.md's "Making a new duck"): it writes each
duck's prompt from the rules that worked, and finishes and checks ChatGPT's picture. The sheet prompts below are how
the first ducks were made, kept for the record; their pictures are now one per duck in `art/ducks/` (the sheets
themselves are in `art/sheets/`). The egg, pond, ripple and icon prompts are still the ones to use.

Paste these into ChatGPT one at a time, **all in the same chat** so the ducks stay consistent. With the first prompt,
**attach a style picture**: a doodle duck on blue water in the look you want (`art/style-reference.jpg` on my PC; it
isn't in the repo, since it's someone else's drawing), so ChatGPT can copy the look.
Download each picture and save it in `~/mori/art/incoming/` under the name shown (PNG, WebP or JPEG). Then run
`python3 ~/mori/scripts/import_art.py` and reload Dakku. Anything not made yet keeps its drawn placeholder.

Tips:
- If a background comes out white or as a grey checkerboard, reply: "Make the background truly transparent and give me
  the PNG again." (A plain white background works in a pinch; a checkerboard doesn't.)
- If a duck stands up or shows its feet, reply: "Redo it sitting low on the water, with no feet showing."
- If it gets too detailed or shiny, reply: "Simpler, like the attached doodle: flat colour and a sketchy outline."
- If a duck faces right, reply: "Flip it so it faces left."
- The super duck is described rather than named, because ChatGPT usually refuses to draw named characters.
- For the ripples: if they touch each other, reply "Leave clear space between the three ripples." If ChatGPT draws a
  duck in the middle, reply "Only the ripples, with no duck."
- For the pond: if ChatGPT puts ducks on it, reply "Remove the ducks: leave the water empty." If the water gets a gradient
  or shine, reply "Make the water one flat colour, with no gradient or reflections." The exact blue doesn't matter: Dakku
  finds the water in the picture itself and only puts ducks on it.

## 1. ducks-1.png (attach the style picture)

```
I'm making a cozy study app where every focus session hatches a little duck. I've attached a picture of the art style I want: please match it closely. I'll ask for several sheets in this chat, all in this same style.

Style, like the attached doodle: a soft, round, blob-shaped call duck drawn by hand. Flat pure white with no shading or highlights, a slightly wobbly dark charcoal outline that looks drawn with a soft pencil or crayon (a little grainy and uneven), one small solid black dot for its eye, and a small pale peach beak. Very simple and calm, like a Japanese doodle sticker. The duck sits low as if floating on water, the bottom of its body calm and rounded, with no feet or legs. Unlike the attached duck, it faces left, in a gentle three-quarter view. Every duck is white; outfits add the colour, in the same flat colours and sketchy outline, kept simple.

Layout: one landscape image, 1536×1024, with a truly transparent background (real alpha, no white, no checkerboard). Do not draw the water: just the ducks. They sit in one row, left to right, evenly spaced with clear space between them so they don't touch, all on the same invisible baseline about 88% of the way down. Every duck's body is the same size; hats and hair may stick up higher. No ground, shadows, text, labels or borders.

This sheet, four ducks, left to right:
1. A plain duck with no outfit at all.
2. A sailor duck: a small navy sailor collar with white stripes and a red bow, and a tiny white sailor cap.
3. A kitty duck: a soft grey cat-ear hoodie with the hood up around its face.
4. A super duck: spiky golden hair standing straight up like flames, an orange martial-arts top with a dark-blue belt, and determined little eyebrows.
```

## 2. ducks-2.png

```
Next sheet, exactly the same doodle style, size, transparent background and layout, three ducks, left to right:
1. A ninja duck: a charcoal ninja hood with a long red headband tied at the back.
2. A fox duck: a white fox mask with red markings worn tilted on the side of its head, small orange fox ears, and a red scarf.
3. A festival duck: an indigo summer yukata with a simple white wave pattern, a red obi sash, and a pink flower on its head.
```

## 3. ducks-3.png

```
Next sheet, exactly the same doodle style, size, transparent background and layout, three ducks, left to right:
1. A samurai duck: a little red samurai helmet with a golden crescent crest, and a dark-blue jacket.
2. A king duck: a small golden crown and a red cape with a white fur collar.
3. An astronaut duck: a white space suit and a round clear glass helmet bubble around its head.
```

## 3b. More ducks: ducks-4.png, ducks-5.png, ducks-6.png

Characters, named outright (ChatGPT draws these as costumes on the white duck). Same chat, with **Create image**
picked under + so it paints instead of editing with code. If it hands back a file link instead of a picture, reply
"Show the image here."

```
New sheet for Dakku, my cozy study app where every focus session hatches a little duck. Draw it in exactly the same doodle style as the duck rows earlier in this chat: a soft, round, blob-shaped white call duck drawn by hand, flat pure white with no shading, a slightly wobbly dark charcoal crayon outline, one small solid black dot eye, a small pale peach beak, sitting low as if floating on water, no feet or legs, facing left in a gentle three-quarter view. The outfits add the colour, in the same flat colours and sketchy outline, simple and cute. Layout: one landscape image, 1536x1024, with a truly transparent background (real alpha, no white, no checkerboard) and no water. The ducks sit in one row, left to right, evenly spaced with clear space between them so nothing touches, all on the same invisible baseline about 88% of the way down. Every duck's body is the same size; hair and hats may stick up higher. No ground, shadows, text, labels or borders. This sheet, four ducks, left to right: (1) Shizuku Osaka from Love Live! Nijigasaki as an idol duck: long straight dark-brown hair with neat bangs that flows down behind the duck's back, tied in a half-up ponytail with her big red ribbon bow at the back of her head, clearly visible behind it, and a light-blue idol outfit with white frills. (2) A nurse duck: a small white nurse cap with a red cross, a pale pink nurse collar and a stethoscope around its neck. (3) Senku from Dr. Stone: tall spiky upswept white hair with pale green tips, the thin stone-crack marks on one side of his face, a simple light-green caveman tunic, holding a small glass flask of bubbling green liquid. (4) Naruto: spiky bright-yellow hair, a blue Leaf Village headband with a metal plate, three whisker marks on each cheek, and an orange-and-black jacket.
```

```
Next sheet, exactly the same style, size, transparent background and layout, three ducks, left to right (the Forger family from Spy x Family): (1) Loid Forger: short neat blond hair swept to the side, a dark-green suit jacket over a black vest, a white shirt and a red tie. (2) Yor Forger as the Thorn Princess: long straight black hair with bangs and two long locks in front, a golden rose headband, a black off-the-shoulder dress with red roses, and a small gold stiletto. (3) Anya Forger: shoulder-length pink hair with her two little black cone-shaped hair ornaments on top, a smug little expression, and her black Eden Academy school dress with gold trim.
```

```
Next sheet, exactly the same style, size, transparent background and layout, three ducks, left to right: (1) Kirby: the duck stays white, wearing a cute round pink Kirby kigurumi hood that frames its own calm face and beak, with Kirby's face on top of the hood (two tall dark-blue oval eyes with a white shine, pink blush and a tiny smile), two little red Kirby feet on the hood, and a small star scarf. (2) Vegeta from Dragon Ball Z: tall black spiky flame-shaped hair with a sharp widow's peak, sharp angry frowning eyebrows and a proud scowl, a blue bodysuit with white Saiyan armour and yellow shoulder pads, and white gloves. (3) Clive Rosfield from Final Fantasy XVI: short dark-brown hair, a short dark beard, a plain dark cape over his shoulders (no fur) on his dark leather outfit, a big sword hilt over his shoulder, and a few small orange fire embers floating around him.
```

Tips from making these: to change one picture, open it and use its own **Describe edits** box (a plain "use this
latest sheet" in the chat can pick an older picture). Ask for faces to stay "the calm default dot-eye duck look", and
for no hands or arms ("only its plain white duck wing"). An angry duck's eyebrow is one straight, thin stroke in the
same soft charcoal crayon as the outlines, tilted down toward the beak, with a small gap above the eye.

```
New sheet (a brand-new image, not an edit): exactly the same doodle style, duck size and transparent background (real alpha) as the Dakku duck sheets in this chat: soft round white call ducks with the same wobbly charcoal crayon outline, one small black dot eye, a pale peach beak, sitting low as if floating, facing left. No hands, arms or feet: every duck only has its plain white duck wing. One landscape image, 1536x1024, four ducks in one row on the same baseline, evenly spaced with clear empty space between them so nothing touches (keep each sword or key inside its own duck's space). Left to right: (1) Sonic the Hedgehog: a blue Sonic hood with his big swept-back blue quills and little blue ears framing the duck's calm face, and a small gold ring floating beside it. (2) Cloud Strife from Final Fantasy VII: tall spiky blond hair, a dark navy sleeveless SOLDIER top with a silver shoulder pauldron, and his huge Buster Sword strapped upright on his back. (3) Sora from Kingdom Hearts: big spiky brown hair, a silver crown necklace, a black-and-red jacket, and the silver Kingdom Key Keyblade with its gold guard resting upright behind him. (4) Sailor Venus: long golden-blonde hair with a big red bow, a gold tiara with an orange gem, an orange choker, and her white sailor uniform with an orange collar and a blue front bow. Calm default dot-eye faces.
```

```
New sheet (a brand-new image, not an edit), the same style, size, transparent background and layout, four ducks, left to right: (1) Yu Narukami from Persona 4 Revival: neat straight silver-grey hair with a bob and bangs, and the black Yasogami High school jacket with a high collar, worn open over a white shirt. (2) Makoto Yuki from Persona 3 Reload: dark blue hair with long bangs covering one eye, the black Gekkoukan High blazer with a white shirt and red ribbon, a red S.E.E.S. armband, and headphones around his neck. (3) Joker from Persona 5: messy black curly hair, his white domino mask, and his black Phantom Thief long coat with a high collar. (4) Kazuma Kiryu from Yakuza: short slicked-back dark hair, a light grey suit over an open-collared dark red shirt, and an angry eyebrow (one straight, thin stroke in the same soft charcoal crayon as the outline, tilted toward the beak, with a small gap above the eye). Calm dot-eye faces otherwise.
```

## 4. eggs.png

```
Next sheet, same doodle style, size and transparent background: four separate pictures in one row on the same baseline, with clear space between them:
1. A smooth cream-white egg sitting in a small round straw nest.
2. The same egg in its nest with a small zig-zag crack.
3. The same egg with a big crack across the top and a little duckling's eyes peeking out of the dark gap.
4. A cold egg: pale grey-blue, cracked, with a few frosty sparkles, sitting on a green lily pad instead of a nest.
```

## 5. pond-wide.png

```
Now the pond the ducks float in, in exactly the same doodle style as the ducks: flat colours and the same soft, slightly wobbly charcoal outline, with no shading or gradients.

One landscape image, 1536×1024, with a truly transparent background outside the pond (real alpha, no white, no checkerboard).

A wide, softly rounded, slightly irregular pond seen from a little above, filling almost the whole picture with just a small transparent margin. The water is one flat periwinkle blue, like the attached style picture, with a few short dark ripple dashes scattered thinly across it. Around the water, a narrow grassy bank in soft sage green, a little wider along the back (top) edge, with a few small grey stones, two or three small clumps of reeds or cattails, and a couple of tiny flowers, all kept sparse and simple.

Leave the water open and empty, because I'll put the ducks on it myself: no ducks or other animals, no people, no text, no bridge, and nothing in the middle of the water. Two or three small lily pads close to the shore are fine, one with a little pink lotus flower.
```

## 6. pond-tall.png (optional: a taller pond for your phone)

```
The same pond again for phones: the same style, colours and details, but as a portrait image, 1024×1536, with the pond taller than it is wide. Keep the water open and empty in the same way.
```

Without this one, phones use the wide pond.

## 7. ripples.png

```
Next, the ripples a duck makes floating on the water, to go under each duck on the pond. Same doodle style and colours as the pond's ripple dashes, on a truly transparent background (real alpha, no white, no checkerboard). One landscape image, 1536×1024.

Three separate ripple rings in one row, evenly spaced, with clear transparent space between them, each about a quarter of the picture wide. Each one is two or three flat, wide, slightly wobbly oval rings around an empty middle, as if spreading out from a duck floating there (don't draw the duck), seen from a little above like the pond, about four times as wide as they are tall: soft pale blue, almost white lines, with a couple of short dark-blue ripple dashes near the ends. Keep them simple, light and a little different from each other.
```

Dakku puts one under every duck, so the duck hides the back of the ring, then makes it swell as the duck bobs and
sends a ring spreading out every so often.

## 8. icon.png

```
Last one: an app icon in the same doodle style. The plain duck from the first sheet, floating in the middle of periwinkle-blue water (#A4BEDF) with a few short dark ripple dashes, just like the attached picture, filling most of the square. 1024×1024, fully opaque, no text and no border.
```

## 9. More ponds (optional)

Dakku can float your ducks on other ponds too: pick one in Settings → Pond (and a group's pond in People & groups).
Ask for these in the same chat, after pond-wide, so they keep its style and shape. Or start a new chat for each one in
the "Dakku ducks" project with `pond-wide.png` attached, and begin the prompt with: *Attached is the pond from my study
app Dakku, where little doodle ducks float on the water.* (That's how the ones in Dakku now were made.) Each theme has a wide picture and an
optional tall one for phones, named as shown. Make as many or as few as you like: Settings only offers the ponds you've
imported. **Seasonal** changes with the month (spring from March, the classic pond in summer, autumn from September,
winter from December), using the classic pond for any season you haven't made.

### pond-spring-wide.png

```
The same pond again, in spring: the same doodle style, size, shape and truly transparent background, and the water still one flat periwinkle blue, open and empty in the middle. On the bank: fresh light-green grass, a small cherry tree leaning in at one back corner with pale pink blossoms, a few small tulips and daisies, and a handful of fallen pink petals floating near the shore only. No ducks, animals, people, text or bridge.
```

### pond-autumn-wide.png

```
The same pond again, in autumn: the same doodle style, size, shape and truly transparent background, and the water still one flat blue, open and empty in the middle. On the bank: warm golden and russet grass, a small Japanese maple at one back corner with red and orange leaves, dry reeds, a couple of little mushrooms, and a few fallen leaves on the bank and floating near the shore only. No ducks, animals, people, text or bridge.
```

### pond-winter-wide.png

```
The same pond again, in winter: the same doodle style, size, shape and truly transparent background. The bank is covered in soft snow (white, with a pale grey-blue outline), with a small snowy pine at one back corner and a few snow-capped stones. A thin rim of pale ice runs along part of the shore, but most of the water stays open, one flat cool blue that's clearly darker than the snow and ice, and empty in the middle. No falling snow over the water, and no ducks, animals, people, text or bridge.
```

### pond-night-wide.png

```
The same pond again, at night: the same doodle style, size, shape and truly transparent background. The water is one flat deep navy blue, open and empty in the middle, with a soft pale reflection of the moon near one side and a few tiny star glints. The bank is dark blue-green, with dark reeds, three or four tiny glowing yellow fireflies, and a small stone lantern with a warm glow at one back corner. Keep the water clearly bluer and lighter than the dark bank. No ducks, animals, people, text or bridge.
```

### pond-garden-wide.png

```
The same pond again, as a small Japanese garden pond: the same doodle style, size, shape and truly transparent background, and the water still one flat periwinkle blue, open and empty in the middle. Around it: smooth grey stepping stones and round mossy rocks along the bank, a small stone lantern, one or two neatly clipped round shrubs, a little bamboo water spout at the back edge, and two or three lily pads with pink lotus flowers near the shore. No fish, ducks, animals, people, text or bridge.
```

### pond-sakura-wide.png

```
The same pond again, in full cherry-blossom season and as pink as can be: the same doodle style, size, shape and truly transparent background, and the water a soft flat lavender-blue, open and empty in the middle. The bank is soft pink-tinted grass covered in fallen pink petals, with two small cherry trees in full pink bloom leaning in at the back corners, a few pink and white flowers, and a scattering of pink petals floating on the water near the shore only. No ducks, animals, people, text or bridge.
```

### pond-halloween-wide.png (an event)

```
The same pond again, on Halloween night: the same doodle style, size, shape and truly transparent background. The water is one flat deep indigo blue, open and empty in the middle, with a soft pale reflection of a thin crescent moon near one side. The bank is dark purple-grey grass, with three or four small carved jack-o'-lanterns glowing warm orange, a small bare twisty black tree at one back corner, a few little purple and orange mushrooms, two or three short candles and some dry dark reeds. Keep the water clearly bluer and lighter than the dark bank. No ducks, animals, people, text or bridge.
```

### pond-thanksgiving-wide.png (an event)

```
The same pond again, at harvest time for Thanksgiving: the same doodle style, size, shape and truly transparent background, and the water still one flat blue, open and empty in the middle. On the bank: warm golden-brown grass, a small oak tree at one back corner with orange, red and yellow leaves, a little hay bale with two or three pumpkins and gourds beside it, a bundle of dried corn stalks, and fallen leaves on the bank, with a few floating near the shore only. No ducks, animals, people, text or bridge.
```

### pond-christmas-wide.png (an event)

```
The same pond again, at Christmas: the same doodle style, size, shape and truly transparent background. The bank is covered in soft snow (white, with a pale grey-blue outline), with a small Christmas tree at one back corner decorated with a gold star and a few round red and gold baubles, a string of small coloured lights along part of the back bank, two little wrapped presents with ribbons, a couple of red-and-white candy canes stuck in the snow and a few snow-capped stones. Most of the water stays open, one flat cool blue that's clearly darker than the snow, and empty in the middle. No falling snow over the water, and no ducks, animals, people, snowmen, text or bridge.
```

### The tall ones (optional, for phones)

After each wide pond you like, ask for its tall one in the same way, and save it with `-tall` instead of `-wide`
(for example `pond-night-tall.png`):

```
Now the same pond as a portrait image, 1024×1536, with the pond taller than it is wide. Keep the style, colours and details, and keep the water open and empty in the same way.
```

In a new chat, attach `pond-tall.png` too and add: *Use the attached picture only for the shape: the same portrait size
and shape of pond and bank, with the same small transparent margin. Keep this pond's own style, colours and details.*

Then run `python3 ~/mori/scripts/import_art.py` as usual: it finds each pond's water by itself, even the dark night
water, and only puts ducks where they can float.

## 10. Decorations (optional)

Things to put on the pond, picked in Settings → Pond. Start a new chat for each in the "Dakku ducks" project, attach
`pond-wide.png` as the style picture, and use this prompt with the decoration's line in it. Save each as shown.

```
Attached is the pond from my study app Dakku, where little doodle ducks float on the water. Draw one decoration to place on that pond's water, in exactly the same doodle style: flat colours and the same soft, slightly wobbly dark charcoal outline (dark grey-brown, about #342C26, never hard black), with no shading, gradients or shine, and seen from the same slight angle from above.

The decoration: {the line below}

The picture: one square image, 1024×1024, with only this one decoration, centred and filling most of the picture, on a truly transparent background (real alpha: no white, no grey checkerboard). Don't draw the water around it, the pond, any ducks, text or a shadow.
```

- `deco-torii.png`: a small red Japanese torii gate standing in the water, like the floating one at Itsukushima: two
  round vermilion pillars with black bands at their feet, a straight crossbeam, and a black top beam that curves gently
  up at both ends. The pillars end in a straight, level line at the bottom, where they go into the water.
- `deco-lantern.png`: a small grey stone lantern (tōrō) standing on a round mossy rock in the water, with a warm yellow
  light glowing in its little window and a curved stone roof. The rock's bottom is a straight, level line where it meets
  the water.
- `deco-koi.png`: two koi fish swimming side by side just under the surface, seen from above: one orange and white, one
  white with red patches, with soft flowing fins and tails, their bodies curving gently as if swimming.
- `deco-lanterns.png`: three small floating paper lanterns (tōrō nagashi) in a loose diagonal row, each a little square
  paper lantern on a small flat wooden base, glowing warm yellow-orange with a tiny flame shape inside. Their bases are
  flat, where they float on the water.
- `deco-lotus.png`: a small cluster of three round green lily pads, each with its little notch, with two pink lotus
  flowers on them: one open with pointed petals and a yellow centre, one a closed bud. Everything lies flat on the water.

Dakku finds each decoration a spot on the open water (the torii towards the back, the stone lantern and lotus near the
shore, the koi and floating lanterns out on the water) and keeps the ducks clear of it.
