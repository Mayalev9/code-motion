# The engine — module map and API

> All paths here are relative to the engine folder (`$E`, see SKILL.md §0).

```
scenes/_lib.js        shared helpers           scenes/_gl.js         WebGL layer
scenes/_shaders.js    2D GLSL                  scenes/_shaders3d.js  raymarching
scenes/_post.js       post pass                scenes/_quad3d.js     real 3D
scenes/_hinge.js      hinge kinematics         scenes/_homog.js      homography warp
scenes/_words.js      word animation / RTL     scenes/_icons.js      squircles
scenes/_lux.js        luxury typography        scenes/_spring.js     UI springs
scenes/example.js     the starter scene        scenes/*.js           your scenes
render.mjs            renderer                 doctor.mjs            environment check
gate.mjs              engine gate              host.html             host page
player.html           scrub player             audio/analyze.py      track → per-frame data
tools/still.mjs       single frames            tools/animatic.mjs    animatic from a shot table
tools/scene-eval.mjs  run code in Chrome       tools/chrome.mjs      finds Chrome
```

---

## `_lib.js` — the base

```js
clamp01(v) · seg(t,a,b) · easeOut(p) · easeInOut(p) · mix(a,b,k) · rgba(c,a)
rng(seed)                       // deterministic PRNG. No Math.random in scenes.
layer(W,H,blurPx,fn) → {canvas, blur, ...}
paste(ctx, layer, alpha, op)    // op defaults to 'lighter'
roundRect(x, px,py,w,h,r)
squircle(x, cx,cy,size, n=4.2)  // super-ellipse, like an iOS icon
resetFrame(ctx, W, H)           // ← mandatory at the start of every draw
```

**`resetFrame` is not cosmetic:** it resets `globalCompositeOperation`, `globalAlpha`, `filter`, **`direction`**, `textAlign`
and `textBaseline`, and fills black. Without it, state leaks between frames.

**The glow pattern** — every bloom in the engine is built like this:

```js
const g = layer(W, H, 46, x => { /* draw the shape */ });
paste(ctx, g, 0.9);          // additive light
paste(ctx, g, 0.45);         // a second paste burns a core (globalAlpha is clamped at 1)
```

---

## `_gl.js` — shaders

```js
glDraw(W, H, fragSource, uniforms) → OffscreenCanvas
glPaste(ctx2d, canvas, alpha, op)
NOISE_GLSL                       // hash · vnoise · fbm to paste into a shader
```

Uniforms: number→`float` · `[x,y]`→`vec2` · `[r,g,b]`→`vec3` · canvas→`sampler2D` · `Float32Array`→`float[]` ·
`{v2|v3|v4: Float32Array}`→`vecN[]` · **`{data: Float32Array, w, h}`→an RGBA32F `sampler2D`** (a data texture, read with
`texelFetch` — for lists longer than any uniform limit). `uRes` is injected automatically. The context is shared and created once.

⚠️ **Antialiasing in a diverging shader** (a loop with a different `break`/`return` per pixel): `fwidth` is computed from neighbouring
pixels that may have exited elsewhere ⇒ do not trust it for edges. Supersample 4× on a rotated grid (`±0.125/0.375`) instead —
4× the cost, always right.

### `TURBULENT` — turbulent displace (in `_shaders.js`)

The equivalent of After Effects' `Turbulent Displace`. Uniforms: `uTex` `uAmount` `uSize` `uEvo`.

```js
const gl = glDraw(W, H, TURBULENT, { uTex: textCanvas, uAmount: 22, uSize: 11, uEvo: evo });
```

**The trick is not the warp — it is stepping time.** `posterizeTime(8)` in code:

```js
const step = Math.floor(t * 8);       // time freezes into 8 steps per second
const evo  = hash(step) * 999;        // the equivalent of random(999)
```

Without the stepping you get a smooth crawling wave. With it — a line that is redrawn, as if by hand.
Measured: the frame holds 133ms and then jumps, i.e. 3.75 frames per step at 30fps.

⚠️ **Turn motion blur off** (`samples: 1`) — it smears exactly the jitter that is the signature.

---

## `_post.js` — the post pass

```js
applyPost(ctx, W, H, { bloom, threshold, radius, chroma })
```

Four stages: a threshold pass at quarter resolution → a separable gaussian blur ×2 → a `lighter` paste → chromatic aberration +
dither. The dither brought banding down from a 2.8px step to 1.5px.

Values by look: neon `bloom 0.4 / threshold 0.64` · luxury `0.16 / 0.82` · bright UI `0.0` (not used — that look does not glow).

---

## `_quad3d.js` — real 3D

```js
renderQuads(W, H, quads, cam) → OffscreenCanvas
// quads: [{ tex: canvas, pos:[x,y,z], size:[w,h], rot:[rx,ry,rz], alpha, sortKey? }]
// cam:   { eye:[x,y,z], at:[x,y,z], fov }
```

**This is what makes perspective possible.** Canvas 2D is affine only, so it cannot foreshorten a tilted plane.

**Iron rules:**
- The camera at **positive `z`** looks towards `-z`. A standard `up` of `[0,1,0]`.
- The scene thinks in downward Y → **flip the Y sign** in the call.
- An object behind = negative `z` on the quad (i.e. positive `z` in the scene, since you pass `-z`).
- Manual depth sorting (far→near), `DEPTH_TEST` off — so transparency accumulates correctly.
- **Distance sorting breaks at the edges** when there is a large background plane (GOTCHAS 26). Optional `q.sortKey`:
  larger = behind = drawn first. Declared layers > guessed geometry.
- **Depth of field** is done in preparation: blur the texture by its distance from the focus plane, in four linked levels.

### The depth-layer pattern (parallax)

When you want "a picture that comes to life": each layer on a different `z` plane, the camera moves, and that is it.

```js
const EYE0 = 2750;
const fit = z => (EYE0 - z) / EYE0 * 0.80;   // perspective compensation + fit to frame
// negative z = far. A far layer must be bigger to look the same size.
```

⚠️ **Sideways drift must be restrained** — the farther a layer, the more it moves on screen; a drift of 175 units pushed a title out
of frame. 78 worked.

⚠️ **The base factor comes from the frame:** the vertical field of view = `2 · distance · tan(fov/2)`.
A 2000-high poster at distance 2750 with `fov 0.58` → field 1641 → factor 0.80.

---

## `_hinge.js` — hinge kinematics (a hierarchy on top of `_quad3d`)

```js
hinge(pivot, R) · compose(A, B) · IDENT            // rigid transform {R, p}
Rx · Ry · Rz · mul3 · apply3                       // STANDARD rotations
eulerForShader(R) → [rx, ry, rz]                   // ⬅️ what the shader will turn back into R
cubeNet(P, a, aT, G) → {C,N,S,E,W,T: {center, R, normal}}
selftest()                                         // round-trip · closed cube · accordion
```

**Why it is needed:** `renderQuads` takes `pos` + Euler per quad **with no hierarchy**. A panel hanging on another panel's hinge needs
composed transforms, and then decomposing the matrix back into angles **in the shader's convention** — which is the transpose of the
standard (`mat3` in GLSL is column-major ⇒ `rotX(a)` there = Rx(−a)). `eulerForShader` handles that; the selftest proves a round-trip at
4e-16 over 400 random matrices. Run it inside Chrome:
`node tools/scene-eval.mjs _hinge "m => m.selftest()"`.

---

## `_homog.js` — drawing through a homography

```js
// items: [{src: canvas, H: [9 numbers, row-major, texture px → screen px], alpha}]
```

Perspective-correct warping of a texture to any four corners on screen — for replicating a tilted page, a screen in a phone, or a
camera tracked from measured points. The vertex leaves in homogeneous coordinates so the GPU does the perspective divide itself.

---

## `_spring.js` — interface springs

```js
SPRINGS = { snap, ui, gentle, lively, ambient }   // the five registers published by motion.dev/ui
spring(t, name='ui') → 0..1                       // analytic damped spring — deterministic
settleTime(name) → seconds                        // derive durations instead of guessing them
STAGGER = { tight: 0.04, base: 0.08, relaxed: 0.15 } · TRAVEL = { hover: 4, enter: 24, section: 48 }
```

Interface motion is built on physics, not drawn curves: `easeOut` looks like "an animation"; a spring with a small overshoot looks like
"an interface". See `UI-EXPLAINER.md`.

---

## `_shaders3d.js` — a volumetric tunnel

`TUNNEL` — raymarching at 72 steps per pixel. What reads as 3D is the grid on the wall: lines along the depth converging to a vanishing
point, and rings flying past. Uniforms: `uZ` `uRoll` `uFov` `uBass` `uMid` `uHigh` `uShock` `uSway`.

---

## `_words.js` — word animation, including RTL

```js
layoutRTL(ctx, text, fontStr) → { items:[{t,x,w,i}], total }
STYLES.typed | .assemble | .riseMask | .punch
sweep(ctx, {cx,cy,L,p,S})       // the caller sets the composite, not the function
backGlow(ctx, W,H, cx,cy, L, amt, color, S)
FONT = '"Heebo","Rubik","Arial Hebrew",Arial,sans-serif'
```

**Why `layoutRTL` is needed:** to animate letter by letter you need a position for every letter, and `fillText` does not give you one.
The function measures each token and places them right to left. A Latin or number run stays one unit that reads left to right —
otherwise `AI` comes out reversed. For left-to-right text use `layoutLTR` from `_lux.js`, or measure each character yourself
(see `scenes/example.js`).

---

## `_icons.js` · `_lux.js`

```js
// _icons.js
GLYPHS         // 12 glyphs: person note eye wave search diamond sparkle flower bolt layers play grid
PALETTES       // 8 gradient pairs
drawIcon(ctx, W,H, {cx,cy,size,glyph,pal,rimHue,alpha,glow,...})
beatTimes(A) · beatState(times, t)

// _lux.js
SERIF = 'Didot, "Bodoni 72", ...'
GOLD [201,169,106] · GOLD_HI [246,231,193] · CREAM [242,237,228]
layoutLTR(ctx, text, font, tracking) → { items, total }
foil(ctx, x0, x1, spec)          // gold foil with a travelling glint band
hairline · fleuron · corners · grain · vignette
```

---

## `render.mjs` — the renderer

```bash
node render.mjs SCENE [--fps 30] [--mblur N] [--shutter 0.6] [--from S --to S] [--scale N] [--tag709]
                      [--out file.mp4] [--force] [--audio x.wav | --no-audio] [--keep-frames] [--frames-only]
```

Starts a temporary static server (dynamic import does not work from `file://`), opens headless Chrome, draws frame by frame, and
encodes with ffmpeg (`libx264 · yuv420p · crf 17 · +faststart`).

| | |
|---|---|
| arguments | strict `parseArgs` — an unknown flag, a missing value or two scenes = an error |
| destination | an existing `--out` is **not overwritten without `--force`**, and this is checked **before** rendering. The default `out/SCENE.mp4` is overwritten |
| frames | temporary PNGs in `out/.jobs/<scene>-<job>/frames`, **deleted after a successful encode** (`--keep-frames` keeps them). A disk estimate is printed (up to W·H·3 bytes per frame) and it stops if there is no room |
| atomic | encodes to a temp file, verifies with a full `-xerror` decode, then renames — a failed encode never leaves a file that looks valid |
| audio | `--audio` › `SCENE.soundtrack` › silent. Trimmed/padded to exactly the video length (`apad` + `-t`, no `-shortest`); with `--from` the audio starts at the same second |
| events | `SCENE.events` (an object or a function) ⇒ `<output>.events.json` |
| manifest | `<output>.manifest.json` — the sha of every code file used, plus Node/ffmpeg/Chrome versions |
| Chrome | found automatically (`tools/chrome.mjs`); `CHROME_PATH` overrides. `node doctor.mjs` checks every dependency |

⚠️ `yuv420p` shifts colours by a few levels. A HEX measured on the canvas is checked again on the file:
`deliver_gate.py OUT.mp4 --audio … --hex '#c8f24a@0.5,0.5@2.0'`.

**Motion blur:** because `draw` is a pure function of `t`, sample `N` moments inside the shutter window and average them with `lighter`
at alpha `1/N` on black — adding = averaging. Measured: in fast motion sharpness drops 15.7%; in a still moment the difference is zero.

---

## Sound derived from the animation — one event timeline

**The rule:** the scene defines `SCENE.events` (the times and parameters of every audible event). `render.mjs` writes them to
`out/SCENE.events.json`, and the sound script **reads that file** — it does not duplicate constants. Change the scene ⇒ render ⇒ the
sound updates by itself. Then `SCENE.soundtrack: 'audio/x.wav'` (or `--audio`) ⇒ the renderer muxes it.

Order: `node render.mjs SCENE --no-audio --to 0.1 --out /tmp/x.mp4 --force` (writes the events) → your sound script → `node render.mjs SCENE`.

⛔ No `-shortest` (GOTCHAS 13) — so a hand-muxed WAV must be as long as the scene.
Verify sync **by counting**: the number of events in the sound script = in the JS, and the RMS at the first hit vs. the silence
before it (e.g. 0.044 vs 0.0003).

---

## `audio/analyze.py` — audio-reactive data

```bash
python3 audio/analyze.py track.wav 30           # → track.json
```

`track.json`: `bass` `mid` `high` `level` `onset` per frame + `beats` (indices).
A scene that declares `audio:` receives it as parameter `A` in `draw`.

---

## `SCENE` — the contract

```js
{ name, width, height, fps, duration, draw,
  audio?:  'audio/track.json',      // → A  (analysis data for drawing — not a soundtrack)
  soundtrack?: 'audio/x.wav',       // a soundtrack the renderer muxes
  events?: {...} | () => {...},     // the event timeline for sound → <output>.events.json
  images?: { key: 'assets/x.jpg' }, // → IMG (ImageBitmap)
  fonts?: [{ family: 'Inter', src: 'assets/fonts/Inter.ttf', weight: '400' }],
  samples?: 4, shutter?: 0.55 }     // motion-blur defaults

draw(ctx, t, W, H, A, IMG)
```

Paths in `audio`, `soundtrack`, `images` and `fonts` are relative to the engine folder. Put fonts you have the rights to in
`assets/fonts/` — a font that is only installed on your machine will not render identically elsewhere.

---

## Combining AI video with a scene

When an object is generated on green and animated by an image-to-video model, the pipeline is:

```bash
# 1. frames from the video, after measuring the object's bounds — not a guessed crop
ffmpeg -i spin.mp4 -vf "fps=24,crop=W:H:X:Y,scale=430:-2" frames/%03d.png
# 2. keying → silhouettes with alpha
python3 $S/keyspin.py frames/ keyed/
# 3. pack into one sprite sheet (e.g. 48 frames, 8 columns) — one load instead of hundreds
```

**What to ask the generator for:** an **asymmetric** object (a rotationally symmetric one looks the same from every angle and the spin
is invisible) · 5 seconds · one full turn · the same length for every object · `starting from exactly where it already is` in the motion
prompt, otherwise the model moves the camera somewhere else before it starts.

**When the layer is a picture, not a silhouette** — `keycolor.py` instead of `keyspin.py`. It keeps the original colour, de-spills, and
closes dark seams the mask punched through. It also returns geometry (`subject_geometry`) — the object's centre and diameter as a fraction
of the PNG, which lets you place by "the ball centred at 0.48" rather than by the file's corner.

```bash
python3 $S/keycolor.py in.jpg out.png --close 14
```

**Time remapping** — "start fast and finish slow" is one line:

```js
const eased = 1 - Math.pow(1 - p, 2.6);   // sample the frame index through a curve
```

The same curve for every object = matched speeds with no extra work.
