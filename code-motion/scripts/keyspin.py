#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Removes a green background from a frame sequence and turns the frames into silhouettes with alpha.
This is the pipeline's Keylight — twenty lines instead of an AE effect.

Usage:  keyspin.py <in_dir> <out_dir> [--soft 2.0] [--fill 20,20,24]
"""
import sys, os, glob
import numpy as np
from PIL import Image, ImageFilter

a = sys.argv[1:]
if len(a) < 2:
    sys.exit("usage: keyspin.py <in_dir> <out_dir> [--soft N] [--fill r,g,b]")
IN, OUT = a[0], a[1]
def flag(n, d):
    return a[a.index('--' + n) + 1] if '--' + n in a else d
SOFT = float(flag('soft', 1.6))
FILL = tuple(int(v) for v in flag('fill', '18,18,22').split(','))

os.makedirs(OUT, exist_ok=True)
files = sorted(glob.glob(os.path.join(IN, '*.png')))
if not files:
    sys.exit('no frames found')

for i, f in enumerate(files):
    im = np.array(Image.open(f).convert('RGB')).astype(float)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]

    # green = the green channel dominates the other two. Saturation adds confidence,
    # because a dark green shadow is still green, and we want to remove it too.
    mx = im.max(axis=2)
    mn = im.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    greenish = (g > r * 1.12) & (g > b * 1.12) & (sat > 0.18)

    alpha = np.where(greenish, 0.0, 255.0)

    # soft falloff at the edges — without it the silhouette is jagged
    am = Image.fromarray(alpha.astype(np.uint8), 'L')
    if SOFT > 0:
        am = am.filter(ImageFilter.GaussianBlur(SOFT))
    alpha = np.array(am).astype(float)

    # also erase what is almost transparent, or a greenish halo remains
    alpha = np.clip((alpha - 60) * (255 / 195), 0, 255)

    out = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    out[..., 0] = FILL[0]; out[..., 1] = FILL[1]; out[..., 2] = FILL[2]
    out[..., 3] = alpha.astype(np.uint8)
    Image.fromarray(out, 'RGBA').save(os.path.join(OUT, os.path.basename(f)))

    if i % 40 == 0:
        cov = (alpha > 127).mean()
        print(f'  {i:3d}/{len(files)}  subject coverage {cov*100:4.1f}%')

print(f'✓ {OUT}  ({len(files)} frames)')
