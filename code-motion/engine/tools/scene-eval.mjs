// Runs an expression on a scene module inside Chrome (OffscreenCanvas · WebGL) and prints JSON.
// Usage: node tools/scene-eval.mjs SCENE "m => m.SCENE.selftest()"
import { chromium } from 'playwright-core';
import fs from 'node:fs'; import path from 'node:path'; import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { findChrome, CHROME_HELP } from './chrome.mjs';
const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [scene, expr] = process.argv.slice(2);
const MIME = { '.html': 'text/html', '.js': 'text/javascript' };
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
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage();
page.on('pageerror', e => console.error('Page error:', e.message));
await page.goto(`${base}/host.html`);
const out = await page.evaluate(async ([src, ex]) => {
  const m = await import(src);
  const f = eval(ex);
  return JSON.stringify(await f(m));
}, [`${base}/scenes/${scene}.js`, expr]);
console.log(out);
await browser.close(); server.close();
