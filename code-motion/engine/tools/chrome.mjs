// Finds a Chrome/Chromium binary on any machine.
// Order: CHROME_PATH env var → common install locations (macOS, Windows, Linux)
//        → Chromium downloaded by `npx playwright install chromium`.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const CANDIDATES = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
    path.join(os.homedir(), 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
  ],
  win32: [
    path.join(process.env['PROGRAMFILES'] || 'C:\\Program Files', 'Google\\Chrome\\Application\\chrome.exe'),
    path.join(process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)', 'Google\\Chrome\\Application\\chrome.exe'),
    path.join(process.env['LOCALAPPDATA'] || '', 'Google\\Chrome\\Application\\chrome.exe'),
  ],
  linux: ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'],
};

function onPath(cmd) {
  try {
    const which = process.platform === 'win32' ? 'where' : 'which';
    return execFileSync(which, [cmd], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).split('\n')[0].trim() || null;
  } catch { return null; }
}

async function playwrightChromium() {
  try {
    const { chromium } = await import('playwright-core');
    const p = chromium.executablePath();
    return p && fs.existsSync(p) ? p : null;
  } catch { return null; }
}

export async function findChrome() {
  if (process.env.CHROME_PATH) return fs.existsSync(process.env.CHROME_PATH) ? process.env.CHROME_PATH : null;
  for (const c of CANDIDATES[process.platform] || []) {
    if (path.isAbsolute(c)) { if (fs.existsSync(c)) return c; }
    else { const p = onPath(c); if (p) return p; }
  }
  return playwrightChromium();
}

export const CHROME_HELP =
  'Chrome was not found. Install Google Chrome, or run `npx playwright-core install chromium` in this folder, '
  + 'or point to a browser with CHROME_PATH=/path/to/chrome.';
