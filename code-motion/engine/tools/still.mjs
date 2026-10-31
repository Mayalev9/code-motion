// Single frames from a scene: node tools/still.mjs SCENE t1,t2,... out-prefix  ⇒ out-prefix_<t>.png
import { chromium } from 'playwright-core';
import fs from 'node:fs'; import path from 'node:path'; import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { findChrome, CHROME_HELP } from './chrome.mjs';
const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [scene, times, prefix] = process.argv.slice(2);
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
if (!scene || !times || !prefix) { console.error('Usage: node tools/still.mjs SCENE t1,t2,... out-prefix'); process.exit(2); }
const browser = await chromium.launch({ executablePath: CHROME, args: ['--force-color-profile=srgb'] });
const page = await browser.newPage();
page.on('pageerror', e => console.error('Page error:', e.message));
await page.goto(`${base}/host.html`);
await page.evaluate(async ([src, ab]) => { await window.__load(src, ab); }, [`${base}/scenes/${scene}.js`, base]);
for (const ts of times.split(',')) {
  const t = Number(ts);
  const t0 = Date.now();
  const url = await page.evaluate(a => window.__frame(a[0], 1, 0.5, 30), [t]);
  fs.writeFileSync(`${prefix}_${ts}.png`, Buffer.from(url.slice('data:image/png;base64,'.length), 'base64'));
  console.log(`t=${ts}  ${Date.now() - t0}ms`);
}
await browser.close(); server.close();
