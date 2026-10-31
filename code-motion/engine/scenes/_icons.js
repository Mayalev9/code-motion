// Squircles and glyphs — shared base for icon scenes.
// All paths: no SVG file and no image.

import { layer, paste, squircle, rgba, clamp01 } from './_lib.js';

export const GLYPHS = {
  person(x, s) {
    x.beginPath(); x.arc(0, -s * 0.20, s * 0.20, 0, Math.PI * 2); x.fill();
    x.beginPath();
    x.moveTo(-s * 0.36, s * 0.40);
    x.quadraticCurveTo(-s * 0.34, s * 0.02, 0, s * 0.02);
    x.quadraticCurveTo(s * 0.34, s * 0.02, s * 0.36, s * 0.40);
    x.closePath(); x.fill();
  },
  note(x, s) {
    x.beginPath(); x.ellipse(-s * 0.16, s * 0.26, s * 0.20, s * 0.16, -0.3, 0, Math.PI * 2); x.fill();
    x.beginPath();
    x.moveTo(s * 0.02, s * 0.30); x.lineTo(s * 0.02, -s * 0.34);
    x.lineTo(s * 0.40, -s * 0.46); x.lineTo(s * 0.40, -s * 0.16);
    x.lineTo(s * 0.10, -s * 0.06); x.closePath(); x.fill();
  },
  eye(x, s) {
    x.beginPath();
    x.moveTo(-s * 0.44, 0);
    x.quadraticCurveTo(0, -s * 0.38, s * 0.44, 0);
    x.quadraticCurveTo(0, s * 0.38, -s * 0.44, 0);
    x.closePath(); x.fill();
    x.save(); x.globalCompositeOperation = 'destination-out';
    x.beginPath(); x.arc(0, 0, s * 0.11, 0, Math.PI * 2); x.fill();
    x.restore();
  },
  wave(x, s) {
    x.lineWidth = s * 0.15; x.lineCap = 'round'; x.lineJoin = 'round';
    x.beginPath();
    x.moveTo(-s * 0.38, s * 0.10);
    x.bezierCurveTo(-s * 0.20, -s * 0.34, -s * 0.02, s * 0.30, s * 0.14, -s * 0.06);
    x.bezierCurveTo(s * 0.24, -s * 0.28, s * 0.32, -s * 0.10, s * 0.38, s * 0.04);
    x.stroke();
  },
  search(x, s) {
    x.lineWidth = s * 0.14; x.lineCap = 'round';
    x.beginPath(); x.arc(-s * 0.06, -s * 0.10, s * 0.26, 0, Math.PI * 2); x.stroke();
    x.beginPath(); x.moveTo(s * 0.13, s * 0.10); x.lineTo(s * 0.36, s * 0.36); x.stroke();
  },
  diamond(x, s) {
    x.beginPath();
    x.moveTo(0, -s * 0.40); x.lineTo(s * 0.36, -s * 0.06);
    x.lineTo(0, s * 0.42); x.lineTo(-s * 0.36, -s * 0.06);
    x.closePath(); x.fill();
  },
  sparkle(x, s) {
    x.beginPath();
    for (let i = 0; i < 4; i++) {
      const a = (i * Math.PI) / 2;
      const ox = Math.cos(a), oy = Math.sin(a);
      const nx = Math.cos(a + Math.PI / 4) * 0.14, ny = Math.sin(a + Math.PI / 4) * 0.14;
      i ? x.lineTo(ox * s * 0.44, oy * s * 0.44) : x.moveTo(ox * s * 0.44, oy * s * 0.44);
      x.lineTo(nx * s, ny * s);
    }
    x.closePath(); x.fill();
  },
  flower(x, s) {
    for (let i = 0; i < 6; i++) {
      const a = (i * Math.PI) / 3;
      x.beginPath();
      x.ellipse(Math.cos(a) * s * 0.22, Math.sin(a) * s * 0.22, s * 0.20, s * 0.14, a, 0, Math.PI * 2);
      x.fill();
    }
  },
  bolt(x, s) {
    x.beginPath();
    x.moveTo(s * 0.10, -s * 0.44); x.lineTo(-s * 0.26, s * 0.06);
    x.lineTo(-s * 0.02, s * 0.06); x.lineTo(-s * 0.10, s * 0.44);
    x.lineTo(s * 0.28, -s * 0.08); x.lineTo(s * 0.03, -s * 0.08);
    x.closePath(); x.fill();
  },
  layers(x, s) {
    for (let i = 0; i < 3; i++) {
      const y = -s * 0.20 + i * s * 0.20;
      x.globalAlpha = 1 - i * 0.22;
      x.beginPath();
      x.moveTo(0, y - s * 0.16); x.lineTo(s * 0.36, y);
      x.lineTo(0, y + s * 0.16); x.lineTo(-s * 0.36, y);
      x.closePath(); x.fill();
    }
    x.globalAlpha = 1;
  },
  play(x, s) {
    x.beginPath();
    x.moveTo(-s * 0.20, -s * 0.34); x.lineTo(s * 0.34, 0); x.lineTo(-s * 0.20, s * 0.34);
    x.closePath(); x.fill();
  },
  grid(x, s) {
    for (let i = 0; i < 4; i++) {
      const gx = (i % 2 ? 1 : -1) * s * 0.19, gy = (i < 2 ? -1 : 1) * s * 0.19;
      x.beginPath();
      x.roundRect(gx - s * 0.15, gy - s * 0.15, s * 0.30, s * 0.30, s * 0.07);
      x.fill();
    }
  },
};

export const GLYPH_KEYS = Object.keys(GLYPHS);

export const PALETTES = [
  [[120, 255, 170], [40, 190, 255]],
  [[255, 210, 120], [255, 120, 200]],
  [[190, 160, 255], [90, 200, 255]],
  [[255, 170, 90], [255, 90, 140]],
  [[120, 255, 210], [110, 140, 255]],
  [[255, 130, 220], [150, 90, 255]],
  [[140, 220, 255], [190, 120, 255]],
  [[255, 236, 150], [120, 220, 255]],
];

/** A single icon: glow, dark body, gradient rim, and a glyph. */
export function drawIcon(ctx, W, H, {
  cx, cy, size, glyph, pal, alpha = 1, S = 1,
  glow = 0.5, rimHue = [200, 140, 255], glyphScale = 0.78, glyphAlpha = 1, rot = 0,
}) {
  if (alpha <= 0.01 || size < 2) return;

  if (glow > 0.01) {
    const g = layer(W, H, 34 * S, x => {
      x.fillStyle = rgba(rimHue, 0.85);
      squircle(x, cx, cy, size * 1.04); x.fill();
    });
    paste(ctx, g, glow * alpha);
  }

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.translate(-cx, -cy);

  squircle(ctx, cx, cy, size);
  const bodyG = ctx.createLinearGradient(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2);
  bodyG.addColorStop(0, '#151128');
  bodyG.addColorStop(0.5, '#08060f');
  bodyG.addColorStop(1, '#120a1e');
  ctx.fillStyle = bodyG;
  ctx.fill();

  squircle(ctx, cx, cy, size);
  const rimG = ctx.createLinearGradient(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2);
  rimG.addColorStop(0, rgba(rimHue, 0.95));
  rimG.addColorStop(0.35, rgba(rimHue, 0.22));
  rimG.addColorStop(0.7, rgba(rimHue, 0.32));
  rimG.addColorStop(1, 'rgba(240,225,255,0.92)');
  ctx.strokeStyle = rimG;
  ctx.lineWidth = 2.6 * S * Math.max(0.7, size / (0.30 * W));
  ctx.stroke();

  if (glyph && glyphAlpha > 0.01) {
    ctx.save();
    ctx.globalAlpha = alpha * glyphAlpha;
    ctx.translate(cx, cy);
    const gg = ctx.createLinearGradient(-size * 0.4, -size * 0.4, size * 0.4, size * 0.4);
    gg.addColorStop(0, rgba(pal[0], 1));
    gg.addColorStop(1, rgba(pal[1], 1));
    ctx.fillStyle = gg;
    ctx.strokeStyle = gg;
    GLYPHS[glyph](ctx, size * glyphScale);
    ctx.restore();
  }
  ctx.restore();
}

/** The list of beats as times in seconds. */
export function beatTimes(A) {
  if (!A || !A.beats) return [];
  return A.beats.map(b => b / A.fps);
}

/** Index of the last beat that has passed, and how long since. */
export function beatState(times, t) {
  let i = -1;
  for (let k = 0; k < times.length; k++) { if (times[k] <= t) i = k; else break; }
  return { i, age: i < 0 ? 99 : t - times[i] };
}
