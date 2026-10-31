# Software explainer animation — the numeric spec

> **Every number here was published by the source itself** — not measured from frames and not guessed. That is rare in this
> genre, which is why this doc comes before any visual reference.

---

## The genre splits into three families — and that difference decides everything

| family | vocabulary | references |
|---|---|---|
| **1 · interface motion** | cards · dashboards · cursors · moving data · macro zooms on UI | What? Studio · Motion UI · the launch videos of Linear/Vercel/Raycast |
| 2 · abstract shapes | morphs · kinetic typography · flat illustration | Ben Marriott |
| 3 · characters | character-led explainers | Yum Yum |

**A mistake learned the hard way:** studying hundreds of posts by a family-2 creator when the look the user wanted was family 1.
⇒ **Before studying a creator — confirm which family the brief is in, and that the creator matches it.**

---

## The motion engine — from `motion.dev/ui`, verbatim

Five registers, all a **physical spring**, not a bezier curve (they live in the engine as `scenes/_spring.js`):

```ts
transitions: {
  snap:    { stiffness: 1218, damping: 70 },   // instant, almost no overshoot
  ui:      { stiffness:  305, damping: 33 },   // ← the default: menus, cards, reveals
  gentle:  { stiffness:  110, damping: 20 },
  lively:  { stiffness:  622, damping: 17 },   // noticeable overshoot
  ambient: { stiffness:   43, damping: 13 },   // background, very slow
}
stagger: { tight: 0.04, base: 0.08, relaxed: 0.15 }   // seconds between items
travel:  { hover: 4, enter: 24, section: 48 }          // pixels of entrance distance
```

**"TRAVEL ±56PX"** and **"UI K 305 · C 33"** appear in the live graph on the page.

A staggered entrance of 0.11–0.14s between items — a value people tend to approve by eye — sits between `base` and `relaxed`:
inside the range the industry publishes.

What the published spec does not include, and what often makes the difference in a finished piece: **real perspective · depth of
field · heavy motion blur · no glow.**

---

## The grammar — from What? Studio's tool descriptions

They sell an AE plugin called **`UI ANIMATOR PRO`**, and its description is really the method:

> "**Sequence** selected interface layers, apply **offset** timing, and reuse **easing** presets for product UI shots."
> · tags: `STAGGER · OFFSET · EASING`

⇒ The three ingredients of a UI shot: **a sequence of layers · a time offset · an easing preset.**

Another of their tools — **`THE EASING LAB`** (free): test a `cubic-bezier` in the browser before copying it to CSS or AE.

**Their project names** are the genre's vocabulary:
`SaaS Interface Reel` · `Metric Dash` · `Macro UI Zooms` · `Product Storyboard` · `Launch Flow` · "Dashboard motion, data story" ·
"Camera moves, product detail".

---

## Palette

Derive it from a real product screen (a screen recording or a dashboard), not from a motion brand. A bright-UI starting point that
works: canvas `#efefed` · card `#ffffff` · one accent (e.g. lime `#c8f24a`) · chips · a measured soft shadow. Measure the HEX values;
do not eyeball them.

---

## Sources
- `https://motion.dev/ui` — the registers, the stagger and the travel (code visible on the page)
- `https://www.whatstudio.digital/` — the grammar, through the tool descriptions and project names
- `https://motion.so/studio` · `https://studiomaydit.com/blog/linear-vercel-raycast-aesthetic`
