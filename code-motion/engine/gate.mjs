// Mechanical gate for the engine — the only thing here that is not "I looked and it seemed fine".
//
// Five gates, each one derived from a trap that once cost a full round:
//   orientation      mirrored text from an upside-down `up` vector or a camera on the wrong side
//   text direction   the canvas inherits `direction` from the page
//   per-plane size   measurements on one plane are not valid on another plane
//   negative t       rendering crashed ONLY with --mblur (sub-samples before t=0)
//   determinism      the ground rule — `draw` is a pure function of t, or there is no motion blur
//
// Usage:
//   node gate.mjs                 # run every gate on every scene
//   node gate.mjs --scene NAME    # one scene
//   node gate.mjs --selftest      # prove that each gate catches its own bug
//
// The selftest is not decoration. A gate that has never been shown to fail on the
// original bug is not a gate — it is a good feeling. Here each gate runs again with
// the bug injected on purpose, and the run fails if it is NOT caught.

import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { findChrome, CHROME_HELP } from './tools/chrome.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const has = n => args.includes(`--${n}`);

const only = flag('scene', null);
const scenes = fs.readdirSync(path.join(HERE, 'scenes'))
  .filter(f => f.endsWith('.js') && !f.startsWith('_'))
  .map(f => f.replace(/\.js$/, ''))
  .filter(n => !only || n === only)
  .sort();
if (!scenes.length) { console.error('No scenes found'); process.exit(1); }

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(HERE, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(HERE) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const CHROME = await findChrome();
if (!CHROME) { console.error(CHROME_HELP); process.exit(1); }
const browser = await chromium.launch({ executablePath: CHROME, args: ['--force-color-profile=srgb'] });

async function run(inject, sceneList) {
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto(`${base}/gates.html`);
  const urls = sceneList.map(s => `${base}/scenes/${s}.js`);
  const r = await page.evaluate(a => window.__gates(a[0], a[1], a[2]), [base, urls, inject]);
  await page.close();
  return { ...r, pageErrors: errs };
}

const P = s => `\x1b[32m${s}\x1b[0m`, F = s => `\x1b[31m${s}\x1b[0m`, D = s => `\x1b[2m${s}\x1b[0m`;
let failed = 0;

// ── the real run ─────────────────────────────────────────────────────────
console.log(`\ngates · ${scenes.length} scene(s)\n`);
const r = await run(null, scenes);

for (const error of r.pageErrors) {
  console.log(`  ${F('✗')} page error ${D(error)}`);
  failed++;
}

for (const u of r.units) {
  console.log(`  ${u.pass ? P('✓') : F('✗')} ${u.name.padEnd(16)} ${D(u.detail)}`);
  if (!u.pass) failed++;
}
console.log('');
for (const s of r.scenes) {
  if (s.error) { console.log(`  ${F('✗')} ${s.name.padEnd(24)} ${D('did not load: ' + s.error)}`); failed++; continue; }
  const ok = s.negT.pass && s.det.pass;
  console.log(`  ${ok ? P('✓') : F('✗')} ${s.name.padEnd(24)}` +
    `${s.negT.pass ? '' : F('  negative t: ' + s.negT.detail)}` +
    `${s.det.pass ? D('  ' + s.det.detail) : F('  determinism: ' + s.det.detail)}`);
  if (!ok) failed++;
}

// ── selftest: prove that each gate catches its own bug ──────────────────
if (has('selftest')) {
  console.log(`\nselftest — each gate runs with its original bug injected. A gate that does not fail is rejected.\n`);
  const sample = [scenes.includes('example') ? 'example' : scenes[0]];
  const cases = [
    ['mirror', 'orientation', o => o.units.find(u => u.tag === 'mirror')],
    ['skip-reset', 'text direction', o => o.units.find(u => u.tag === 'skip-reset')],
    ['fixed-plane', 'per-plane size', o => o.units.find(u => u.tag === 'fixed-plane')],
    ['negative-index', 'negative t', o => o.scenes[0].negT],
    ['random', 'determinism', o => ({ pass: o.scenes[0].det.pass, detail: o.scenes[0].det.detail })],
  ];
  for (const [inject, name, pick] of cases) {
    const out = await run(inject, sample);
    const g = pick(out);
    const caught = g && !g.pass;
    console.log(`  ${caught ? P('✓') : F('✗')} ${name.padEnd(16)} ` +
      D(caught ? 'caught — ' + g.detail : 'bug was injected and the gate passed anyway'));
    if (!caught) failed++;
  }
}

await browser.close();
server.close();
console.log(failed ? F(`\n${failed} failure(s)\n`) : P('\nall passed\n'));
process.exit(failed ? 1 : 0);
