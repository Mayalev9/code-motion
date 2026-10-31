# QUALITY — judging a film artistically

> This is not a tick-box checklist. Every criterion is **a question you answer in a sentence, with the frame or the second that
> proves the answer**. "Looks good" is not an answer. `review.py` prepares the material for judging; **the judging itself is done
> by eye, on the encoded MP4.**
>
> There is no numeric quality score. A number can point to a problem (a freeze, black, a colour that shifted); it cannot say the film
> is good. (A film once passed 6/6 on every metric and the person who ordered it was not happy at all.)

---

## 1 · The questions

| # | criterion | the question | how to check |
|---|---|---|---|
| Q1 | **message** | what does the viewer know/feel at the end, in one sentence? Is it the sentence from the brief? | watch once, without stopping, then write the sentence |
| Q2 | **hero moment** | what is remembered after watching? At what second? Is it the strongest moment in the film? | the frame of that moment in `review/keys/` |
| Q3 | **originality** | what here would not look the same in any other film on this subject? | put it in words; if there is nothing — go back to the idea, not to polish |
| Q4 | **hierarchy** | in every key frame: what do you see first, second, third? Is that the right order? | frames shrunk to phone size, a one-second glance |
| Q5 | **composition** | weight, breathing room, safe margins; nothing important pushed to the edge | `review/phone/` · safe area ~12% top, ~20% bottom in reels |
| Q6 | **legibility** | every text can be read at phone size, while it is on screen, even in motion | time on screen ≥ 0.3s per word + 0.5s · check on a real-size frame |
| Q7 | **typography** ⚠️ *in a replication this is not taste but fidelity — font, weight, size, tracking and word spacing are measured against the source* | a font whose character suits the brief; consistent spacing, weight and size; natural line breaks | a 1:1 crop on a word |
| Q8 | **continuity of focus** | at every cut/transition — does the eye know where to go? Does the focus continue somewhere close, or is there a reason for the jump? | the two frames on either side of each transition, side by side |
| Q9 | **motion vs. rest** | are there places where the film breathes? Does the motion stress something, or only "animate"? | the motion curve in `review/` · declared holds |
| Q10 | **material** | is the material convincing — moving light, body, contact shadow, imperfection — or flat colour? | a 1:1 crop at two different moments: does the sheen move? |
| Q11 | **light** | a consistent light direction; contrast leads to the hero | a grey (luma) frame — is the hero brighter/darker than its surroundings? |
| Q12 | **sound** | does the sound tell something (event · weight · space) or only fill? Is it in sync? Does the film work without sound? | listen while watching · `events.json` against the audio · watch without sound |
| Q13 | **ending** | the ending gives a moment to take it in and leaves the moment/message; not cut off, not dragging | the last 2 seconds, twice |

---

## 2 · By type of film — what decides, and at what pace

The same question is answered differently by type. **First identify the type from the brief**, and only then judge.

| | fast reel (social) | slow luxury | product demo | exact replication |
|---|---|---|---|---|
| **decisive** | Q2 · Q1 · Q6 | Q10 · Q11 · Q9 | Q1 · Q4 · Q6 | **fidelity in every shot, including small details** — `sbs.py` + gap log (REPLICATION.md) |
| **pace** | a hook in the first 1–2s; a cut/beat every 0.5–2s; acceleration towards the peak | a cut every 3–6s or fewer; long fades; silence allowed | every action is visible, and no faster than it can be read; "skeleton → fill" | **the source's** — not "improved" |
| **language** | strong contrast, big typography, one key word | low, precise contrast, wide spacing, serif | a real interface, perspective, depth, a cursor that acts | the source's, including its flaws |
| **sound** | beats on cuts; works without sound (captions/text) | room, material, few events | clicks/confirmations on actions | the source's, or silence if that is what it was |
| **typical failure** | emphasis on every line · no hero moment | glow instead of material · too fast | decorative motion that hides the product | an "improvement" the source never made · REF\|OURS too late |
| **Q not relevant** | — | Q9 reversed: the rest is the content | Q3 secondary to clarity | Q3 · Q7 (the source's taste, not ours) |

A type not on the list (UI explainer, title, loop): pick the closest column and write in the direction doc what differs.

---

## 3 · A review round — the format

Every round is written to `direction/SCENE.review.md` (created by `review.py`, filled in by eye):

```
## Round N · vN · date
Watched: [ ] full MP4 · [ ] at phone size · [ ] with sound · [ ] without sound
       (anything not done — write that it was not done, and why. ⛔ do not present a green gate in its place)

| weakness (concrete, with the second/frame) | Q# | cause | change made |
|---|---|---|---|
| "the title at 2.1 is readable only after the camera stops" | Q6 | camera move at 0.9rad/s over the text | slowed to 0.5 + a 0.4s hold |

Comparison with the previous version: review/compare-vN-1.png — what improved, what got worse
```

**Rule:** a change that adds complexity must answer a weakness in the table. An addition without a weakness = noise.
**Rule:** if a weakness returns for two rounds — the problem is in the idea or the direction, not in the polish. Go back to DIRECTION.

---

## 4 · What not to do

- Do not declare "studio level" / "beautiful" on the strength of a number, a green gate, or because the steps were done.
- Do not fix a weak idea with bloom, 3D or motion blur. A weak animatic ⇒ a new idea.
- Do not judge from a contact sheet alone: it does not show pacing, a short freeze or sync.
- When you could not actually watch or listen — **say so**, in words, in the report.

## ⚠️ Typography in a replication is not a matter of taste

In an **original** film Q7 is a preference. In a **replication** it is **critical**: in one replication, misidentifying the weight
(Inter-600 instead of 700) and the size (136 instead of 138) moved the ink height by 2px and the line width by 18px, and wrong word spacing
(41/32/44 vs 21/24/28) changed how the whole line looks. ⇒ **Typographic fidelity is measured**, not estimated by eye: the ink profile of a
whole word after width normalisation, ink height, stem, and word gaps.
