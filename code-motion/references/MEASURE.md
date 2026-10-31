# Measurement traps — how to read a source before replicating it

> How to measure a source before you rebuild it. These are about *measuring*, not about the engine,
> so they hold in code, in After Effects or anywhere else. Engine traps live in `GOTCHAS.md`.

---

## 1 · A low residual is not evidence of the right fit

**Symptom:** an automatic circle fit returned a residual of `0.72px` over 83 points — sounds excellent.
Drawing the circle on the frame: it was **not on the rim** at all.

**Cause:** the fit was tight — to the wrong detail. Both "the brightest pixel in the row" and
"a contrast ridge" locked onto something else.

**Fix:** every geometric fit is marked `verified: false` until it is drawn on the frame and looked at.
**A measurement that confirms itself is the first suspect.**

---

## 2 · Downloading references

`yt-dlp` works for most public video pages. For Instagram, `gallery-dl --cookies-from-browser chrome` usually works for
single posts and hashtag pages (`instagram.com/explore/tags/NAME/`); profile pages are often blocked. Stock sites behind
Cloudflare (VideoHive/Envato) usually block downloads. Only download what the user is allowed to use as a reference.

---

## 3 · A rotationally symmetric object does not show rotation

**Symptom:** a round table rotated 360° and the video looked frozen.

**Cause:** a shape that looks the same from every angle does not change its silhouette.

**Fix:** ask for an **asymmetric** object — a jug with a handle, a chair, a lamp with an arm.
That is a failure in choosing the subject, not in the engine.

---

## 4 · Cropping frames from video — measure, don't guess

**Symptom:** the tip of a lamp was cut off; in another video the softboxes came into frame.

**Fix:** find the subject's bbox before cropping — scan several frames with the same green test and take the min/max.
In a video with lighting in frame, measure while ignoring the top strip.

---

## 5 · A bbox measurement contaminated by a neighbour

**Symptom:** "its letter height is 0.287" — and building by that gave a title that was too tall, half swallowed by the ball.

**Cause:** the bbox of the white pixels in the top third also included the tiny caption sitting to the right, which goes lower.
The real value was 0.2258.

**Fix:** measure **a single glyph** in a narrow x-window that contains only it.

---

## 6 · A dark seam punches through the mask, and a brightness guard does not help

**Symptom:** the black seams of a basketball were keyed out together with the green.

**Rejected cause:** "they're dark, filter by brightness." **Measured: they are as bright as the background itself** —
157 vs 151. Brightness does not separate them, checked twice.

**Fix:** topology, not colour.
- **Morphological closing** (radius 14 at 3584px) closes a narrow green channel entering from the silhouette edge. Real gaps
  are much wider and survive.
- **Hole filling** plugs a region that was keyed out and cannot be reached from the outer background.
- In what was given back — **full de-spill**, otherwise a green spot stays inside the seam.

`scripts/keycolor.py` does all three. The radius was chosen by running two options and looking at two sensitive areas,
not by estimate.

---

## 7 · The metric measured the wrong layer

**Symptom:** the eye saw the speed lines disappear after 2.4 seconds. The metric claimed they were getting stronger —
7.17 in second five vs 4.19 in second one.

**Cause:** the probe ran over an area the arm enters, and later over a pattern texture that is always on. It measured
variance, not lines.

**Fix:** a probe area that is clean background **at every moment of the film**, not just at the moment checked.
And when the metric contradicts the eye — **suspect the metric first.** Here the eye was right.

**In the replication gate too:** `replicate_gate.py`'s metrics are global per frame, so they can catch exactly the same
wrong layer — one element moves and hides that another froze (selftest 22).
⇒ `--roi NAME=x0,y0,x1,y1` on every element the brief says to keep, **in a rectangle that is clear of other elements for the
whole film** (the same rule as the probe area here).

---

## 8 · A point metric does not measure motion

In one replication the gate compared **the final frame** with the source and passed at 0.1%. The user looked and said
"his opening takes more time" — and was right: **all the motion was squeezed into 0.33 seconds**, followed by 2.7 seconds
of freeze. Identical final geometry, a completely different animation.

**The fix is a second gate on the curve:** measure size per frame over the whole loop and compare to the source curve,
with a threshold on the mean deviation. The selftest **freezes the motion** halfway and the gate must fail.

And what the measurement revealed about the original's method: **the zoom is built from two regimes** — a decelerating
exponential push until the mark closes, then **linear in scale** from 0.40 of the final size to 1.00.
A single `easeInOut` over the whole range gives exactly the freeze that was caught.

---

## 9 · Mid-shot frames are not watching

One replication built 15 shots from **one frame in the middle of each shot**. The pacing was measured and right, the palette
right, and the reaction was **"a completely different world"**.

Extracting **every frame** of the two long shots revealed two things a mid-frame cannot show, and both change the whole character:

1. **It was not a logo animation — it was a screen recording of the mark being designed.** All through the build there is a
   **mouse cursor and anchor points**, everything is built as a **thin outline**, and the colour comes in only at the end,
   **all at once**. A mid-frame catches "outline" or "filled", never the fact that someone is *editing* in front of you.
2. **The frame is not black.** A bright ceiling strip, a warm falloff, **an amber light band** and haze — the layer that gives
   it the texture of a photograph. It was measured with a row-by-row brightness profile.

**The rule:** a contact sheet answers "what is in the shot"; only a **dense sequence** answers "what happens in it".

---

The traps below were learned across several replications. They are **engine-independent** — they are about *how you measure
a source*.

---

## 10 · A profile fit mixes two effects and produces a fake third

Fitting a height profile along a section gave a **×8.36 zoom** with a low, consistent rms. It did not exist. What disproved it:
**the building widths** — 67, 68, 59 pixels, **exactly the same throughout the section**. ⇒ `a=1.000`, a pure pan.

The reason: the buildings *grew* vertically **while** the camera moved. A height profile sees both and assigns the difference
to a fake third factor. **A low rms is not evidence — it only says that the model you chose explains the numbers you fed it.**

> **The rule: measure a property that is immune to the second effect.** Width is immune to vertical growth; height is not.
> No immune property? Then there is no measurement — there are two hypotheses (§12).

**And the rule has a second side:** an immune property proves only **the measured axis**. After you disprove an effect on one
axis, ask what else is immune to the same property — the next effect can hide there. (In that case vertical drift was suspected
for this reason; **the measurement disproved it too** — the ground line was constant. But it was the right question.)

---

## 11 · The measuring area must exclude the second element

The same pattern exactly, one round later — which is why it is listed separately.

Measuring the width of a blue ring by the 6th percentile of blue pixels: a rotating needle sits **inside** the same blue,
and its glow reaches the centre ⇒ "ticks 211px long". They were built. That version was **worse** than the previous one,
4.58 vs 3.87 — the measurement was not just wrong, it made the output worse.

The fix was one line — exclude the needle's sector before measuring:
```python
dif = np.abs(((ang - na + 180) % 360) - 180)
away = (dif > 28) & (dif2 > 28) & (d > 50)
m = blue & away
```

> **A colour mask is not an object mask.** If two elements share a colour, every statistic on "the pixels of that colour"
> measures both.

**And it came back a third time — inside a gate built to catch it.** A gate reported "a leak in block A, 8.1 → 74.1".
There was no leak: block B is a **full-frame** block that starts at frame 501, before block A ends at 503 — so the check window
measured the neighbour's error. **A measuring window after an event must stop at the next event that overlaps in space.**

---

## 12 · Two hypotheses → render and measure, not "looks like it"

In one section the buildings seemed to be revealed by an **opening mask**. The eye said something else — the windows keep
their size. Instead of arguing: **render both hypotheses and measure both.** scale-Y gave an error of 21; a mask gave 74.

> When there are two hypotheses and a render costs minutes — **always render both.** Deciding by "looks like it" costs an hour;
> measuring costs two minutes.

---

## 13 · A threshold metric is a step, not a scale

Lowering a trail's opacity from 78% to 63% made the pixel count collapse by **60%**. The conclusion "the change is dramatic"
was wrong — **the core of the line simply dropped below 170**, and everything above it vanished from the count at once.
The image barely changed.

> **Counting pixels above a threshold measures the threshold.** Measure brightness (`max(RGB)`, a radial profile, an area mean) —
> a continuous quantity that moves with the image.

---

## 14 · Extract an asset from the base frame

A wordmark was extracted from frame 400 — which had already gone through +2.9% of the zoom — and then the zoom curve was applied
to it **from the start**. The result: text 2% too wide for the whole film. The right frame was 318, before the zoom begins.

> **Before extracting an asset: verify that the frame you extract from comes before any transform you are about to apply to it again.**

---

## 15 · A block that is footage in the source must be footage in the replication

A block in one source is **five** screenshots that alternate. It was built from one asset with a transform animation. MAE of the
block: **50.7**. Switching to a PNG sequence with alpha brought it down to **1.4** — 36× — without changing a single keyframe.

> **Changing content is not a transform.** Before animating a block: check whether its content is identical throughout the block.
> If not — a sequence, not an animation.

---

## 16 · "Ink" is a binary threshold — an opacity fade barely moves it

The coverage metric counts pixels below a threshold (`luma < 235`). So:

| what was done | what was expected | what happened |
|---|---|---|
| opacity down to 30% | ink drops to 30% | **barely moved** — black at 30% is luma 178, still below the threshold |
| motion sped up at the end | ink drops | **rose 1.8×** — motion blur widens every stroke and doubles the area |

Both failure directions of one principle: **ink measures area, not strength.**
- A fade changes *contrast*; it lowers the metric only when it crosses the threshold (<10%).
- Motion changes *area*; speed alone inflates the metric without the drawing changing.

⇒ A gap in the coverage curve does not necessarily mean "I drew more". Before fixing the drawing, check **speed** and
**opacity relative to the threshold**.
The isolation check that settles it in one run: turn the suspect layer off, render, and subtract. In one round the suspect came
out **0.0000** — and the search moved straight to the right cause. An unmeasured suspicion is a guess, even when it is reasonable.

---

## 17 · "The frame that looks settled" may be the extreme of a wobble

Measuring a pill in a frame that looked still gave a width of 241→**217**. The real width only arrives 10 frames later: the chosen
frame was **the minimum of the settling wobble**, not the final state.
**A single measurement does not prove stability — only a series that freezes does.** Before taking "final dimensions" from a frame,
scan the value over 20–30 frames and see that it freezes.

---

## 18 · A fixed measuring window is invalid when the container wobbles

Typing timing inside a pill came out as garbage: ink was measured in a fixed per-letter pixel window while the pill moved between
90% and 110%. ⇒ **Normalise the measuring window by the container's measured scale** in every frame. After normalising, the glyph
positions came out constant — and that itself was the finding: the text is carried by the pill, not animated separately.

---

## 19 · A detector threshold is not an opacity measurement

"The detector found 2 of 8 handles in the first frame" reads exactly like a fade-in, and a fade that does not exist got built.
Measuring **ink depth** on the same handle: 4 → 184 in one frame. A hard cut. ⇒ When you want to know "how transparent", measure
strength — do not count how many objects crossed a threshold.

---

## 20 · A single frame does not prove rest

"Four cards that land and stop" was built from one frame that looked tidy. Brightness isolation over the sequence showed **four
cards falling in sequence, rotating, and only two coming to rest**.
⇒ Before sampling a "rest layout", run nearest-neighbour tracking over the whole sequence. And frames where objects merge —
**skip them**, do not record a measurement that is really two objects.

---

## 21 · Font identification: pixel correlation measures weight, not shape

At a source resolution of 702px, correlation on a word is dictated by stroke weight and spacing — it crowned a **rounded** font that
the eye rejects instantly. The test that decided it, and is resolution-proof:
1. normalise every candidate to the measured **x-height**;
2. check the **width of 5–7 words** and the **ascender**.
The right font hits all three. A **uniform** deviation across all words = the font is narrower/wider than the source;
a **scattered** deviation = glyph differences.
Availability check: a plain `ls` on a cloud-font folder may return nothing because the files are **hidden with a dot**
(`.15708.otf`) — check the system font list, not just the disk.

---

## 22 · A colour measured as "the mean of bright pixels" is biased towards white

Measuring a glowing coloured stroke by averaging every pixel above 200 returns a colour that is too pale: the hottest pixels in a glow
are clipped towards white, and they dominate a threshold mask. ⇒ Sample hue **at the centre line of the stroke** (or take the median
hue inside a mask of mid-brightness pixels, e.g. 80–200), and measure the glow's falloff separately as a radial profile.

---

## 23 · Which fonts are actually available — ask Chrome, not the disk

The renderer draws with whatever Chrome resolves. Check before measuring a font match (run inside the engine folder):

```bash
node tools/scene-eval.mjs example "async m => { await document.fonts.ready;
  const c = new OffscreenCanvas(10, 10).getContext('2d');
  const w = f => { c.font = '64px ' + f; return c.measureText('mmmmmmmmmmlli').width; };
  return ['Inter', 'Helvetica Neue', 'Arial'].map(f =>
    [f, w('\"' + f + '\", monospace') !== w('monospace') || w('\"' + f + '\", serif') !== w('serif')]); }"
```

A font is available when text set in it measures differently from both fallbacks. ⚠️ Do **not** use `document.fonts.check` for
this — tested: it returned `true` for a font that is not installed. If the source's font is not available and cannot be licensed, pick the
closest by the test in §21, scale glyphs to the measured boxes (GOTCHAS 17), and **declare it as a deviation** in the gap log.
