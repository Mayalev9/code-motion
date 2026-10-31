// Renders a scene to video — headless Chrome draws every frame, ffmpeg encodes.
//
// Usage:
//   node render.mjs SCENE [--fps N] [--mblur N] [--shutter X] [--from S --to S]
//                         [--out file.mp4] [--force] [--audio file.wav | --no-audio]
//                         [--keep-frames] [--frames-only] [--scale N] [--tag709]
//
//   --out          Destination. **An explicit destination that already exists is not
//                  overwritten without --force.** The default out/SCENE.mp4 is the
//                  renderer's own output and is overwritten.
//   --audio        WAV to mux. Without the flag: `SCENE.soundtrack` if defined. --no-audio = silent.
//                  Audio is trimmed/padded to exactly the video length (no -shortest).
//   --keep-frames  Keep the PNG folder after a successful encode (default: deleted).
//   --frames-only  Stop before encoding and hand over the PNG sequence instead.
//   --scale N      Render at N× resolution (1–4). Scenes keep drawing in logical space.
//   --tag709       Encode as explicitly tagged bt709 (for delivery). See tools/_color.mjs.
//
// If the scene defines `SCENE.events`, they are written to out/SCENE.events.json —
// **one event timeline** that a sound script reads, instead of duplicating constants.
//
// Chrome is found automatically (tools/chrome.mjs); CHROME_PATH overrides. `node doctor.mjs` checks the setup.
import { chromium } from 'playwright-core';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { colorPath } from './tools/_color.mjs';
import { findChrome, CHROME_HELP } from './tools/chrome.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// Strict parsing: an unknown flag or a missing value is an error
// (a hand-rolled parser once rendered `--fps 30 myscene` as a scene called "30").
let opts, positionals;
try {
  ({ values: opts, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      fps: { type: 'string' }, mblur: { type: 'string' }, shutter: { type: 'string' },
      from: { type: 'string' }, to: { type: 'string' }, out: { type: 'string' },
      audio: { type: 'string' }, 'no-audio': { type: 'boolean' },
      force: { type: 'boolean' }, 'keep-frames': { type: 'boolean' }, scale: { type: 'string' },
      'frames-only': { type: 'boolean' }, tag709: { type: 'boolean' },
    },
  }));
} catch (e) {
  console.error(`Argument error: ${e.message}\nUsage: node render.mjs SCENE [--fps N] [--out file.mp4] ...`);
  process.exit(2);
}
if (positionals.length !== 1) {
  console.error(positionals.length ? `Expected one scene, got: ${positionals.join(' ')}`
                                   : 'Usage: node render.mjs SCENE   (a file in scenes/, without .js)');
  process.exit(2);
}
if (opts.audio && opts['no-audio']) { console.error('--audio and --no-audio contradict each other'); process.exit(2); }
const sceneName = positionals[0];

// ── provenance ────────────────────────────────────────────────────────────
// Every render writes a manifest that ties the output to the exact code, assets
// and tool versions it was made with — so an older version can be explained or rebuilt.
const sha = f => { try { return crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex').slice(0, 16); } catch { return null; } };
const ver = (cmd, args) => { try { return execFileSync(cmd, args, { encoding: 'utf8' }).split('\n')[0].trim(); } catch { return null; } };

function sceneDeps(file, seen = new Set()) {
  if (seen.has(file) || !fs.existsSync(file)) return seen;
  seen.add(file);
  const src = fs.readFileSync(file, 'utf8');
  for (const m of src.matchAll(/from\s+'(\.[^']+)'/g)) {
    seen.add(path.resolve(path.dirname(file), m[1]));
    sceneDeps(path.resolve(path.dirname(file), m[1]), seen);
  }
  return seen;
}

function writeManifest({ fps, total, audioSrc, SCALE, meta }) {
  const deps = {};
  for (const f of sceneDeps(scenePath)) deps[path.relative(HERE, f)] = sha(f);
  const man = {
    output: path.relative(HERE, out), 'sha256-16': sha(out),
    scene: sceneName, jobId,
    created: new Date().toISOString(),
    fps, frames: total, seconds: Number((total / fps).toFixed(6)),
    scale: SCALE, size: `${meta.width * SCALE}x${meta.height * SCALE}`,
    audio: audioSrc ? path.relative(HERE, audioSrc) : null,
    'audio-sha': audioSrc ? sha(audioSrc) : null,
    code: deps,
    environment: {
      node: process.version,
      ffmpeg: (ver('ffmpeg', ['-version']) || '').replace('ffmpeg version ', ''),
      chrome: chromeVersion || null,
      platform: `${process.platform}-${process.arch}`,
    },
    note: 'The manifest records HOW the file was made — not that it is correct or approved.',
  };
  fs.writeFileSync(out.replace(/\.mp4$/, '') + '.manifest.json', JSON.stringify(man, null, 1));
}

const scenePath = path.join(HERE, 'scenes', `${sceneName}.js`);
if (!fs.existsSync(scenePath)) { console.error(`No such scene: ${scenePath}`); process.exit(1); }

const outDir = path.join(HERE, 'out');
fs.mkdirSync(outDir, { recursive: true });
const defaultOut = path.join(outDir, `${sceneName}.mp4`);
const out = opts.out ? path.resolve(opts.out) : defaultOut;

// Every job gets its own frame folder, so two renders of the same scene never mix frames.
let chromeVersion = null;
const jobId = `${process.pid}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const jobDir = path.join(outDir, '.jobs', `${sceneName}-${jobId}`);
const frameDir = path.join(jobDir, 'frames');
// Atomic write: encode to a temp file and rename only after success,
// so a failed encode never leaves a partial file that looks like a real output.
const outTmp = path.join(jobDir, 'encode.mp4');

// Existing explicit destination ⇒ stop BEFORE minutes of rendering, not after.
if (opts.out && fs.existsSync(out) && !opts.force) {
  console.error(`Destination already exists: ${out}\nTo overwrite: --force`);
  process.exit(1);
}
if (!fs.existsSync(path.dirname(out))) {
  console.error(`Destination folder does not exist: ${path.dirname(out)}`);
  process.exit(1);
}

const CHROME = await findChrome();
if (!CHROME) { console.error(CHROME_HELP + '\nThen run: node doctor.mjs'); process.exit(1); }

// Temporary static server — dynamic import of a module does not work from file:// (CORS).
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(HERE, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(HERE) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const run = (cmd, a) => new Promise((res, rej) => {
  const p = spawn(cmd, a, { stdio: 'inherit' });
  p.on('error', rej);
  p.on('close', c => (c === 0 ? res() : rej(new Error(`${cmd} failed (${c})`))));
});

let browser, encoded = false;
try {
browser = await chromium.launch({ executablePath: CHROME, args: ['--force-color-profile=srgb'] });
chromeVersion = browser.version();   // recorded in the manifest: rasterization differs between versions
const page = await browser.newPage();
let pageError = null;
page.on('pageerror', e => { pageError ??= e; console.error('Page error:', e.message); });

await page.goto(`${base}/host.html`);
const SCALE = Math.max(1, Math.round(Number(opts.scale ?? 1)));
if (!Number.isFinite(SCALE) || SCALE < 1 || SCALE > 4) { console.error(`--scale must be 1–4 (got ${opts.scale})`); process.exit(2); }
await page.evaluate(async ([src, ab, sc]) => { await window.__load(src, ab, sc); },
                    [`${base}/scenes/${sceneName}.js`, base, SCALE]);
if (pageError) throw pageError;

const meta = await page.evaluate(() => window.__meta());
const fps = Number(opts.fps ?? meta.fps);
const samples = Number(opts.mblur ?? meta.samples);   // sub-samples for motion blur
const shutter = Number(opts.shutter ?? meta.shutter);
// --from / --to (seconds): render a section of a long scene
const tFrom = Number(opts.from ?? 0), tTo = Math.min(meta.duration, Number(opts.to ?? meta.duration));
const total = Math.round((tTo - tFrom) * fps);
if (!Number.isFinite(fps) || fps <= 0 || !Number.isInteger(samples) || samples < 1 ||
    !Number.isFinite(shutter) || shutter < 0 || !Number.isFinite(tFrom) || tFrom < 0 ||
    !Number.isFinite(tTo) || tTo <= tFrom || total < 1) {
  throw new Error('Invalid render parameters: fps>0, mblur a positive integer, shutter>=0, 0<=from<to');
}

// Soundtrack: --audio > SCENE.soundtrack, unless --no-audio
const audioSrc = opts['no-audio'] ? null
  : opts.audio ? path.resolve(opts.audio)
  : meta.soundtrack ? path.join(HERE, meta.soundtrack) : null;
if (audioSrc && !fs.existsSync(audioSrc)) throw new Error(`Audio file does not exist: ${audioSrc}`);

// One event timeline for picture and sound
const events = await page.evaluate(() => window.__events());
if (events != null) {
  // Events are tied to the OUTPUT, not the scene name, so two renders never overwrite each other
  const ev = out.replace(/\.mp4$/, '') + '.events.json';
  fs.writeFileSync(ev, JSON.stringify({ scene: meta.name, duration: meta.duration, events }, null, 1));
  console.log(`  events → ${path.relative(HERE, ev)}`);
}

// Disk space: a canvas PNG is up to ~3 bytes per pixel in the worst case (noise/grain)
const worst = meta.width * SCALE * meta.height * SCALE * 3 * total;
const free = (() => { try { const s = fs.statfsSync(outDir); return s.bavail * s.bsize; } catch { return null; } })();
const GB = b => (b / 1e9).toFixed(1) + 'GB';
if (free != null && worst > free * 0.9) {
  throw new Error(`Possibly not enough disk space: frames up to ${GB(worst)} · free ${GB(free)}. Shorten with --from/--to.`);
}
fs.mkdirSync(frameDir, { recursive: true });
console.log(`scene ${meta.name} · ${meta.width * SCALE}x${meta.height * SCALE}`
            + (SCALE > 1 ? ` (logical ${meta.width}x${meta.height} x${SCALE})` : '')
            + ` · ${fps}fps · ${meta.duration}s → ${total} frames`
  + (samples > 1 ? `  · motion blur ${samples}x (shutter ${shutter})` : '')
  + `  · temp PNG up to ${GB(worst)}` + (free != null ? ` (free ${GB(free)})` : ''));

const t0 = Date.now();
for (let i = 0; i < total; i++) {
  const t = tFrom + i / fps;
  const dataUrl = await page.evaluate(a => window.__frame(a[0], a[1], a[2], a[3]), [t, samples, shutter, fps]);
  if (pageError) throw pageError;
  fs.writeFileSync(path.join(frameDir, String(i).padStart(5, '0') + '.png'),
    Buffer.from(dataUrl.slice('data:image/png;base64,'.length), 'base64'));
  if (i % 15 === 0 || i === total - 1) {
    process.stdout.write(`\r  frame ${i + 1}/${total}  (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  }
}
console.log('');

// ⚠️ yuv420p shifts colours slightly: a HEX measured on the canvas is re-checked in
//    the encoded file (scripts/deliver_gate.py --hex).
if (opts['frames-only']) {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (fs.existsSync(out)) fs.rmSync(out, { recursive: true, force: true });
  fs.renameSync(frameDir, out);
  encoded = true;
  console.log(`✓ ${out}  · ${total} frames (not encoded)`);
} else {
const { vf: COLOR_VF, args: COLOR_ARGS } = colorPath(!!opts.tag709);
const dur = (total / fps).toFixed(6);
const ffArgs = ['-y', '-v', 'error', '-framerate', String(fps), '-i', path.join(frameDir, '%05d.png')];
if (audioSrc) {
  ffArgs.push('-i', audioSrc, '-map', '0:v', '-map', '1:a', '-af', 'apad', '-t', dur,
              '-c:a', 'aac', '-b:a', '192k');
  // a section (--from) ⇒ the audio starts at the same point
  if (tFrom > 0) ffArgs.splice(ffArgs.indexOf(audioSrc) - 1, 0, '-ss', String(tFrom));
}
ffArgs.push('-vf', COLOR_VF, ...COLOR_ARGS,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-preset', 'slow',
            '-movflags', '+faststart', outTmp);
await run('ffmpeg', ffArgs);
// Verify before renaming: a file that cannot be decoded never gets the final name.
await run('ffmpeg', ['-v', 'error', '-xerror', '-i', outTmp, '-f', 'null', '-']);
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.renameSync(outTmp, out);          // atomic within the same filesystem
encoded = true;
writeManifest({ fps, total, audioSrc, SCALE, meta });
console.log(`✓ ${out}` + (audioSrc ? `  · audio: ${path.relative(HERE, audioSrc)}` : '  · silent'));
}
} finally {
  if (browser) await browser.close();
  server.close();
  if (encoded && !opts['keep-frames'] && fs.existsSync(jobDir)) {
    fs.rmSync(jobDir, { recursive: true });
  } else if (!encoded && fs.existsSync(jobDir)) {
    // A failed encode leaves no partial file anywhere that looks like an output.
    if (opts['keep-frames']) {
      fs.rmSync(outTmp, { force: true });
      console.error(`Job folder kept for debugging: ${path.relative(HERE, jobDir)}`);
    } else {
      fs.rmSync(jobDir, { recursive: true, force: true });
    }
  }
}
