// Environment check for the engine. Exits 0 only when every required dependency is present,
// and for every missing one it prints the exact command to fix it.
// Usage:  node doctor.mjs
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { findChrome, CHROME_HELP } from './tools/chrome.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ok = s => console.log(`  \x1b[32m✓\x1b[0m ${s}`);
const bad = s => console.log(`  \x1b[31m✗\x1b[0m ${s}`);
const warn = s => console.log(`  \x1b[33m!\x1b[0m ${s}`);
let failed = 0;
const need = (cond, good, fix) => { if (cond) ok(good); else { bad(fix); failed++; } };
const sh = (cmd, a) => { try { return execFileSync(cmd, a, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); } catch { return null; } };
const mac = process.platform === 'darwin', win = process.platform === 'win32';
const install = { ffmpeg: mac ? 'brew install ffmpeg' : win ? 'winget install ffmpeg' : 'sudo apt install ffmpeg' };

console.log('\ncode-motion · environment check\n');

// Node: the requirement is read from playwright-core itself, so a package update
// can never make doctor approve a Node version that the renderer cannot run on.
const cmp = (a, b) => {
  const A = String(a).split('.').map(Number), B = String(b).split('.').map(Number);
  for (let i = 0; i < 3; i++) if ((A[i] || 0) !== (B[i] || 0)) return (A[i] || 0) - (B[i] || 0);
  return 0;
};
const pwDir = path.join(HERE, 'node_modules', 'playwright-core');
need(fs.existsSync(pwDir), 'playwright-core installed', 'playwright-core missing — run: npm install   (in this folder)');

let needNode = '18.15.0', src = 'the engine';
if (fs.existsSync(pwDir)) {
  const eng = JSON.parse(fs.readFileSync(path.join(pwDir, 'package.json'), 'utf8')).engines?.node;
  const m = eng && String(eng).match(/(\d+)(?:\.(\d+))?(?:\.(\d+))?/);
  if (m) {
    const pw = `${m[1]}.${m[2] || 0}.${m[3] || 0}`;
    if (cmp(pw, needNode) > 0) { needNode = pw; src = `playwright-core (${eng})`; }
  }
}
need(cmp(process.versions.node, needNode) >= 0, `Node ${process.versions.node} (needs ≥${needNode})`,
     `Node ${process.versions.node} — needs ${needNode} or newer (required by ${src}). Get it from https://nodejs.org`);

const CHROME = await findChrome();
need(!!CHROME, `Chrome: ${CHROME}`, CHROME_HELP);

const ff = sh('ffmpeg', ['-hide_banner', '-encoders']);
need(ff != null, 'ffmpeg', `ffmpeg missing — run: ${install.ffmpeg}`);
if (ff != null) need(/libx264/.test(ff), 'ffmpeg · libx264', 'ffmpeg was built without libx264 — install a full build (the renderer encodes with libx264)');
need(sh('ffprobe', ['-version']) != null, 'ffprobe', 'ffprobe missing (it ships with ffmpeg)');

const PY = win ? 'python' : 'python3';
const py = sh(PY, ['-c', 'import numpy, PIL; print(numpy.__version__, PIL.__version__)']);
need(py != null, `${PY} · numpy ${py ? py.trim().split(' ')[0] : ''} · Pillow ${py ? py.trim().split(' ')[1] : ''}`,
     `${PY} with numpy + Pillow missing — run: pip3 install numpy pillow   (needed by the measuring tools and gates)`);
if (sh(PY, ['-c', 'import scipy']) == null) warn('scipy not installed — optional (refmeasure falls back to numpy): pip3 install scipy');

if (CHROME) {
  const cv = sh(CHROME, ['--version']);
  const fv = sh('ffmpeg', ['-version']);
  ok(`recorded in every render manifest: Node ${process.versions.node} · ${cv ? cv.trim() : 'Chrome'} · ` +
     `${fv ? fv.split('\n')[0].replace('ffmpeg version ', 'ffmpeg ').slice(0, 40) : 'ffmpeg ?'}`);
}

try {
  fs.mkdirSync(path.join(HERE, 'out'), { recursive: true });
  const s = fs.statfsSync(path.join(HERE, 'out'));
  const gb = s.bavail * s.bsize / 1e9;
  (gb < 10 ? warn : ok)(`free space for out/: ${gb.toFixed(1)}GB` +
    (gb < 10 ? ' — 1080×1920 PNG frames are up to ~6MB each in the worst case' : ''));
} catch { warn('could not measure free space in out/'); }

console.log(failed ? `\n\x1b[31m${failed} missing — fix the lines marked ✗ and run again\x1b[0m\n`
                   : '\n\x1b[32mEnvironment OK\x1b[0m\n');
process.exit(failed ? 1 : 0);
