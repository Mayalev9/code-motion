# Traps — the code-motion engine

> Every one of these was caught in a real run, not in theory.
> **Traps about measuring a source** (engine-independent): `MEASURE.md`

---

## 1 · The canvas inherits `direction` from the page

**Symptom:** Latin text drawn out of its shape to the left — `"A Cool Template"` showed up as `"l Template"`.
In Hebrew/Arabic: letters in reverse order.

**Exact cause — measured:** an `<html dir="rtl">` host page, and `ctx.direction` inherits from it. But `direction` alone is
not enough to break it: the second factor is that **the default `textAlign` is `start`**, and `start` under `rtl` means right.
Only the combination makes the text **end** at `x` instead of starting there.

Measured in Chrome, `fillText('ABCD', 100, …)` on a 400-wide canvas:

| textAlign | direction | ink |
|---|---|---|
| `start` | `rtl` | **0..98** ← the bug |
| `start` | `ltr` | 100..209 |
| `left` | `rtl` | 100..209 |

**Fix:** `resetFrame()` in `_lib.js` pins **both** — `direction='ltr'` and `textAlign='left'`. Every scene must call it first.
(This engine's `host.html` is `ltr`, but `gate.mjs` tests under `rtl` on purpose.)

⚠️ `OffscreenCanvas` inherits `direction` just like a DOM canvas — assuming it didn't is what made the first version of the
text gate pass on a deliberately injected bug.

---

## 2 · `globalAlpha` is clamped at 1

**Symptom:** `paste(ctx, layer, 1.25)` did nothing. The glow stayed weak.

**Cause:** values above 1 are silently clamped.

**Fix:** paste the same layer **twice** — `paste(l, 1); paste(l, 0.55)`. With `lighter` it adds up and burns in a bright core.

---

## 3 · A function that sets `globalCompositeOperation` itself overrides the caller

**Symptom:** the scanning light line was drawn as a solid white rectangle instead of colouring only the letters.

**Cause:** the caller set `source-atop` to clip to the letters, but `sweep()` set `lighter` inside — which overrode it.
`lighter` on transparent pixels produces colour, hence the rectangle.

**Fix:** a drawing function does not set the composite. **The caller decides.** Also: build the word in a separate layer,
so the clipping applies only to what is in that layer.

---

## 4 · Negative `t` from a motion-blur sub-sample

**Symptom:** the render crashed **only** with `--mblur`. Without motion blur it worked fine.
`drawImage: The provided value is not of type ...`

**Cause:** the first sub-sample of frame 0 gets a small negative `t`. `Math.floor(t * 24) % 4` returns `-1` → `tiles[-1]` → `undefined`.

**Fix:** a non-negative modulo: `((n % 4) + 4) % 4`.
**The rule:** every index derived from `t` must assume `t` can be negative.

---

## 5 · An upside-down `up` in `lookAt` flips handedness

**Symptom:** the whole picture in mirror writing.

**Cause:** `up = [0,-1,0]` was passed to get a downward Y like the canvas. That flips the sign of the X axis in the camera basis.

**Fix:** a standard `up = [0,1,0]`, and flip the Y sign **in the call** to the function.

---

## 6 · The camera on the wrong side of z

**Symptom:** still mirror writing, even after fixing `up`.

**Cause:** the camera sat at negative `z` looking towards `+z`. The convention is the opposite.

**Fix:** the camera at positive `z` looks towards `-z`. Objects get negative `z`.

---

## 7 · Drawing order — the hero last

**Symptom:** the icon that inflated into a title card had other icons floating inside it.

**Cause:** a `for i` loop drew the hero at index 7, and items 8–11 were drawn after it.

**Fix:** sort the loop so the hero is last.

---

## 8 · Randomness with repeats

**Symptom:** the same glyph appeared four times on screen out of eight.

**Cause:** `keys[Math.floor(r() * keys.length)]` for each item — sampling **with** replacement.

**Fix:** shuffle the array (Fisher-Yates) and take by index.

---

## 9 · A line of text that does not fit the width

**Symptom:** `PRIVATE COLLECTION` showed up as `RIVATE COLLECTIO` — cut on both sides.

**Cause:** wide letter spacing × 18 characters exceeded the frame width.

**Fix:** `fit()` — first reduce spacing to a minimum, and only then shrink the font.

---

## 10 · Canvas 2D knows no perspective

**Symptom:** "3D" cards came out flat and were rejected.

**Cause:** `setTransform` is **affine only** — it rotates and stretches, but does not foreshorten.

**Fix:** `_quad3d.js` — textures on quads in space with a perspective camera.

---

## 11 · Risograph — the paper has to breathe

**Symptom:** the result came out as a flat orange field, like a filter.

**Cause:** ink coverage too high; the separations overlapped and filled everything.

**Fix:** `a *= (1 - L * 0.55) * amt` per ink, and a dot diameter of `0.62` instead of `0.70`.
**The rule:** in riso you see the paper between the dots. If not — it is a filter.

---

## 12 · Depth — what is behind needs a positive `z`

**Symptom:** cards floated **in front of** the phone and hid the screen.

**Cause:** the quad takes `-z`, so a positive `z` in the scene = behind. The sign was reversed.

**Fix:** check the sign against the quad, not against intuition.

---

## 13 · `-shortest` cuts to the shorter stream

**Symptom:** a 13-second video came out as 8 after muxing audio.

**Cause:** the track was 8 seconds.

**Fix:** make sure the audio is longer than the video, or drop `-shortest`. (`render.mjs` pads/trims audio to the exact video length.)

---

## 14 · ffmpeg — the height must be divisible by 2

**Symptom:** `height not divisible by 2 (470x831)`.

**Fix:** round to even: `scale=470:832`.

---

## 15 · A narrow object shrinks when fitted to the width

**Symptom:** a tall, narrow lamp became a thin strip inside its letter box.

**Fix:** a per-object height multiplier. A narrow object will not collide with its neighbours, so it may exceed in height
instead of shrinking.

---

## 16 · `letterSpacing` is silently ignored on OffscreenCanvas

**Symptom:** a 9% change in the target width did not move the output by a single pixel.

**Cause:** the property is not honoured in that context — not in drawing and not in `measureText`.

**Fix:** manual glyph layout — measure each character, draw it, and advance by hand.
That also removes any doubt about whether spacing is added after the last letter or only between letters.

---

## 17 · Matching a font you do not have — stretch the letter, not the spacing

**Symptom:** the title's total width matched the reference (ratio 1.97 vs 1.96), but it looked completely different:
narrow letters with huge gaps instead of wide, dense letters.

**Cause:** closing a width gap with spacing adds **air**, not **letter**. The two posters reach the same total width in opposite ways.

**Fix:** first set the size by **letter height** — the parameter the eye reads — and then `ctx.scale(sx, 1)` on the glyphs
themselves. Choose the base font by the shape of the counters (the inner spaces).

---

## 18 · Layers without shadow do not read as layers

**Symptom:** the poster was exact in size and colour and still looked "flat" against the reference.

**Fix:** a soft shadow under the title and under the subject. That is what sells "this layer is cut out and placed on top".
It needs padding in the texture, otherwise the shadow is clipped at the edge — and then the measured fractions of the object
inside it have to be recomputed.

---

## 19 · The world's aspect must be the frame's aspect

**Symptom:** the N of "NO. 01" was cut in the margin, and the bottom caption spilled out.

**Cause:** the poster world was 1400×2000 (ratio 0.70) inside a 9:16 frame (ratio 0.5625). Fitted to height, the poster came out
15% wider than the frame, and everything in the margins was lost.

**Fix:** `PW = PH * W/H`. If the poster is meant to fill a 9:16 frame, its world is 9:16 too.

---

## 20 · Sizes on one plane are not valid on another plane

**Symptom:** the subject flooded the whole frame even though "it is 84% of the poster height".

**Cause:** `PH` is the poster's height **on the poster's plane**. The subject sat at `z=0`, where the field of view is 1665 units,
not 2000. The same number, a different meaning.

**Fix:** do not derive sizes from `PH` but from the desired fraction of the frame, per plane:

```js
const visAt = z => 2 * (EYE0 - z) * Math.tan(fov / 2);
const frameFrac = (frac, z) => frac * visAt(z);
```

**The rule:** in a scene with several z planes, every size is derived through `frameFrac`. (`gate.mjs` checks this.)

---

## 21 · A mask clips the shadow too

**Symptom:** every letter revealed behind its own mask had a horizontal cut line under it instead of a soft shadow.

**Fix:** two passes. Draw all the glyphs into an ink canvas **without shadow**, and only then paste the composite with `shadowBlur`.
The shadow applies to the result, not to the parts.

---

## 22 · A background layer smaller than the frame leaves a one-pixel seam

**Symptom:** a dark one-pixel line at the left edge, even when the canvas background is the same colour.

**Cause:** the antialiased edge of the quad is composited over the background and comes out slightly dark.

**Fix:** give a flat-colour layer a size larger than the frame (1.06). That touches no measured position, because it has no content.

---

## 23 · A scene's first draw is not the steady state

**Symptom:** the determinism gate failed four scenes. It looked like `Math.random` in the code — but there was none in the whole engine.

**What was measured:** the sequence of differences between consecutive draws at the same `t` was `2433/0/0` — **only the first draw
differs**, and from the second on everything is pixel-identical. The difference was concentrated in the text area, up to 13 levels.
Every failing scene went through `applyPost`, which keeps buffers in a Map and reuses them.

**What it means in production:** without a warm-up, **the first frame of every render** carries that difference.

**Fix:** `host.html` draws two throw-away frames at `t=0` before the loop.

**The lesson:** "not deterministic" and "not settled yet" look the same from outside. The difference is measured over a sequence of
four draws, not two.

---

## 24 · An effect's strength must come from speed, not from a time window

**Symptom:** speed lines burned at full strength for about two seconds, even after everything stopped — and then they read as
scratches on the picture.

**Fix:** derive the strength from the numeric derivative of the entrance curve:
```js
const at = u => ease(clamp01(seg(u, t0, t1)));
const speed = Math.abs(at(t + 1/60) - at(t)) * 60;
```
`draw` stays a pure function of t, so this works in motion-blur sub-samples too.

---

## 25 · Time the camera to the EXTREMES of the geometry, not its average

**Symptom (an unfolding cube-net scene):** two failures caught only on the contact sheet, in the same scene:
1. The E/W arms of the cube net **were cut off at the sides** halfway through the unfold — the camera pull-back was timed to the
   "average" of the unfold (1.5–4.2s) while the wide arms open **first** (1.45–2.4s). The geometry got ahead of the camera.
2. **The fold into a cube was invisible.** The arms fold *backwards* (so the outer faces point outward in the cube), and a frontal
   camera sees only the front panel — the most complex motion in the scene happened behind it.

**Fix:** (1) the pull-back window is derived from the **first element to overflow**, not the average — `seg(t, 1.35, 3.1)` instead of
`1.5–4.2`. (2) **orbit** to ¾ during the fold: `eye = [sin(θ)·D, y+lift, cos(θ)·D]` with `θ` peaking mid-fold and staying at 0.30rad
for the roll — which also makes the floor shadow make sense.

**The rule:** when geometry grows or rotates — compute the **bounding box of the extreme frame** and time the camera to it; and when
motion happens *behind* a plane — move the camera off the plane before the motion begins. Neither failure was visible in the code,
only on the sheet.

**What did NOT cost a round, because it had a selftest:** the hinge kinematics (`_hinge.js`). The net's tail folds **opposite** to
the arm it hangs on (an accordion), otherwise it returns to the centre plane — caught by the numeric test, before the first frame.
**The difference in rounds between "checked by number" and "checked by eye" is the whole story of that scene.**

---

## 26 · Painter's sorting by CENTRE DISTANCE is not plane sorting

**Symptom (a split-flap board scene):** 26 of 30 board cells vanished at rest. Only the three central columns survived.
The cell state was completely right; the textures were right.

**Cause — measured:** `renderQuads` sorts far→near by **the distance of the centre from the eye**. A wide background board
(960×520) at `z=-3` sits in the centre; a small card at `z=-1` but 390 units off-axis is farther from it in centre distance by
390²/2D ≈ 26 units ⇒ the board is "closer" ⇒ drawn **after** the card and covers it. Exact computation for cell (0,1): card 2905.9,
board 2884.2. For cell (0,6): card 2883.0, board 2884.2 ⇒ survives. **Matches the picture exactly.**

**Fix:** an optional `q.sortKey` in `_quad3d` — larger = behind = drawn first. A scene that knows its layers **declares** them
(board 100 · cards 50 · flap 20) instead of trusting geometry.

**The rule:** a large background plane + small objects in front of it = distance sorting breaks at the edges.
**How it was caught:** not by eye — by **counting ink per cell** (numpy on the frame). The eye saw "most cells are empty"; the number
said exactly *which*, and the computation followed from that.

---

## 27 · The back of a quad in GL = a VERTICAL flip only, not "flipped and mirrored"

**Symptom:** mirror letters appeared on the back of a falling flap ("Ɔ" instead of C).

**Cause:** the assumption was that the back of a card looks flipped and mirrored — true for **opaque paper** with ink on its far side.
But GL draws the same texture on both sides of the quad, like a **transparency**: rotating around the X axis swaps up/down and does
not touch left/right ⇒ looking at the back = a vertical flip only. `rotate(π)` added a horizontal mirror.

**Fix:** `translate(0,h); scale(1,-1)`. **And verify by eye on an asymmetric glyph** (F · D · K), not on O — a symmetric glyph hides the bug.

---

## 28 · A mapping defined through its inverse must be one-to-one — and that is measured, not seen

**Symptom that did not happen (a marbling scene):** the first wave comb gave `min du/du′ = −0.177`. In the frame that would have looked
like a "fold" — doubled/mirrored pattern pieces where the wave is steep. Caught by a `selftest` **before the first frame**, and fixed
in the parameters (λ 40→48 · amp 40→34 · period 520→600 · α 92→80 ⇒ 0.351).

**The rule:** when you define a deformation through the inverse mapping (because that is the only one you compute), the image is always
"defined" — but if the inverse is not one-to-one, the output shows the same source twice. No error, no NaN — just a false pattern.
⇒ **Every such deformation gets a selftest of its derivative.**

**And how to verify a physical orientation (continuing trap 27):** not by eye on a pattern — **stamp markers**. A magenta square at the
bottom-left of the print, cyan at the top-right, and locate them in the final frame with numpy. They should land where real paper would
put them (a vertical mirror around the axis line, no horizontal mirror).

---

## Meta-lesson

Some traps were caught **by looking at the result**, and some by a numeric gate before rendering.

`node gate.mjs` runs five mechanical gates on every scene, and `--selftest` proves that each of them fails on the original bug when it
is injected. The gates were derived directly from traps 1 · 4 · 5 · 6 · 20, and in their first run they found trap 26 — which nobody
had suspected.

**Three lessons from building the gates themselves:**
1. **A gate without a selftest is not a gate.** The first version of the text gate set `textAlign='left'` explicitly and so immunised
   itself against the very bug it came to catch.
2. **The cause written in the docs may be inaccurate.** Building the gate revealed that trap 1 needs **two** conditions, not one, and
   corrected the record.
3. **When the metric contradicts the eye — suspect the metric** (`MEASURE.md` §7), but when the metric reveals something the eye did not
   see — dig to the root rather than silencing it (trap 26).
