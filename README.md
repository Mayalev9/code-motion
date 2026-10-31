# code-motion — a Claude Code skill for motion graphics from code

Give Claude a video, and it rebuilds it — shot by shot, measured, not guessed — as code that renders to MP4.
Or give it an idea, and it makes original motion the same way.

No After Effects. No keyframes. No video model, no credits. Every frame is computed by a function, `draw(ctx, t)`,
rendered in headless Chrome and encoded with ffmpeg.

## What's inside

```
code-motion/
├── SKILL.md          ← what Claude reads: the workflow, the rules, the gates
├── references/       ← replication method, measurement traps, engine traps, API, quality guide
├── scripts/          ← measuring and comparison tools (side-by-side, blink, per-frame diff, gates)
└── engine/           ← the renderer: 2D canvas, WebGL, real 3D, motion blur, bloom, springs, a starter scene
```

## Install

1. **Requirements:** [Claude Code](https://claude.com/claude-code), Node 20+, Google Chrome (or Chromium), ffmpeg,
   Python 3 with `numpy` and `Pillow`.

   ```bash
   # macOS
   brew install node ffmpeg python && pip3 install numpy pillow
   # Ubuntu/Debian
   sudo apt install nodejs npm ffmpeg python3-pip && pip3 install numpy pillow
   # Windows
   winget install OpenJS.NodeJS ffmpeg Python.Python.3 && pip install numpy pillow
   ```

2. **Copy the skill** into your Claude Code skills folder:

   ```bash
   git clone <this repository> /tmp/code-motion
   mkdir -p ~/.claude/skills
   cp -R /tmp/code-motion/code-motion ~/.claude/skills/
   ```

   (Or download the ZIP and put the `code-motion` folder in `~/.claude/skills/`.)

3. **Start Claude Code in any project folder** and ask for motion. The first time, Claude copies the engine into a `motion/`
   folder in your project, runs `npm install`, and runs a health check (`node doctor.mjs`) that tells you exactly what to install
   if anything is missing.

## Try it

> Replicate the first two seconds of this video, 1:1: `path/to/reference.mp4`

> Make a 6-second 9:16 intro for my channel: the title writes itself in glowing light.

Start small. Two seconds of a reference is enough to learn the loop:
**break it into shots → measure → build one shot → compare side by side → fix → next shot.**

## How it works

- **Measure, don't guess.** Fonts, colours, positions and timing are measured from the source frame by frame. Every number in the
  code is marked `measured`, `estimated` or `decision`.
- **Compare after every shot.** `sbs.py` renders your version next to the original — side by side, a frozen blink, full-resolution
  overlays — and logs every difference with a severity.
- **Gates that prove themselves.** Every gate has a `--selftest` that injects the bug it is meant to catch and checks that it fails
  for the right reason. A green gate is a sanity check, not an approval — the skill says what it does *not* check.
- **Honest reports.** Claude cannot watch in real time or listen to audio; the skill makes it say so instead of pretending.

## Check your install

```bash
cd motion                       # the folder Claude created in your project
node doctor.mjs                 # environment check
node gate.mjs --selftest        # engine gates, each proven to catch its bug
node render.mjs example         # → out/example.mp4
```

## Notes

- Replicating a brand's ad is a great way to learn. If you publish the result, credit the original, and don't use the brand's logo,
  audio or assets without permission.
- Fonts: put the font files you have the right to use in `motion/assets/fonts/` and declare them in the scene — a font that is only
  installed on your machine renders differently elsewhere.

## License

MIT — see `LICENSE`.
