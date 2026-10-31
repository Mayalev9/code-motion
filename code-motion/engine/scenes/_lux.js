// Helpers for a luxury look: gold foil, hairlines, ornaments and grain.
// The difference between "expensive" and "just dark" is almost always subtlety: thin lines,
// wide spacing, long motion, and low contrast between tones.

import { layer, paste, clamp01, rgba } from './_lib.js';

export const SERIF = 'Didot, "Bodoni 72", "Hoefler Text", "Times New Roman", serif';
export const SERIF_SC = '"Bodoni 72 Smallcaps", Didot, "Times New Roman", serif';

export const GOLD = [201, 169, 106];      // #c9a96a
export const GOLD_HI = [246, 231, 193];   // #f6e7c1
export const GOLD_DK = [124, 98, 52];
export const CREAM = [242, 237, 228];     // #f2ede4

/** Left-to-right layout with letter spacing (tracking) that can be animated. */
export function layoutLTR(ctx, text, fontStr, tracking) {
  ctx.save();
  ctx.font = fontStr;
  ctx.direction = 'ltr';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  const chars = [...text];
  const w = chars.map(c => ctx.measureText(c).width);
  const total = w.reduce((a, b) => a + b, 0) + tracking * Math.max(0, chars.length - 1);
  let x = -total / 2;
  const items = [];
  for (let i = 0; i < chars.length; i++) {
    items.push({ t: chars[i], x, w: w[i], i });
    x += w[i] + tracking;
  }
  ctx.restore();
  return { items, total };
}

/**
 * Gold foil: a gradient with a glint band that travels across.
 * spec = glint position in 0..1; outside that range there is no glint, only gold.
 */
export function foil(ctx, x0, x1, spec) {
  const g = ctx.createLinearGradient(x0, 0, x1, 0);
  g.addColorStop(0.00, rgba(GOLD_DK, 1));
  g.addColorStop(0.18, rgba(GOLD, 1));
  g.addColorStop(0.46, rgba(GOLD_HI, 1));
  g.addColorStop(0.62, rgba(GOLD, 1));
  g.addColorStop(0.86, rgba(GOLD_DK, 1));
  g.addColorStop(1.00, rgba(GOLD, 1));
  if (spec >= -0.2 && spec <= 1.2) {
    const s = clamp01(spec);
    const lo = Math.max(0.0001, s - 0.10), hi = Math.min(0.9999, s + 0.10);
    g.addColorStop(lo, rgba(GOLD, 1));
    g.addColorStop(clamp01(s), 'rgba(255,250,238,1)');
    g.addColorStop(hi, rgba(GOLD, 1));
  }
  return g;
}

/** A hairline with tapered ends — stretches out from the centre. */
export function hairline(ctx, cx, y, halfWidth, alpha, S, color = GOLD) {
  if (halfWidth < 1) return;
  const g = ctx.createLinearGradient(cx - halfWidth, 0, cx + halfWidth, 0);
  g.addColorStop(0.00, rgba(color, 0));
  g.addColorStop(0.14, rgba(color, alpha * 0.85));
  g.addColorStop(0.50, rgba(color, alpha));
  g.addColorStop(0.86, rgba(color, alpha * 0.85));
  g.addColorStop(1.00, rgba(color, 0));
  ctx.save();
  ctx.fillStyle = g;
  ctx.fillRect(cx - halfWidth, y, halfWidth * 2, Math.max(1, 1.15 * S));
  ctx.restore();
}

/** A small diamond with an inner line — separates a name from a subtitle. */
export function fleuron(ctx, cx, cy, r, alpha, S) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(Math.PI / 4);
  ctx.strokeStyle = rgba(GOLD, alpha);
  ctx.lineWidth = 1.2 * S;
  ctx.strokeRect(-r, -r, r * 2, r * 2);
  ctx.fillStyle = rgba(GOLD_HI, alpha * 0.85);
  ctx.fillRect(-r * 0.30, -r * 0.30, r * 0.60, r * 0.60);
  ctx.restore();
}

/** Thin brackets in the corners of the frame. */
export function corners(ctx, W, H, inset, len, alpha, S) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.strokeStyle = rgba(GOLD, alpha);
  ctx.lineWidth = 1.1 * S;
  const x0 = inset, x1 = W - inset, y0 = inset, y1 = H - inset;
  const seg = [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]];
  for (const [x, y, sx, sy] of seg) {
    ctx.beginPath();
    ctx.moveTo(x + sx * len, y); ctx.lineTo(x, y); ctx.lineTo(x, y + sy * len);
    ctx.stroke();
  }
  ctx.restore();
}

/** Grain: the one thing that keeps black from looking digital and flat. */
const grainCache = new Map();
export function grain(ctx, W, H, t, amount, S) {
  const gw = Math.round(W / 3), gh = Math.round(H / 3);
  const key = `${gw}x${gh}`;
  let tiles = grainCache.get(key);
  if (!tiles) {
    // four pre-made tiles that alternate — cheap, and it does not look like a loop
    tiles = [];
    for (let k = 0; k < 4; k++) {
      const c = new OffscreenCanvas(gw, gh);
      const x = c.getContext('2d');
      const img = x.createImageData(gw, gh);
      let seed = 9871 + k * 7919;
      for (let i = 0; i < img.data.length; i += 4) {
        seed = (seed * 1664525 + 1013904223) >>> 0;
        const v = 128 + ((seed >>> 16) % 255 - 127) * 0.55;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = 255;
      }
      x.putImageData(img, 0, 0);
      tiles.push(c);
    }
    grainCache.set(key, tiles);
  }
  // non-negative modulo: with motion blur the first sub-sample gives a small negative t,
  // and % of a negative number returned index -1 → tile undefined → drawImage crashed.
  const tile = tiles[((Math.floor(t * 24) % 4) + 4) % 4];
  ctx.save();
  ctx.globalCompositeOperation = 'overlay';
  ctx.globalAlpha = amount;
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(tile, 0, 0, W, H);
  ctx.restore();
}

/** A warm, subtle vignette. */
export function vignette(ctx, W, H, amt) {
  const g = ctx.createRadialGradient(W * 0.5, H * 0.46, W * 0.30, W * 0.5, H * 0.5, W * 1.05);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(0.62, `rgba(6,4,2,${amt * 0.35})`);
  g.addColorStop(1, `rgba(0,0,0,${amt})`);
  ctx.save();
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  ctx.restore();
}
