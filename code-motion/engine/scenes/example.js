// example — a 5-second starter scene that touches the main parts of the engine:
// a spring entrance, a glowing border traced around a rounded rectangle, letters that rise
// one by one, blurred light layers, bloom, and motion blur. Everything is a function of t.
//
// Render it:   node render.mjs example
// Check it:    node gate.mjs --scene example
// Copy this file to start your own scene.
import { resetFrame, layer, paste, roundRect, seg, easeOut, mix, rgba } from './_lib.js';
import { applyPost } from './_post.js';
import { spring } from './_spring.js';

const W = 1920, H = 1080;
const WORD = 'Made with code';
const FONT = '600 92px "Helvetica Neue", Helvetica, Arial, sans-serif';   // decision: a system font, so it works everywhere
const ORANGE = [217, 119, 87], VIOLET = [150, 120, 255];                  // decision

export const SCENE = {
  name: 'example',
  width: W, height: H, fps: 30, duration: 5.0,
  samples: 4, shutter: 0.55,   // motion blur: 4 sub-samples per frame
  draw,
};

// A point on the perimeter of a rounded rectangle, at fraction u (0..1) clockwise from top-centre.
function perimeterPoint(x, y, w, h, r, u) {
  const straightW = w - 2 * r, straightH = h - 2 * r, arc = Math.PI * r / 2;
  const segs = [straightW / 2, arc, straightH, arc, straightW, arc, straightH, arc, straightW / 2];
  const total = segs.reduce((a, b) => a + b, 0);
  let d = ((u % 1) + 1) % 1 * total;
  const cx = x + w / 2;
  const corner = (ccx, ccy, a0, k) => [ccx + r * Math.cos(a0 + k * Math.PI / 2), ccy + r * Math.sin(a0 + k * Math.PI / 2)];
  const steps = [
    k => [cx + k * straightW / 2, y],
    k => corner(x + w - r, y + r, -Math.PI / 2, k),
    k => [x + w, y + r + k * straightH],
    k => corner(x + w - r, y + h - r, 0, k),
    k => [x + w - r - k * straightW, y + h],
    k => corner(x + r, y + h - r, Math.PI / 2, k),
    k => [x, y + h - r - k * straightH],
    k => corner(x + r, y + r, Math.PI, k),
    k => [x + r + k * straightW / 2, y],
  ];
  for (let i = 0; i < segs.length; i++) {
    if (d <= segs[i] || i === segs.length - 1) return steps[i](segs[i] ? Math.min(1, d / segs[i]) : 0);
    d -= segs[i];
  }
}

function draw(ctx, t) {
  resetFrame(ctx, W, H);

  // ── the room: a deep violet base with two soft lights drifting slowly (keeps the frame alive, never pure black) ──
  ctx.fillStyle = '#1b1726';                                                    // decision
  ctx.fillRect(0, 0, W, H);
  const lights = layer(W, H, 120, x => {
    x.fillStyle = rgba(VIOLET, 0.55);
    x.beginPath(); x.arc(W * (0.30 + 0.06 * Math.sin(t * 0.9)), H * (0.35 + 0.05 * Math.cos(t * 0.7)), 420, 0, Math.PI * 2); x.fill();
    x.fillStyle = rgba(ORANGE, 0.45);
    x.beginPath(); x.arc(W * (0.72 + 0.05 * Math.cos(t * 0.8)), H * (0.68 + 0.06 * Math.sin(t * 1.1)), 380, 0, Math.PI * 2); x.fill();
  });
  paste(ctx, lights, 0.8);

  // ── the pill: springs in from 0.2s ──
  const s = spring(Math.max(0, t - 0.2), 'ui');
  const pw = mix(260, 980, s), ph = 200, pr = ph / 2;
  const px = (W - pw) / 2, py = (H - ph) / 2;

  ctx.fillStyle = '#0b0b0f';
  roundRect(ctx, px, py, pw, ph, pr);
  ctx.fill();

  // ── a glowing comet that traces the border (0.5s → 2.3s draws it, then it keeps orbiting) ──
  const trace = easeOut(seg(t, 0.5, 2.3));
  const head = 0.05 + t * 0.22;
  const comet = (x) => {
    const N = 420;
    for (let i = 0; i < N; i++) {
      const u = head - (i / N) * mix(0.02, 0.55, trace);
      const [a, b] = perimeterPoint(px, py, pw, ph, pr, u);
      const k = 1 - i / N;
      const c = [0, 1, 2].map(j => Math.round(mix(VIOLET[j], ORANGE[j], k)));
      x.fillStyle = rgba(c, 0.9 * k);
      x.beginPath(); x.arc(a, b, 2.5 + 3.5 * k, 0, Math.PI * 2); x.fill();
    }
  };
  const fade = seg(t, 0.4, 0.7);
  paste(ctx, layer(W, H, 28, comet), 0.9 * fade);    // wide soft halo
  paste(ctx, layer(W, H, 8, comet), 1.0 * fade);     // tighter glow
  ctx.save(); ctx.globalAlpha = fade; comet(ctx); ctx.restore();   // the sharp core

  // a dim full outline once the trace is complete
  ctx.save();
  ctx.strokeStyle = rgba([255, 255, 255], 0.12 * seg(t, 1.6, 2.4));
  ctx.lineWidth = 2;
  roundRect(ctx, px, py, pw, ph, pr);
  ctx.stroke();
  ctx.restore();

  // ── the word: letters rise from behind a cut, 40ms apart, from 1.0s ──
  ctx.save();
  ctx.font = FONT;
  ctx.textBaseline = 'middle';
  const total = ctx.measureText(WORD).width;
  let x = W / 2 - total / 2;
  roundRect(ctx, px + 20, py + 20, pw - 40, ph - 40, pr - 20);
  ctx.clip();                                     // the cut the letters rise from behind
  for (let i = 0; i < WORD.length; i++) {
    const ch = WORD[i];
    const p = spring(Math.max(0, t - 1.0 - i * 0.04), 'ui');
    ctx.fillStyle = rgba([245, 245, 250], p);
    ctx.fillText(ch, x, H / 2 + (1 - p) * 70);
    x += ctx.measureText(ch).width;
  }
  ctx.restore();

  applyPost(ctx, W, H, { bloom: 0.45, threshold: 0.6, chroma: 0.006 });
}
