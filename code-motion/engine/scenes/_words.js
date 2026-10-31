// Word animations, with real RTL support (Hebrew, Arabic) as well as LTR.
//
// Why this is not trivial: to animate letter by letter you need a position for every letter, and fillText
// does not give you one. So we lay out by hand — measure every letter and place them right to left.
// A Latin/number run stays one unit that reads left-to-right inside the RTL sentence.

import { layer, paste, seg, easeOut, easeInOut, clamp01, rgba } from './_lib.js';

export const FONT = '"Heebo", "Rubik", "Arial Hebrew", Arial, sans-serif';

/** Splits text into tokens: each RTL letter on its own, each Latin run as one unit. */
function tokenize(text) {
  const out = [];
  let buf = '';
  const isLatin = c => /[A-Za-z0-9@#.+_-]/.test(c);
  for (const c of [...text]) {
    if (isLatin(c)) { buf += c; continue; }
    if (buf) { out.push(buf); buf = ''; }
    out.push(c);
  }
  if (buf) out.push(buf);
  return out;
}

/**
 * Right-to-left layout around a centre of 0.
 * Returns each token's LEFT edge (because that is how we draw with textAlign:'left').
 */
export function layoutRTL(ctx, text, fontStr) {
  ctx.save();
  ctx.font = fontStr;
  ctx.direction = 'ltr';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  const toks = tokenize(text);
  const w = toks.map(t => ctx.measureText(t).width);
  const total = w.reduce((a, b) => a + b, 0);
  let x = total / 2;              // start at the right edge
  const items = [];
  for (let i = 0; i < toks.length; i++) {
    x -= w[i];
    items.push({ t: toks[i], x, w: w[i], i, isSpace: toks[i] === ' ' });
  }
  ctx.restore();
  return { items, total };
}

/** Draws a single token with its own transform. */
function drawTok(ctx, it, cx, cy, fontStr, { dx = 0, dy = 0, sc = 1, rot = 0, alpha = 1, blur = 0, color = '#fff' } = {}) {
  if (alpha <= 0.003) return;
  ctx.save();
  ctx.font = fontStr;
  ctx.direction = 'ltr';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.globalAlpha = alpha;
  if (blur > 0.15) ctx.filter = `blur(${blur}px)`;
  // rotate and scale around the token's own centre
  const mx = cx + it.x + it.w / 2, my = cy;
  ctx.translate(mx + dx, my + dy);
  ctx.rotate(rot);
  ctx.scale(sc, sc);
  ctx.fillStyle = color;
  ctx.fillText(it.t, -it.w / 2, 0);
  ctx.restore();
}

// ── animation styles ──────────────────────────────────────────────────────
// all take p (0..1 inside the beat) and draw onto ctx.

export const STYLES = {
  /** typing with a blinking cursor */
  typed(ctx, { L, cx, cy, font, p, S }) {
    const n = Math.floor(clamp01(p / 0.62) * (L.items.length + 1));
    let lastX = L.total / 2;
    L.items.forEach((it, i) => {
      if (i >= n) return;
      drawTok(ctx, it, cx, cy, font, { alpha: 1 });
      lastX = it.x;
    });
    if (p < 0.85 && Math.floor(p * 9) % 2 === 0) {
      ctx.save();
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.fillRect(cx + lastX - 7 * S, cy - L.fs * 0.78, 3 * S, L.fs * 0.86);
      ctx.restore();
    }
  },

  /** letters converge from random spots and lock in */
  assemble(ctx, { L, cx, cy, font, p, rnd }) {
    L.items.forEach((it, i) => {
      const d = clamp01((p - i * 0.028) / 0.55);
      const e = easeOut(d);
      const r = rnd(i);
      drawTok(ctx, it, cx, cy, font, {
        dx: (r.a - 0.5) * 520 * (1 - e),
        dy: (r.b - 0.5) * 340 * (1 - e),
        rot: (r.c - 0.5) * 1.5 * (1 - e),
        sc: 0.55 + 0.45 * e,
        alpha: e,
        blur: (1 - e) * 13,
      });
    });
  },

  /** letters rise from behind a cut — the caption classic */
  riseMask(ctx, { L, cx, cy, font, p }) {
    const h = L.fs * 1.25;
    ctx.save();
    ctx.beginPath();
    ctx.rect(cx - L.total / 2 - 40, cy - h, L.total + 80, h + L.fs * 0.35);
    ctx.clip();
    L.items.forEach((it, i) => {
      const d = clamp01((p - i * 0.022) / 0.5);
      const e = easeOut(d);
      drawTok(ctx, it, cx, cy, font, { dy: (1 - e) * h, alpha: 1 });
    });
    ctx.restore();
  },

  /** punch: enters big and blurred and settles */
  punch(ctx, { L, cx, cy, font, p }) {
    const e = easeOut(clamp01(p / 0.34));
    L.items.forEach((it, i) => {
      const d = clamp01((p - i * 0.012) / 0.34);
      const k = easeOut(d);
      drawTok(ctx, it, cx, cy, font, {
        sc: 1.9 - 0.9 * k,
        alpha: k,
        blur: (1 - k) * 22,
      });
    });
    return e;
  },
};

/** a light sweep that scans the word — coloured with a gradient */
export function sweep(ctx, { cx, cy, L, p, S }) {
  const x = cx - L.total / 2 - 80 + p * (L.total + 160);
  const g = ctx.createLinearGradient(x - 90 * S, 0, x + 90 * S, 0);
  g.addColorStop(0, 'rgba(120,200,255,0)');
  g.addColorStop(0.5, 'rgba(205,232,255,0.92)');
  g.addColorStop(1, 'rgba(150,120,255,0)');
  // Do NOT set the composite here! The caller decides ('source-atop' so
  // the light paints only the letters). Setting it here overrode that and drew a rectangle on the transparent area.
  ctx.save();
  ctx.fillStyle = g;
  ctx.fillRect(cx - L.total / 2 - 100, cy - L.fs * 0.95, L.total + 200, L.fs * 1.25);
  ctx.restore();
}

/** soft glow behind the line, like on pills */
export function backGlow(ctx, W, H, cx, cy, L, amt, color, S) {
  if (amt <= 0.01) return;
  // stretched along the line and flat in height — a glow that sits *behind text*,
  // not a round blob that takes over the frame.
  const g = layer(W, H, 46 * S, x => {
    x.save();
    x.translate(cx, cy - L.fs * 0.28);
    x.scale(1, 0.42);
    const rad = L.total * 0.62 + 90 * S;
    const rg = x.createRadialGradient(0, 0, 0, 0, 0, rad);
    rg.addColorStop(0, rgba(color, 0.85));
    rg.addColorStop(0.45, rgba(color, 0.30));
    rg.addColorStop(1, rgba(color, 0));
    x.fillStyle = rg;
    x.beginPath(); x.arc(0, 0, rad, 0, Math.PI * 2); x.fill();
    x.restore();
  });
  paste(ctx, g, 0.55 * amt);
}
