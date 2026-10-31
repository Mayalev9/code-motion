// Post-production pass on the finished frame: thresholded bloom, chromatic aberration and dither.
// Everything runs in WebGL; between stages we copy to an intermediate canvas because the context is shared.

import { glDraw } from './_gl.js';
import { BRIGHT, BLUR, CHROMA } from './_shaders.js';

const bufs = new Map();
function buf(key, w, h) {
  let c = bufs.get(key);
  if (!c) { c = new OffscreenCanvas(w, h); bufs.set(key, c); }
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return c;
}
function copy(src, key, w, h) {
  const c = buf(key, w, h);
  const x = c.getContext('2d');
  x.clearRect(0, 0, w, h);
  x.drawImage(src, 0, 0, w, h);
  return c;
}

/**
 * @param {number} bloom   bloom strength (0 = off)
 * @param {number} threshold  brightness threshold where the bloom starts
 * @param {number} radius  blur radius
 * @param {number} chroma  chromatic aberration strength (0 = off)
 */
export function applyPost(ctx, W, H, { bloom = 0.55, threshold = 0.62, radius = 2.4, chroma = 0.010 } = {}) {
  const src = ctx.canvas;

  if (bloom > 0) {
    const bw = Math.round(W / 4), bh = Math.round(H / 4);
    // downscale to a quarter — bloom does not need full resolution, which is what makes it cheap
    const small = copy(src, 'small', bw, bh);
    const bright = copy(glDraw(bw, bh, BRIGHT, { uTex: small, uThreshold: threshold }), 'bright', bw, bh);
    const hb = copy(glDraw(bw, bh, BLUR, { uTex: bright, uDir: [1, 0], uRadius: radius }), 'hb', bw, bh);
    const vb = copy(glDraw(bw, bh, BLUR, { uTex: hb, uDir: [0, 1], uRadius: radius }), 'vb', bw, bh);

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = bloom;
    ctx.filter = 'none';
    ctx.drawImage(vb, 0, 0, W, H);
    ctx.restore();
  }

  if (chroma > 0) {
    const full = copy(src, 'full', W, H);
    const out = copy(glDraw(W, H, CHROMA, { uTex: full, uAmount: chroma }), 'out', W, H);
    ctx.save();
    ctx.globalCompositeOperation = 'copy';
    ctx.globalAlpha = 1;
    ctx.filter = 'none';
    ctx.drawImage(out, 0, 0);
    ctx.restore();
  }
}
