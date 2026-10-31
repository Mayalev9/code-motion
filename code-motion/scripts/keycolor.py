#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Green-screen keying that keeps the original colour — unlike keyspin.py, which flattens to a silhouette.

This is the pipeline's full Keylight: mask + de-spill + crop to the bbox.
Without de-spill a greenish line stays on every edge, which is what gives away amateur keying.

Usage:  keycolor.py <in.jpg> <out.png> [--soft 2.4] [--pad 12] [--maxh 2200]
"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter

a = sys.argv[1:]
if len(a) < 2:
    sys.exit("usage: keycolor.py <in> <out> [--soft N] [--pad N] [--maxh N]")
SRC, DST = a[0], a[1]
def flag(n, d):
    return a[a.index('--' + n) + 1] if '--' + n in a else d
SOFT = float(flag('soft', 2.4))
PAD  = int(flag('pad', 12))
MAXH = int(flag('maxh', 2200))

im = np.array(Image.open(SRC).convert('RGB')).astype(np.float64)
r, g, b = im[..., 0], im[..., 1], im[..., 2]

# ── the mask ─────────────────────────────────────────────────────────────
# green = the green channel dominates the other two. Saturation adds confidence: a dark
# green shadow is still green, and we want to remove it too.
mx = im.max(axis=2); mn = im.min(axis=2)
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
greenish = (g > r * 1.15) & (g > b * 1.15) & (sat > 0.20)

# ── cleaning the mask ────────────────────────────────────────────────────
# Dark details inside the subject (e.g. seams) can reflect enough green to pass the saturation
# test, and the mask punches holes in them. A brightness guard does not help — they measured as bright as the background.
# Two topological operations fix it:
#   closing — closes a narrow green channel that enters from the silhouette edge (a seam touching
#             the edge). Real gaps (e.g. between a thumb and an object) are much wider
#             than CLOSE, so they survive.
#   filling — plugs a region that was peeled away and cannot be reached from the outer background.
from scipy.ndimage import binary_fill_holes, binary_closing
CLOSE = int(flag('close', 14))
subject = ~greenish
if CLOSE > 0:
    yy, xx = np.ogrid[-CLOSE:CLOSE + 1, -CLOSE:CLOSE + 1]
    disk = (xx ** 2 + yy ** 2) <= CLOSE ** 2
    subject = binary_closing(subject, structure=disk)
subject = binary_fill_holes(subject)
recovered = subject & greenish           # what was given back to the subject — pure green

alpha = np.where(subject, 255.0, 0.0)
am = Image.fromarray(alpha.astype(np.uint8), 'L')
if SOFT > 0:
    am = am.filter(ImageFilter.GaussianBlur(SOFT))
alpha = np.array(am).astype(np.float64)
# stretch the edge slope to erase greenish semi-transparency without biting into the subject
alpha = np.clip((alpha - 55) * (255 / 185), 0, 255)
holes = recovered

# ── de-spill ─────────────────────────────────────────────────────────────
# wherever green exceeds the red-blue average, pull it down to that average. This cleans
# the greenish glow that spills onto fingers and edges.
# Inside a plugged hole the removal is total — what was there is pure green, and without full removal
# a green spot would remain inside the seam instead of black.
avg = (r + b) / 2.0
g2 = np.where(g > avg, avg + (g - avg) * 0.15, g)
g2 = np.where(holes, avg, g2)

out = np.dstack([r, g2, b, alpha]).astype(np.uint8)

# ── crop to the real bbox ────────────────────────────────────────────────
# measure, don't guess. Threshold 40, not 0, to ignore single noise pixels.
solid = alpha > 40
ys, xs = np.where(solid)
if len(ys) == 0:
    sys.exit('error: the whole image was keyed out — the threshold is too aggressive')
y0, y1 = max(0, ys.min() - PAD), min(out.shape[0], ys.max() + PAD + 1)
x0, x1 = max(0, xs.min() - PAD), min(out.shape[1], xs.max() + PAD + 1)
out = out[y0:y1, x0:x1]

img = Image.fromarray(out, 'RGBA')
if img.height > MAXH:
    k = MAXH / img.height
    img = img.resize((max(2, round(img.width * k)), MAXH), Image.LANCZOS)
img.save(DST)

cov = solid.mean()
print(f'✓ {os.path.basename(DST)}  {img.width}×{img.height}  '
      f'bbox y{y0}..{y1} x{x0}..{x1}  subject coverage {cov*100:.1f}%')
