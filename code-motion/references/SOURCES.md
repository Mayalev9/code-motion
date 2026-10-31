# SOURCES — what is actually inside the motion pieces worth replicating

> **What this is:** profiles of eleven real product-motion videos that were replicated with this engine — what is in them in
> practice, with concrete moments. **It is not one look:** they differ from each other, and that is documented in §Differences.
> Use it to know **what to look for** in a new source — never as a look to copy.
>
> **How the profiles were collected:** a contact sheet of each video (48 cells over its whole length) · `measure.py` at the source
> rate (segments · brightness · palette) · audio measurement (`ebur128` · silence · attacks · spectral centroid).
> ⚠️ "Sound" here = numbers, not listening. A contact sheet is an overview — it does not show easing, a short freeze or sync.
> **Times marked "~" were read from a sheet cell (±0.5s).**
> ⚠️ `measure.py` "segments" = visual jumps. In a fast, continuous camera move every frame is a "segment"; in a 2×2 grid it is a
> change in one quadrant.
>
> ⛔ **The source is the yardstick — not this doc and not an earlier replication.** In every new replication, measure its own source.

## Profiling a new source — the template

For each source, write down:
- **Structure:** the sections in order, with times.
- **Typography:** font class, weight, size, how text enters (word by word? typed? letters assembling?), which word gets the accent.
- **Pace:** segments per second, the median segment, the longest uncut shot.
- **Motion:** camera vs. object vs. text; blur = focus or motion; the animation rate vs. the file rate.
- **Material / light:** base colour, accent(s) with measured HEX, glass/grain/photo/illustration.
- **Cursor:** arrow, mac hand, none.
- **Sound (measured):** LUFS · LRA · silence share · attacks per second · or no audio channel.
- **Small details that are easy to miss:** one-frame flashes, a colour that turns on mid-shot, a frame around the frame.

---

## Revern · 1920×1080 · 25fps · 30.1s
- **Structure:** a typographic opening on black (0–3.1) → a flash → logo on light grey (3.3–5.1) → **one continuous demo of 16.6s
  with no cut** (6.7–23.3) → **a typographic burst: 4 segments of 0.48s** (23.3–25.5) → a 4.5s logo hold.
- **Typography:** letters scattered on a grid (~0–1) that assemble into "Need to know where a photo was taken?" — white, small,
  centred. In the burst: huge words in a heavy grotesque — "(SEE)" · "What" · "Others" · "Can't" — with editorial micro-text,
  crop marks and label columns (a Swiss/editorial language), alternating light/dark.
- **Pace:** 0.30 segments/s — the slowest of the set; all the energy is inside the shot (camera), and the type burst is a sharp contrast.
- **Motion:** zoom+pan over panels; a picture in a tilted card inside a circle mask; green radius circles expanding on a map;
  a map in a 3D tilt with pins. Typing in steps with a 3–4 frame jitter; a double flash on an inversion.
- **Material/light:** dark UI `#131215–#1c1d20` · **one accent — green** · floating pixel squares · black and white in the typography.
- **Sound:** −10.9 LUFS · LRA 5.1 · silence at the start · 1.3 attacks/s.
- **Easy to miss:** two white flashes on frames 1 and 3 · a picture that goes from grey to colour.

## hooklab · 1920×1080 · 60fps · 20.1s
- **Structure:** words building on warm cream (0–4.1) → a light UI card → **a switch to dark** (~4.2): a wall of UGC videos · a list of
  hooks with scores · **a 3D ring** (a cluster of 10 segments of 0.1s at 10.3–11.2 = a fast spin) · phone+panel · huge numbers → logo (16.5–20).
- **Typography:** "your / next / ad / is one **link** away" — word by word, bold black grotesque, **one word in orange**.
  At the end single huge words/numbers in the centre — 3.8x · 4.2x · $9.80 · 24 · hooks · ads · **launched** (orange), with tiny grey
  captions under them; the transition between them is a blur.
- **Pace:** 1.35 segments/s, median 0.10 (because of the ring); 60fps — very smooth motion.
- **Material/light:** a light opening with a soft pink bloom → dark `#151515` · orange-red accent `#ee464d`.
- **Sound:** −13.6 LUFS · **LRA 1.5** (heavily compressed) · silence at the start.

## Omar · 3840×2160 · 30fps (animated at 25) · 18.1s
- **Structure:** four chapters, **each with its own coloured gradient mesh on a white base**: purple (0–3.3) · blue (~3.5–6.3) ·
  green (~9.5–13.5) · blue-violet (~13.8–18).
- **Typography:** "Great · videos · aren't · accident" — **one word per shot**, bold white with blur; "They're built with purpose"
  scrolls with **a glowing purple underline and sparks**; "create content that captures attention" — small black type, typed, with a
  gradient highlight on the last word.
- **Motion:** floating cards and phones; **blur = focus, not motion** (Laplacian 3.12→1.05→5.41); **animated at 25fps and served at 30**
  (a duplicated frame at f≡1 mod 6 — measured per chapter; assuming f≡0 shifted every table by a frame) — a "not quite smooth" smoothness.
- **Material:** glassy 3D icon tiles · a money counter `$6,842,075` · chips with red dots · pill buttons.
- **Cursor:** **a big mac hand** that clicks (not an arrow).
- **Sound:** −16.8 LUFS · LRA 2.2 · 2.7 attacks/s (the densest).
- **Easy to miss:** at 3.30 the source is white and the sentence has almost left the frame — a replication had a purple gradient and a
  centred sentence there, found only by `sbs.py`.

## Leo · 3840×2160 · 60fps · 11.7s
- **Structure:** **a 2×2 grid of four independent loops** that never line up (280·232·246·174 frames).
- **Content:** "SPCX SpaceX / your name" · an orange blob "Explore" · "smarter" with **an orange arc under it** · blue 3D glass steps
  "Trade BNB at full speed" · a trading dashboard `$47,383.31 +$31,552.64` in green · "with Infinity AI ∞".
- **Material/light:** pure black (brightness 5–50) · **two accents: orange and electric blue** · thin white type.
- **Sound:** −13.3 LUFS · LRA 4.2 · **no silence at the start**.

## Bolt Forge · 1920×1080 · 25fps · 6.8s
- **Structure:** a very dense 2×2 grid in 6.8s: a warping arrow icon (TL) · a prompt box + an arrow cursor clicking a blue send button ·
  websites being generated (TR) · **huge blue-on-blue words** (BR): "Build" · "without" · "without boundaries" · "Introducing" · "bolt forge" ·
  "Up to 42x…50x the usage" (a rising counter) · "Free on every plan."
- **Material/light:** white + electric blue in soft gradients · **frosted glass** · brightness 176–228 (the brightest).
- **Pace:** no rest at all (0% holds — "reads as a loop").
- **Sound:** −11.5 LUFS · **LRA 0.9** · 3.6% silence.

## Commas · 960×540 (embedded in a larger frame) · 25fps · 43.7s · **no audio channel**
- **Structure:** a painted hill landscape that returns as a background ↔ white/blue ↔ a dashboard UI; a comma logo at the end (40.1–43.4).
- **Typography:** sentences built word by word, medium sans, **the key word in blue**: "Not **bolted** onto it." · "Up to **two affiliates**
  paid." · "Every commission **paid**." · "Every sale **credited**." · "Ours doesn't." (letters dropping) · "Automatically." in a blue pill.
- **Material:** glass cards with amounts (`$1,250.00`) over the landscape · network dots ("Two become a network") · blue halftone on the
  first frame · white-blue UI.
- **Pace:** 0.87/s, median 1.0 — a sentence every ~1s, with 0.08s flashes.
- **Easy to miss:** the painted landscape is an asset you cannot draw in code — ask for it. The failure that was caught: frozen shots.

## Blackbox · 3840×2160 · 24fps · 15.0s
- **Structure:** ASCII rain "&H$@" + "32.05 t/s" (~0) · a pixelated hexagon logo · symmetric black-and-white smoke (~2–2.5) · a pulsing
  white square · a bar chart "Gpt-5.5 / Blackbox / Grok 4.1" (~3–4.5) with **the Blackbox bar in orange** · an orange screen · grainy
  black-and-white corridor photos + "IN: $0.37 / M | OUT: $1.08" typed (~7–10) · pixels scattering into the logo · "BLACKBOX.AI" typed with
  a cursor highlight (~12.9–15).
- **Typography:** thin, small technical sans; prices typed with a "|" cursor.
- **Material/light:** black · grain · black-and-white photography · **one accent — orange**. Technical brutalism.
- **Pace:** 1.60/s, median 0.19 — **the fastest**; flashes of 0.08–0.17 (a series of brightness jumps at 9.2–10.0).
- **Sound:** **−22.2 LUFS · LRA 9.0 · 20.9% silence** — the only one built on silence and dynamics.

## Quiver · 1280×720 · 25fps · 43.9s
- **Structure:** "Arrow 2.0 is live" on light-blue grid paper · a mac window with a navigation list · **a real photo**: a hand holding a
  drawing sheet (~6–7) · a list scrolling like a slot machine with **a selection frame**: Pictograms / Labels / Illustrations / Icons /
  Technical Drawings / Typography (~7.5–15) · blue skies with a bezier curve · a terminal · **the letters "italic" drawn as vector lines** ·
  a greyhound logo, then **real embroidery on a shirt** (~17.7) · a chat "create variations" · stamps · "Preparing the paths… / Warming up the
  canvas…" · "The Creativity was always yours / We are just here to help bring it to life" · a long QuiverAI logo hold (33.8–43.9).
- **Typography:** thin, grey, small sans; larger list labels with a blue selection frame.
- **Material/light:** very bright (150–253) · light-blue line drawing · **a mix of UI + real photography + illustration**.
- **Sound:** −14.4 LUFS · LRA 6.8 · 7.5% silence.

## Habitify · **720×720 (1:1)** · 30fps · 11.4s
- **Structure:** **one UI element at a time** on light grey `~#e4e3e8`: a dark app icon → a blue "+" button that gets pressed → a pill
  "Create Good Habit" (enters tilted and straightens) → a dark card "Enter Habit…" → a tab bar → "Last 7 Days" (blue squares filling) →
  a "Read a Book" widget → an orange card with a book → a blue tick → **a glowing white logo on dark** (10.3–11.4).
- **Motion:** every element enters **with a tilt + focus blur** and straightens; a mac hand clicks. The first shot is 6.0s continuous.
- **Sound:** **−9.0 LUFS · LRA 0.8** — a compressed wall of sound.

## Trust Wallet · 2160×1556 · 60fps · 20.1s
- **Structure:** **a white card inside a light grey frame with a chapter bar at the bottom** ("Feature introduction / How it works / Outro"
  + a progress marker) — for the whole film. Inside it: "Meme · Meme trading · is · is now · **instant**" → phone screens (a list · a
  keyboard · "Paste" · a green chart · entering $100 · "Slide to Buy") → a black pill that expands → black cards "meme trading / on Trust
  Wallet / built for speed" → the TRUST logo (15.8–20).
- **Typography:** bold black geometric sans in the centre; **"instant" in blue with 3D coins**; white on black at the end.
- **Pace:** 0.50/s; a 6.2s shot at 3.3 (the flow on the phone).
- **Sound:** **−8.5 LUFS** (the loudest) · LRA 5.6.
- **Easy to miss:** the outer frame and chapter bar ARE part of the film — crop decisions depend on it.

## Grammarly · 1280×720 · 24fps · 25.5s
- **Structure:** a tiny "There always comes a moment" with a green spark (0–~2.5) → an Apple notification in perspective → **a macro on a
  white porcelain card**: "Product Designer" · text typed with a cursor · the camera tilts and moves over the text (8.0–12.3 continuous
  motion) → a mac hand clicks a send button → the page with **blue correction lines** · a green G pin that lands and bounces → logo (20.9–25.5).
- **Material/light:** **soft 3D, shallow depth of field, studio light** · cool mint-grey · porcelain white · green accent.
- **Pace:** 0.27/s — an 8.0s opening shot; everything in camera motion.
- **Sound:** −16.2 LUFS · LRA 5.0 · 7.5% silence.

---

## §Differences — why there is no one "look"

| | base | accent | pace (segments/s) | material | format | sound (LUFS · LRA) |
|---|---|---|---|---|---|---|
| Revern | dark + light burst | green | 0.30 (a 16.6s shot) | flat UI + editorial type | 16:9 | −10.9 · 5.1 |
| hooklab | light → dark | orange | 1.35 | UI + 3D + UGC | 16:9 · 60fps | −13.6 · 1.5 |
| Omar | white + a mesh per chapter | 4 chapter colours | 1.44 | glass + cards | 16:9 · 25-in-30 | −16.8 · 2.2 |
| Leo | black | orange + blue | 1.20 | 3D glass | 2×2 grid · 60fps | −13.3 · 4.2 |
| Bolt Forge | white-blue | blue | 1.18 | frosted glass | 2×2 grid | −11.5 · 0.9 |
| Commas | white + painted landscape | blue | 0.87 | landscape + glass + UI | 16:9 | **none** |
| Blackbox | black | orange | **1.60** | grain + b&w photo + ASCII | 16:9 · 24fps | **−22.2 · 9.0** |
| Quiver | very bright | sky blue | 1.07 | drawing + real photo + UI | 16:9 | −14.4 · 6.8 |
| Habitify | light grey | blue (+orange) | 0.61 | iOS UI, one element | **1:1** | **−9.0 · 0.8** |
| Trust Wallet | white in a frame | blue (+green) | 0.50 | phone UI + coins | 16:9 in a frame · 60fps | **−8.5** · 5.6 |
| Grammarly | mint grey | green | 0.27 | **soft 3D, macro, DOF** | 16:9 · 24fps | −16.2 · 5.0 |

**Light vs. dark · 0.27 vs. 1.60 segments/s · −8.5 vs. −22 LUFS (and one with no audio) · 16:9 / 1:1 / grid.**
What is right for one of them is a mistake in another. ⇒ In every replication, the numbers of **this source**.

## What recurs in most sources (an observation, with exceptions)

| recurs | where | not in |
|---|---|---|
| **one sentence spread across shots, word by word** | Revern · hooklab · Omar · Commas · Trust · Grammarly | Leo · Blackbox · Habitify · Quiver (labels) |
| **one accent colour on a neutral base**, usually on the key word | Revern · hooklab · Commas · Trust · Blackbox · Grammarly · Bolt | Omar (a colour per chapter) · Leo (two) |
| **a cursor that acts** — an arrow or a mac hand | Revern · Bolt (arrow) · Omar · Habitify · Grammarly (hand) · hooklab | Leo · Blackbox · Commas · Quiver |
| **the real interface is the image** | all except Blackbox (partly) | — |
| **focus blur as a transition** (not motion blur) | Omar · Habitify · hooklab (numbers) · Grammarly (DOF) | Blackbox (hard cuts) |
| **a long uncut ending that lands on the logo** | Revern 4.5 · Commas 3.3 · Grammarly 4.5 · Trust ~4 · Quiver 10 (loading lines → sentence → logo) | Habitify 1.1 |

⚠️ "Recurs" ≠ "always do it". It helps you know **what to look for** in a new source, not what to assume about it.
