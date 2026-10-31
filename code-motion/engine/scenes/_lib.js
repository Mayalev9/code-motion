// Shared helpers for every scene.

export const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v);
export const seg = (t, a, b) => clamp01((t - a) / (b - a));
export const easeOut = p => 1 - Math.pow(1 - p, 3);
export const easeInOut = p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
export const mix = (a, b, k) => a + (b - a) * k;
export const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

export function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

export function layer(W, H, blurPx, fn) {
  // The offscreen grows with the scale; otherwise a blurred layer would be stretched
  //    from the proxy resolution and lose everything 4K is meant to give.
  // The blur used to sample transparent-black outside the canvas ⇒ a dark ramp at the edge
  //    of every frame (measured: corner 71 vs 255 in the reference, |col0−col1|
  //    16.2 vs 0.03 in the reference).
  //    ⇒ margins + EDGE CLAMP (copy the outer row/column into the margins),
  //    which is exactly how a blur should behave at a border. This is a class fix: every
  //    scene that uses `layer()` with blur benefits, with no change to the scenes.
  const S = globalThis.__SCALE || 1;
  const M = blurPx ? Math.ceil(blurPx * 3) : 0;
  const c = new OffscreenCanvas((W + 2 * M) * S, (H + 2 * M) * S);
  const cx = c.getContext('2d');
  if (S !== 1 || M) cx.setTransform(S, 0, 0, S, M * S, M * S);
  fn(globalThis.__scaleCtx ? globalThis.__scaleCtx(cx, S) : cx);
  if (M) clampEdges(cx, (W + 2 * M) * S, (H + 2 * M) * S, M * S);
  return { canvas: c, blur: blurPx, scale: S, w: W + 2 * M, h: H + 2 * M, m: M };
}

// Edge clamp: stretches the outer pixel of the drawn area into the margins.
function clampEdges(cx, CW, CH, m) {
  const src = cx.canvas, iw = CW - 2 * m, ih = CH - 2 * m;
  cx.save();
  cx.setTransform(1, 0, 0, 1, 0, 0);
  // NOT `copy` — it replaces the WHOLE canvas, not the target rectangle: the first
  //    attempt erased the entire image and left one corner.
  //    The margins are transparent, so `source-over` is exactly an edge clamp.
  cx.globalCompositeOperation = 'source-over';
  cx.drawImage(src, m, m, 1, ih, 0, m, m, ih);               // left
  cx.drawImage(src, CW - m - 1, m, 1, ih, CW - m, m, m, ih); // right
  cx.drawImage(src, m, m, iw, 1, m, 0, iw, m);               // top
  cx.drawImage(src, m, CH - m - 1, iw, 1, m, CH - m, iw, m); // bottom
  cx.drawImage(src, m, m, 1, 1, 0, 0, m, m);                 // corners
  cx.drawImage(src, CW - m - 1, m, 1, 1, CW - m, 0, m, m);
  cx.drawImage(src, m, CH - m - 1, 1, 1, 0, CH - m, m, m);
  cx.drawImage(src, CW - m - 1, CH - m - 1, 1, 1, CW - m, CH - m, m, m);
  cx.restore();
}

export function paste(ctx, l, alpha = 1, op = 'lighter') {
  ctx.save();
  ctx.globalCompositeOperation = op;
  ctx.globalAlpha = clamp01(alpha);
  // The Proxy multiplies the blur by the scale; drawing happens in LOGICAL size, so
  // the mapping is 1:1 against a source that is already S× larger.
  ctx.filter = l.blur ? `blur(${l.blur}px)` : 'none';
  // ⚠️ At scale=1 the old 3-argument call is kept EXACTLY: even when the sizes are
  //    equal, the 5-argument form takes a different sampling path in Chrome
  //    and breaks byte-for-byte identity.
  const m = l.m || 0;
  if ((l.scale ?? 1) === 1 && !m) ctx.drawImage(l.canvas, 0, 0);
  else ctx.drawImage(l.canvas, -m, -m, l.w ?? l.canvas.width, l.h ?? l.canvas.height);
  ctx.restore();
}

export function roundRect(x, px, py, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  x.beginPath();
  x.moveTo(px + rr, py);
  x.lineTo(px + w - rr, py); x.arcTo(px + w, py, px + w, py + rr, rr);
  x.lineTo(px + w, py + h - rr); x.arcTo(px + w, py + h, px + w - rr, py + h, rr);
  x.lineTo(px + rr, py + h); x.arcTo(px, py + h, px, py + h - rr, rr);
  x.lineTo(px, py + rr); x.arcTo(px, py, px + rr, py, rr);
  x.closePath();
}

// iOS-icon-style squircle — a continuous corner, not a fixed radius
export function squircle(x, cx, cy, size, n = 4.2) {
  const a = size / 2;
  x.beginPath();
  const STEPS = 160;
  for (let i = 0; i <= STEPS; i++) {
    const th = (i / STEPS) * Math.PI * 2;
    const ct = Math.cos(th), st = Math.sin(th);
    const px = cx + a * Math.sign(ct) * Math.pow(Math.abs(ct), 2 / n);
    const py = cy + a * Math.sign(st) * Math.pow(Math.abs(st), 2 / n);
    i ? x.lineTo(px, py) : x.moveTo(px, py);
  }
  x.closePath();
}

// Reset state before every frame — the canvas inherits text direction from the page, which breaks alignment
export function resetFrame(ctx, W, H) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.globalAlpha = 1;
  ctx.filter = 'none';
  ctx.direction = 'ltr';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, W, H);
}
