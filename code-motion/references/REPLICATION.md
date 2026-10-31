# REPLICATION — the replication path (the core work)

> **The source is the yardstick.** The goal is high fidelity to it, including the small details — not to improve,
> not to interpret, not to "adjust to taste". If something of ours looks "better" but differs from the source — **that is a gap.**
>
> ⛔ **A previous replication is not a source.** Even when it represents a style the user loves, that does not mean every
> detail in it was confirmed as accurate (one well-liked replication turned out to have a deviation at 3.30s that was found
> only weeks later). Never copy a value from an earlier replication — **measure in the current source.**
> `SOURCES.md` says what to look for; the source says what is right.

`$S` below = this skill's `scripts/` folder. `$E` = the engine folder in the user's project (see SKILL.md §0).

## 0 · Before measuring: what is actually in the file
- **The real frame:** is it embedded inside a frame? (e.g. 960×540 inside 1080×778; or a card inside a frame with a
  chapter bar — where the frame IS part of the film). ⇒ `--crop` / `--ref-crop` according to what you are replicating.
- **The real rate:** the file's fps ≠ the animation rate (e.g. 25fps animation served at 30 — a duplicated frame every 6).
  Count duplicated frames.
- **The audio:** is there a channel? Music / effects / speech? — **not listened ⇒ mark as not checked**; measure with
  `deliver_gate` / `ebur128`.
- **Assets that cannot be drawn in code** (photographs, embroidery, a painted landscape, UGC clips): identify them **now**,
  and ask the user for them, or declare a deviation — never silently replace them with something generic.

## 0′ · Working resolution vs. delivery resolution

| | what | why |
|---|---|---|
| **proxy** | half the source on each axis (4K ⇒ 1920×1080) | fast iteration rounds. **All measurements and comparisons run here** |
| **delivery** | **a native render at the source resolution** (e.g. 3840×2160) | the version that is delivered and finally checked |

⛔ **Delivery = re-rendering at full resolution, not upscaling the proxy.** Upscaling does not bring details back;
it only hides that they were never built. `sbs` reports a WARN when sizes differ — that is a reminder that you are
on the proxy, not an approval.
⛔ **A drop in resolution in the version you show is a declared deviation**, not "a minor gap", and needs approval.

The engine supports this: `node render.mjs SCENE --scale 2`. Scenes always draw in **logical space**
(`SCENE.width × SCENE.height`); at `--scale S` the backing store is S× larger and the CTM is scaled, so no scene changes.
What the CTM does NOT fix — `shadowBlur`, `shadowOffsetX/Y` and `ctx.filter` work in **device space** per the Canvas2D spec —
is fixed by a Proxy around the context in `host.html`, and `layer()` creates offscreens S× larger. `lineWidth`, `setLineDash`
and gradients are in user space and scale by themselves. Proof that it works: `--scale 1` must give byte-identical PNGs
to a normal render, and `--scale 2` downscaled must match the proxy closely.

## 1 · Watch the whole source, then break it into shots
1. **Watch all of the source:** a contact sheet over the full length for an overview, then dense frames around every event
   (every frame at cuts and transitions). ⚠️ Claude does not watch in real time — whatever needs real time (easing,
   pacing, sync) is measured per frame, or stays "not checked".
2. **A shot table** in `direction/NAME.md` (a ```shots``` block — `DIRECTION.md`), at the source rate (`measure.py` without `--fps`):
   for each shot — `t0/t1` (seconds **and frames**) · **what the shot does, in one sentence** (`role`; "you don't get it"
   was the most common failure) · what moves (camera / object / text) · where the eye goes.
3. **A small-details list for every shot** (they are what gets forgotten): font · weight · size · tracking · colour (measured HEX) ·
   baseline · easing (by per-frame position, not by feel) · type of blur (focus or motion) · one-frame flashes · cursor
   position · word-by-word timing · shadow/glow · grain.

## 2 · Build shot by shot, and compare after every shot
```bash
node render.mjs SCENE --from A --to B --out /tmp/shot.mp4 --force
# source time ≠ file time: the shot was rendered alone ⇒ it starts at 0 in ours, at A in the source
python3 $S/sbs.py REF.mp4 /tmp/shot.mp4 \
        --ref-from A --ours-from 0 --duration $(echo "B-A" | bc) [--ref-crop W:H:X:Y]
```
**Read `preflight.txt` first.** Length · fps · size · aspect ratio · audio — every difference appears there as a warning
or a failure. A `FAIL` in the preflight = the comparison is **not aligned**, and any conclusion from it is worthless:
fix the alignment (`--ref-from`/`--ours-from`/`--duration`/crop) before looking at gaps.

| file | why |
|---|---|
| `sbs.mp4` | watch it through — REF \| OURS \| diff, A/B audio (source left · ours right) |
| `blink.mp4` | blinking on the same frame — **offset, spacing and typography** jump out |
| `hires/` | at source resolution 1:1 + a red/cyan overlay — **this is where you judge font and spacing** |
| `frames*.png` | a downscaled sheet — **overview only** |
| `gaps.json` · `worst.txt` | difference · affected area · measured severity per frame |

- Do not move on to the next shot while there is an open **critical/significant** gap that can be closed.
- **Show the first shot to the user before continuing.** It is the cheapest moment to discover you misread the source.
- When the metric and the eye disagree — **suspect the metric**, open `hires/`.

## 3 · The gap log — `direction/NAME.gaps.md`

| # | time / frame | severity | what differs (source ⟷ ours, in numbers when possible) | how found | cause | fix | status |
|---|---|---|---|---|---|---|---|
| 1 | 3.30 · f99 | critical | background: white ⟷ purple gradient; the sentence: exits left ⟷ centred | sbs · hires | chapter boundary late | … | open |

**Severity — four levels:**

| level | what it is | what you do |
|---|---|---|
| **critical** | wrong shot/structure/content · a missing or extra event · a different base colour · a missing ending | stop and fix |
| **significant** | an element in another place · a different font/weight/size · timing off by more than ~2 frames · a different easing | fix before moving on |
| **minor** | a sub-pixel offset · a radius/spacing slightly off · a hue off by a single level | log it; fix if cheap |
| **encoding-noise** | gradient banding, grain, compression artefacts | **do not fix** — note once that it was identified as such |

⛔ **A drop in resolution, a missing asset or a substituted material is not "minor"** — it is a **declared deviation** that
needs the user's approval, even when the pixel difference is small.

`gaps.json` suggests severity **from pixels** (affected area · mean difference). That points where to look —
**the decision is by eye**: one wrong letter is "significant" even at 0.1% of the area.

**Status:** `open` · `closed` (with the frame that proves it) · `declared deviation` (only with a reason — a missing asset /
an engine limit). **Every visible difference goes into the log**, even small ones. An empty log ≠ a perfect replication —
only that "nothing was found".

### When to stop and ask the user
**Only** when: (1) there is a **material deviation** that cannot be closed in code · (2) an **asset** is missing that the user
needs to provide · (3) there is a **decision that cannot be inferred from the source** (illegible text, a colour below the noise).
⛔ Do not stop on every sub-pixel difference or on encoding noise — fix and carry on.

## 3′ · A time shift or a visual model? — `align.py`

A big gap in `sbs` **does not say what broke**. Before fixing timing or drawing:

```bash
python3 $S/align.py REF.mp4 OURS.mp4 --ranges 0:62,63:100,101:187 --max-shift 5
```
Compares `ours[f]` against `ref[f+k]` for every k and reports the winner:

| finding | meaning |
|---|---|
| best k ≠ 0 with a clear improvement | **time shift** — a cut point / offset |
| k=0 with a sharp V, the difference stays high | **visual model** — not timing |
| a **flat** k curve | the content differs; shifting does not help at any k |
| `↳ hold phase` | the duplicates (25→30) fall on a different residue — not a constant offset |

Two traps learned the hard way:
1. **Per-frame argmin is noisy.** A first version classified "hold phase" by argmin spread — and caught near-static content.
   **The mean curve is the signal; per-frame argmin is not.**
2. **A strong negative k in a narrow range around a chapter boundary is not proof of an offset.** In one replication it
   appeared at three joins, and at all three **the cut point was right** — what broke was the *shape of the transition*
   (a missing ramp · a cut replaced by a ramp · a transition that barely exists). ⇒ **Verify every join separately** by
   measuring the actual jump, and do not apply a shared rule before the hypothesis is proven at each one.

## 4 · Full assembly and watching it through
```bash
python3 $S/sbs.py REF.mp4 out/SCENE.mp4 [--ref-crop …]          # the central tool — watch it through from start to end
#   preflight.txt first · blink.mp4 for typography · hires/ for 1:1 · gaps.json for severity
python3 $S/replicate_gate.py REF.mp4 out/SCENE.mp4 --roi …        # a sanity check, not a target (a metric is not a goal)
python3 $S/deliver_gate.py out/SCENE.mp4 --audio yes|no …          # the file itself
```
- **Watch `sbs.mp4` from start to end** — and at normal speed (what Claude can do: dense frames over its whole length;
  what it cannot — say so).
- `worst.txt` is a place to start, not an importance ranking. A 2-frame gap in word timing barely moves an average.
- Every new gap ⇒ the log.

## 5 · What to show the user
`sbs.mp4` + `frames.png` + the gap log (open · declared deviations) + **what was not checked** (real-time viewing, listening).
Not "done" while a gap is open; not "faithful" on the strength of a number.

## Traps that recur in replications (`MEASURE.md`)
- **Coarse sampling erases events** — two white flashes on frames 1 and 3 simply do not exist in a contact sheet.
- **A metric that mixes two effects invents a third** — measure a property that is immune to the second effect.
- **Assuming an animation that does not exist** (or missing one that does) — count, don't look.
- **REF|OURS too late** — `sbs.py` after every shot, not at the end.
- **Frozen shots**: per-shot frame difference against the source — `sbs` + `replicate_gate` G3.
- **A colour mask ≠ an object mask** — any bbox that comes out as "the whole frame" is this.
- **A value derived from the frame average instead of sampled** — in one replication this produced two separate bugs:
  a background derived from mean luminance (an average that includes text and glow), and a light lobe whose strength was
  derived from it and so **came back to life** in the closing flash.
  ⇒ **Sample background and colour in an area free of content**, never derive them from a global metric.
- **A chapter transition is not just a cut point** — check the *shape* of the transition (a ramp? a cut? how many frames?)
  by measuring the per-frame jump on both sides around the join.
- **A drop in resolution is not "a minor gap"** — 4K→1080 is a **delivery decision** that needs approval (§0′).
- **`ffmpeg -ss` at a rounded time skips a frame.** `f'{95/30:.6f}'` = `3.166667` lands on the frame boundary and sometimes
  on **the next frame**. This produced two fake "regressions" that looked like real bugs.
  ⇒ **Per-frame measurement reads a continuous stream**, never seeking.
- **A synthesised soundtrack is not a soundtrack replication.** One synthesised score "sounded similar" but its correlation
  with the source audio was **0.0005**. ⇒ **A fidelity version takes the audio from the reference**; a synthesised version
  is a separate, labelled file, not "the replication".
  ⚠️ **And the reverse:** taking the audio from the reference is not "replicating the soundtrack" but a
  **source-audio passthrough**. A correlation of 0.9997 proves the source was **passed through and aligned**, not re-composed.
  It is a **declared deviation** in any output that is not allowed to use the source audio.

## Two lessons from inside the equivalence tooling

**1 · A positive control on MP4 is not a control.** After changing a scene in frames 296–400, comparing MP4s showed
differences up to **60** in frames 264–295 — *before* the range — and in 400–404 after it. Those are not engine changes:
B-frames reference **backwards** and P-frames forwards, so a change in one frame moves the encoded residuals across the
whole GOP. The same check on **PNG**: **byte-identical** outside the range.
⇒ **Every "what did not change" control runs on PNG.**

**2 · "No frame was compared" passed as ✅.** A frame reader looked for `{i+1:05d}.png` while `render.mjs` writes from **0**.
When every index is dropped, `worst` stays at `(0,0,0)`, every condition holds, and the gate prints ✅ without measuring
anything. ⇒ every stage needs an **emptiness gate** that fails explicitly, verified both ways: **fault injection**
(a request for frames that do not exist ⇒ ❌) and a **clean case** (⇒ ✅).
⚠️ Same class: *"a gate without a positive control is a counter."*

"Not deterministic" was a wrong conclusion once: three runs gave two different MP4 hashes. At the **PNG** level the difference
was **0** — the noise was entirely from H.264 at crf 17. ⇒ Determinism and equivalence checks compare PNG; comparing MP4 measures
the codec, not the engine.

An "edge ratio" that suits one scene and fails another is not a criterion — report it as **information**, and gate on
`MAE ≤ tol` together with a negative control.

⚠️ "Equivalence" = the same picture at a higher resolution. It does **not** say the picture is right against the reference.

## The integral of noisy measurements drifts — recover the quantity itself

Building a scroll table two ways: **integrating per-frame velocities** drifted +14px after 6 frames, **+52** after 15.
**Unwrapping the positions themselves** (modulo the spacing, along a non-decreasing path) gave **±1px**.
⇒ When you can measure the quantity directly, do not sum its derivative. Measurement noise cancels in the quantity and
accumulates in the derivative.

## Measuring in a cropped window gives a wrong — and convincing — ratio

A text width measured in the window `x 600–1300` gave a ratio of **×1.30–1.33, consistent across three lines** — three
"independent" measurements that agree, which looked like strong evidence. In the full box the ratio was **×1.67 in one and
×1.39 in another**: the window **cut off** the end of the text exactly where it overflows. Scaling by the first measurement
**made the metric worse** ⇒ reverted.
⇒ **Before concluding anything from a ratio, make sure the measurement was not clipped.** Agreement between measurements that
all suffer from the same clipping is not evidence — it is the same error repeating.

## Transparency lets the background colour through — "glass" is not always glass

A card interior in the source measured **neutral grey (217,217,217)**; ours came out (221.8,233.8,248.7) — **a blue tint**,
because the fill was `rgba(…,0.80)` and the blue background bled through. ⇒ Check neutrality (R=G=B) before assuming a
brightness difference is only brightness.

## A global metric cannot calibrate a property that varies in space

A "correct" blur calibration: render at eight fixed blur values, measure sharpness (p99.5 of |∇L|) **per frame**, invert the
table. Sharpness locked in almost exactly — 7.3 vs 7.0 · 8.7 vs 8.7 · 37.7 vs 38.7 — **and the MAE got worse.**

The reason: **local** sharpness on a 6×4 grid of the same frame ranged from **1.3 to 74.3** (×56). That is **depth of field** —
a sharp island inside heavy blur. One global number gives **the same value** to "medium blur everywhere" and to "very blurred
with a sharp island", so calibrating by it pushes everything to blur.

⇒ **Before calibrating by a scalar, measure the same property as a map.** If the spatial spread is large, the scalar does not
describe what you are calibrating, and a "successful" calibration by it will make the output worse.
⚠️ Same class as *"a metric is a check, not a target"* — but it fails even when the metric **does** improve, because it was
the wrong metric to begin with.

## Colour management — whatever is untagged, someone will guess

**h264 without colour tags is the default, and that is a fault.** A file from `libx264` without explicit flags gets
`color_range/space/transfer/primaries = unknown`, and every consumer guesses — an HD player assumes bt709. If swscale
converted with bt601 (its **default** from RGB), the measured gap against the canvas source is **mean 2.87 · p99 15**
instead of 0.74.

`-color_trc` and `-color_primaries` in ffmpeg do not reach the stream — measured: they stayed `unknown` in `ffprobe`.
Only `-x264-params colorprim=…:transfer=…:colormatrix=…` writes them. ⇒ Verify in `ffprobe` that all four fields were
written; do not assume a flag that was accepted without error was also recorded. (`render.mjs --tag709` does this.)

### How to tell what the source is, when the source is untagged

- **Range** — from the Y histogram. A sharp peak at **235** and zero at 255 ⇒ limited range; a peak at 255 ⇒ full range.
  ⚠️ A small share of pixels below 16 is **ringing**, not evidence of full range.
- **Matrix** — cannot be read, can be measured: a **2×2** table of (our encoding matrix) × (the matrix declared in measurement).
  The declared matrix barely matters, because it applies to both sides and cancels out; **the encoding matrix does**. The one
  that wins in both rows is the source's.
- An "out of gamut" test is not decisive — tried, gave 3:1 with tiny margins.

### Two measurements that measured nothing

**A negative control that was never applied.** `-vf scale=out_color_matrix=bt601` together with `-colorspace bt709` came out
**byte-identical** to the correct encode (same sha). "The negative control gave the same result" was misread as "the measurement
is robust" — the truth was that the mutation was never created. ⇒ **Verify that the mutation exists in the output** before
reading the result.

**"What a player sees" through ffmpeg.** `ffmpeg -i f.mp4 -pix_fmt rgb24` returns **the same number for a tagged and an untagged
file** — the automatic conversion ignores the tags. Three different files gave an identical 0.74. ⇒ Force
`scale=in_color_matrix=…` explicitly; otherwise you measure swscale's default, not the file.

### The measurement itself needs a declared colour path

`_compare_core.color_filter()` applies a declared conversion **identically to both sides**, and the signature reports it.
⛔ Adding it **changes the signature**: the same file measured 17.24 before and 17.69 after. Numbers from the two signatures
are not comparable.

### Delivery: fidelity to the data vs. fidelity to the look

When the source is untagged, it is **displayed wrongly for everyone**. A correctly tagged output shows the right colours —
i.e. **different from the source as it looks**. That is a declared delivery decision, not a technical detail (one measured
cost: **1.64 MAE** for tagging). Bring both numbers and let whoever ordered it decide.

## Two renders of the same scene must never overwrite each other

The renderer once used a frame folder shared by scene name, and two renders of the same scene — **even with a different
`--out`** — deleted or mixed each other's frames (it happened for real, mid-measurement). The engine now:
1. **isolates every job** — `out/.jobs/<scene>-<pid>-<time>-<random>/frames`. Two parallel renders of the same scene produce
   complete, **byte-identical** files.
2. **writes atomically** — encodes to `encode.mp4` inside the job folder, **verifies with a full `-xerror` decode**, and only then
   renames to the final name. A failed encode leaves **no file at the destination**.
3. writes **`<output>.events.json`** instead of `<scene>.events.json` — events are tied to the output, not the scene name.

### `<output>.manifest.json` — provenance

Without it, older versions cannot be rebuilt: the code each version was built from gets overwritten. Every render writes a
manifest: the output's `sha` · scene · jobId · time · fps · frame count · seconds · the audio and its `sha` · **the `sha` of the
scene file and everything it imports** · and the versions of **Node · ffmpeg · Chrome · platform** (rasterization differs
between Chrome versions).
⚠️ The manifest records **how** the file was made — not that it is right, nor that it was approved.
A manifest tells you the code was different, not what it was — put the project under git to rebuild old versions
(don't initialise git or commit without the user asking).

## "Passed the gate" is not "the file is complete"

An MP4 physically cut at 45% once passed the delivery gate 5/5 — and was even reported as ending "at rest". All four reasons
are classic fake green:
· ffmpeg's exit code was **thrown away**;
· decoding ran **without `-xerror`**, so ffmpeg decoded "as much as it could" and returned rc=0;
· the end-motion check returned **0.0** when frames were missing — and 0 read as "frozen", i.e. a **valid** ending;
· the file check mainly checked that the **header** could be read, not that everything decodes.

⇒ **`D0 · file integrity`** runs **first**: it decodes all of the video and all of the audio with `-xerror`, checks the exit code,
and counts frames against what the file **declares**. A failure there is **hard and cannot be overridden**, and the other gates
are **not reported at all** — measuring a partial stream is not measuring.
⚠️ D0 checks **decoding only**. Audio length vs. video is D2's question; mixing the two once created a false failure on a valid file
whose audio was short on purpose.

## When a gap is **closed** — and the signature without which you may not compare

> **A parent gap is closed only when all three hold:**
> 1. **every** sub-gap of it is closed or explicitly defined as a **declared deviation**;
> 2. **its whole range** was checked **visually** (REF | OURS), not just its ends;
> 3. there is no frame in the range that was not looked at.
>
> ⛔ **MAE is a tool for finding, not a sign-off.** A low number is not "checked", and a number that went down is not "closed".

> **Two more rules learned by mistake:**
>
> **R1 · A control showing that other frames did not change proves no regression — not fidelity.**
> "The four chapters I did not touch came out identical to the digit" says the change was targeted. It does **not** say they
> match the source. Fidelity needs a comparison **against the reference**, frame by frame.
>
> **R2 · Never validate a model on the frame it was fitted on.** A lobe fit on f62 that yields MAE 23.4 on f62 is a **fitting
> residual**, not proof. You need frames that took no part in the fit (**holdout**), and the number on them is recorded separately.
> A model that fails on the holdout — fails.
> ⛔ **Every chapter/range must have an explicit state** — `open` · `closed` · `declared deviation` · `not checked`.
> "The metric is low" is not one of them.

### The measurement signature — mandatory in every report
Two tools in the same project once gave **44.21 and 31.41 for the same chapter, and both were right.** The difference is not
only scale: `sbs.py` measures at `--metric-width 720` and merges channels by **max** (`np.abs(A-B).max(axis=2)`), while another
tool measured at 1920×1080 and merged by **RGB mean**. Max-per-channel is always higher than the mean — so a column that mixes
the two shows an "improvement" or a "regression" that never happened.

⇒ Every recorded number carries a **signature**: `tool·version · measuring resolution · crop · frame range · colour space ·
channel merge`. **Never compare two numbers with different signatures** — not in a table, not between versions, not between chapters.

| tool | resolution | crop | scale pipeline | colour | channel merge |
|---|---|---|---|---|---|
| `sbs.py` | `--metric-width` (**720**) | `--ref-crop` · `--ours-crop` | ffmpeg: crop → `trim(start_frame)` → scale to square pixels by SAR → `fps=` · then **Pillow LANCZOS** to the panel and **padding** with no stretching | `rgb24`; the file's **declared** `pix_fmt` and `color_*` go into the signature | **max per channel** |
| `perframe.py` | `--width` (**1920**) | `--ref-crop` · `--ours-crop` | ffmpeg `scale` with `flags=lanczos` only | same | `--union` (**RGB mean**) |

⛔ **Different pipelines ⇒ the numbers are not comparable**, even at the same resolution and channel merge. That is why
`signature()` requires an explicit `pipeline` from each tool.
⚠️ **Do not write "sRGB" as a fact.** The tool reports what is **declared** in the file (`color_space`/`color_primaries`/
`color_transfer` — usually "undeclared") and what the conversion actually is. If the two files declare differently, the signature shows it.

**`perframe.py REF OURS [--ranges "name:a-b,…"] [--union mean|max] [--ref-crop …]`**
— per-frame difference, read as a continuous stream. **Exit codes: 3** hard failure · **2** mismatch (unless `--allow-mismatch`) · **0** OK.

Three failures an earlier version returned exit 0 on — all closed, each with a test case:
· a 64×36 source vs a 64×64 replica stretched into the same box returned MAE 0.67 ⇒ now **a different aspect ratio = FAIL, and is
  not measured at all** (stretching invents a match).
· 30fps vs 24fps with the same frame count returned **MAE 0.00** ⇒ now **a different fps = FAIL**.
· `--union typo` was computed as mean and written into the signature as typo ⇒ now **an invalid value = failure**.

⛔ **No `zip`.** Both sides are read in full; a long tail is reported as "extra frames".
⛔ **`-xerror` + exit code.** Without it ffmpeg decodes "as much as it can" from a broken file and returns **rc=0** — measured on a file
   cut in half: without `-xerror` rc=0, with it rc=183. Also, fewer frames than the file **declares** is a separate FAIL.

**Shared core:** `_compare_core.py` — `probe` · `crop_dims` · `preflight` · `frame_chain` · `extract_frame` · `Decoder` · `signature`.

**Why frame extraction must live in one place.** When `sbs.py` had two extraction paths (the main decoder + a local hires
extractor), one of them computed the index from a variable left over from **another** loop — `rfN + g['i']` instead of `rfN + i`.
The result: **every hires image was pulled from the same frame**, with different file names and times, and `blink.mp4` (built from
them) blinked between two copies of the same moment. ⇒ `frame_chain` is the only chain, and `extract_frame` the only extractor.

**A test that proves the right frame was extracted:** "the two images differ" alone is **not enough** — it also passes when two wrong
frames were pulled. The test here runs a counter film where frame k is painted with value k, and checks that every image is
**the exact frame** requested. Verified by mutation: a fixed index · an "old" index (i//3) — both fail.

**A frame window is judged as a window.** A 100-frame source vs a 50-frame replica, asking for the first 10: the ten frames exist,
are identical, and there is no MISSING — and the tool once returned **exit 2** on comparing the full lengths. Now
`preflight(win=(start_ref, start_ours, n))` checks `available = total − start` on each side.

**Frame arguments are rejected explicitly** — `--frames 0`/negative, `--ref-frame`/`--ours-frame` negative or past the end,
a negative `--hires`. `--hires 0` is a **documented off switch**, not an error.

**The signature is built before any report** and goes into `preflight.txt` (full), `gaps.json` (full) and `worst.txt` (id + the
deciding fields). `sbs.py` and `perframe.py` use **the same** preflight, because two different checks for "are the files comparable"
are two standards. The default **fails** on a mismatch; override only with `--allow-mismatch`. A difference in **resolution only,
at the same aspect ratio**, is allowed (proxy) — and recorded in the signature.

## The tools themselves — run their selftests
```bash
python3 $S/sbs.py --selftest            # 47 cases
python3 $S/deliver_gate.py --selftest   # 44 cases
python3 $S/replicate_gate.py --selftest # 26 cases
python3 $S/perframe.py --selftest       # 27 cases
python3 $S/align.py --selftest          # 7 cases
python3 $S/refmeasure.py --selftest
```
Every case has a negative control. The counts go stale — verify by running before quoting them.
Mutation-tested: returning `min` for the window · stretching to a common ratio · ignoring `--ours-from` · removing `apad` — each one
failed exactly the case meant to catch it.
