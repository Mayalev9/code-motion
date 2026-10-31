// Animatic — check story and pacing BEFORE building. One card per shot, lasting the shot's length.
//
// Usage:  node tools/animatic.mjs direction/SCENE.md [--out out/SCENE-animatic.mp4] [--audio x.wav]
//
// Reads the ```shots``` block from the direction doc (DIRECTION.md). For each shot: number · role ·
// focus · what changes · why · sound, plus a time bar. If a shot has `frame` (a path to an image —
// a sketch, a frame from an earlier version), it becomes the card's background.
//
// ⚠️ An animatic checks ORDER, LENGTH and the HERO MOMENT — not the look. If it is boring or unclear,
//    change the idea/direction. Polish will not save it (QUALITY.md §4).
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { findChrome, CHROME_HELP } from './chrome.mjs';

const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { values: o, positionals } = parseArgs({ allowPositionals: true,
  options: { out: { type: 'string' }, audio: { type: 'string' } } });
const src = positionals[0];
if (!src || !fs.existsSync(src)) { console.error('Usage: node tools/animatic.mjs direction/SCENE.md'); process.exit(2); }
const md = fs.readFileSync(src, 'utf8');
const m = md.match(/```shots\s*\n([\s\S]*?)\n```/);
if (!m) { console.error(`No \`\`\`shots block in ${src}`); process.exit(1); }
const D = JSON.parse(m[1]);
const [W, H] = D.size || [1080, 1920];
const shots = D.shots;
const total = shots[shots.length - 1].t1;
for (let i = 0; i < shots.length; i++) {
  if (!(shots[i].t1 > shots[i].t0)) throw new Error(`shot ${i + 1}: t1 must be after t0`);
  if (i && Math.abs(shots[i].t0 - shots[i - 1].t1) > 1e-6) throw new Error(`shot ${i + 1}: gap/overlap with the previous shot`);
}
const name = path.basename(src).replace(/\.md$/, '');
const out = path.resolve(o.out || path.join(HERE, 'out', `${name}-animatic.mp4`));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'animatic-'));

const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const CHROME = await findChrome();
if (!CHROME) { console.error(CHROME_HELP); process.exit(1); }
const browser = await chromium.launch({ executablePath: CHROME });
try {
  const page = await browser.newPage({ viewport: { width: W / 2, height: H / 2 }, deviceScaleFactor: 2 });
  const list = [];
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i];
    const img = s.frame ? `url(data:image/png;base64,${fs.readFileSync(path.resolve(path.dirname(src), s.frame)).toString('base64')})` : 'none';
    const key = Object.entries(D.keyframes || {}).filter(([, t]) => t >= s.t0 && t < s.t1).map(([k]) => k);
    await page.setContent(`<!doctype html><html dir="ltr" lang="en"><body style="margin:0;width:${W / 2}px;height:${H / 2}px;
      font:15px/1.45 -apple-system,system-ui,sans-serif;background:#1b1b1e ${img} center/cover no-repeat;color:#f2f2f0;display:flex;flex-direction:column;justify-content:flex-end">
      <div style="background:rgba(12,12,14,.82);padding:18px 18px 22px">
        <div style="font-size:12px;opacity:.6"><bdi dir="ltr">${s.t0.toFixed(2)}–${s.t1.toFixed(2)}</bdi>s · <bdi dir="ltr">${(s.t1 - s.t0).toFixed(2)}</bdi>s</div>
        <div style="font-size:26px;font-weight:700;margin:2px 0 8px">#${i + 1} ${esc(s.role)}
          ${key.length ? `<span style="font-size:13px;background:#c8f24a;color:#111;border-radius:10px;padding:2px 8px;margin-inline-start:6px">${esc(key.join(' · '))}</span>` : ''}</div>
        <div><b>Focus:</b> ${esc(s.focus)}</div><div><b>Changes:</b> ${esc(s.change)}</div>
        <div><b>Why:</b> ${esc(s.why)}</div><div><b>Sound:</b> ${esc(s.sound)}</div>
        <div style="height:6px;background:#333;border-radius:3px;margin-top:12px;position:relative">
          <div style="position:absolute;inset-inline-start:${(s.t0 / total) * 100}%;width:${((s.t1 - s.t0) / total) * 100}%;height:6px;background:#c8f24a;border-radius:3px"></div></div>
      </div></body></html>`);
    const f = path.join(tmp, `${String(i).padStart(3, '0')}.png`);
    await page.screenshot({ path: f });
    list.push(`file '${f}'\nduration ${(s.t1 - s.t0).toFixed(4)}`);
  }
  list.push(`file '${path.join(tmp, String(shots.length - 1).padStart(3, '0') + '.png')}'`);  // concat: the last shot must be repeated
  fs.writeFileSync(path.join(tmp, 'list.txt'), list.join('\n'));
  const args = ['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(tmp, 'list.txt')];
  if (o.audio) args.push('-i', path.resolve(o.audio), '-map', '0:v', '-map', '1:a', '-af', 'apad', '-c:a', 'aac');
  args.push('-t', String(total), '-vf', `scale=${W / 2}:${H / 2},fps=30,format=yuv420p`, '-c:v', 'libx264', out);
  await new Promise((res, rej) => { const p = spawn('ffmpeg', args, { stdio: 'inherit' }); p.on('close', c => c ? rej(new Error('ffmpeg ' + c)) : res()); });
  console.log(`✓ ${out}  (${shots.length} shots · ${total}s)`);
} finally {
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}
