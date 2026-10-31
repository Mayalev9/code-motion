# DIRECTION — a direction doc before building

> Kept in the project: `$E/direction/SCENE.md`. Written **before** the scene, and updated when the direction changes.
> `review.py --direction` and `tools/animatic.mjs` read its shot block, so the plan, the animatic and the review all talk
> about the same shots.

## The structure

```markdown
# SCENE — title

## Brief            (SKILL.md §2 — anything not stated is marked "assumption:" and asked if it matters)
audience · platform · message · feeling/reaction · language · aspect ratio · length · role of sound · fidelity · type (QUALITY.md §2)

## The idea in one sentence
## Hero moment      what is remembered, at what second, and why it is the strongest in the film
## Three frames     opening · peak · ending — what you see in each and where the eye goes
## What we do NOT do   the temptations the idea does not need (bloom? more motion? another layer?)

## Shots
```shots
{ "size": [1080, 1920],
  "keyframes": { "open": 0.5, "peak": 6.9, "end": 11.5 },
  "shots": [
    { "t0": 0, "t1": 1.0, "role": "hook", "focus": "the button",
      "change": "a cursor enters and clicks", "why": "…", "sound": "click at 0.80",
      "frame": "optional/sketch.png" } ] }
```                 (shots are continuous: each shot's t0 = the previous shot's t1)

## Sound plan       events ⇒ SCENE.events ⇒ the sound script (ENGINE.md)
```

## §Directions — before an original film (mandatory, before the direction doc)

3–4 directions for the user to choose between. **Really different**: a different idea, a different visual language, a different
hero moment — not "the same idea in three executions". For each direction, one page:

| field | content |
|---|---|
| the idea in a sentence | what happens, and why it is interesting |
| hero moment | what is remembered, and at roughly what second |
| visual language | material · light · colour · typography — and what in it is **not** in earlier films |
| signature | what will make it theirs even if the idea is familiar |
| risk | what might not work, and what gets tested first |
| still or sketch | one frame (a still from the engine / a sketch) — so the choice is about a look, not just words |

**Do not build before a choice.** A short comparison table at the end: which direction is strongest for the brief, and why —
a recommendation, not a decision.

## For each shot — five questions, each answered in a sentence

| field | the question | weak answer | good answer |
|---|---|---|---|
| `role` | what is the shot's role in the story? | "transition" | "reveal: the page is a cube net" |
| `focus` | where is the eye looking? | "the cards" | "the tip of the right arm, which opens first" |
| `change` | what changes between the first and last frame? | "animation" | "the arms open, the camera pulls back ×2" |
| `why` | why does the motion happen? | "to make it dynamic" | "so the whole cross fits in frame before the fill" |
| `sound` | how does sound take part? | "music" | "a paper rustle for each arm, staggered like the unfold" |

An empty `why`, or "to make it dynamic" ⇒ the motion is deleted. Motion has to mean something.

## Animatic — before polish

```bash
node tools/animatic.mjs direction/SCENE.md           # → out/SCENE-animatic.mp4
```

One card per shot at its exact length, showing role · focus · change · why · sound. Each shot can have a `frame` — a sketch,
a frame from an earlier version, or a quick still from `tools/still.mjs`.

Watch the animatic **once at normal speed** and ask:
1. Does the hero moment fall in the right place and get enough time?
2. Is there a shot without a role? Two shots with the same role?
3. Where is it boring? (a long shot with no change and no reason to hold)
4. Does the ending give a moment to take it in?

A bad answer ⇒ **change the idea or the shots**, and only then build. Do not fix with bloom, 3D or motion blur.

## After every render
```bash
python3 $S/review.py out/SCENE.mp4 \
        --direction direction/SCENE.md --prev out/SCENE-prev.mp4 --label vN
```
Fill in the round in `direction/SCENE.review.md` (QUALITY.md §3).
