#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reference vs. render, side by side — the check that caught every mistake.

Usage:  compare.py REF.mp4 MINE.mp4 [--ref-times 1,3,5] [--mine-times 1,3,5]
        [--crop W:H:X:Y] [--out compare.png]

Without --times it samples four evenly spaced points along each.
"""
import subprocess, sys, os, tempfile, atexit, shutil
from PIL import Image

a = sys.argv[1:]
if len(a) < 2:
    sys.exit("Usage: compare.py REF.mp4 MINE.mp4 [--ref-times ..] [--mine-times ..] [--crop ..] [--out ..]")
REF, MINE = a[0], a[1]
def flag(n, d=None):
    return a[a.index('--' + n) + 1] if '--' + n in a else d

def dur(v):
    r = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
                        '-of','csv=p=0', v], capture_output=True, text=True)
    return float(r.stdout.strip())

def times(spec, v):
    if spec: return [float(x) for x in spec.split(',')]
    d = dur(v)
    return [d * f for f in (0.15, 0.40, 0.65, 0.90)]

RT = times(flag('ref-times'), REF)
MT = times(flag('mine-times'), MINE)
CROP = flag('crop')
OUT = flag('out', 'compare.png')

tmp = tempfile.mkdtemp()
atexit.register(shutil.rmtree, tmp, ignore_errors=True)
# `-ss` exactly on a frame boundary sometimes returns the next frame. Every time that arrives here
#    is shifted to the middle of the frame, so sampling is stable. For numeric measurement — `perframe.py`,
#    which reads sequentially and never seeks.
# The fps is MEASURED per file, not assumed. A fixed `snap_mid(t, 30)` would shift
#    sampling in 24 · 25 · 60fps files — i.e. the "fix" would create exactly the bug
#    it came to close, just in a different source.
def fps_of(v):
    r = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
                        '-show_entries','stream=r_frame_rate','-of','csv=p=0', v],
                       capture_output=True, text=True)
    try:
        n, d = r.stdout.strip().split('/')
        f = float(n) / float(d)
        return f if f > 0 else 30.0
    except Exception:
        return 30.0

def snap_mid(t, fps):
    return (int(round(t * fps)) + 0.5) / fps

def grab(v, t, name, crop=None):
    t = snap_mid(t, fps_of(v))
    vf = 'scale=380:-2'
    if crop: vf = f'crop={crop},' + vf
    p = os.path.join(tmp, name)
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',v,
                    '-vf',vf,'-frames:v','1',p], check=True)
    return Image.open(p).convert('RGB')

top = [grab(REF, t, f'r{i}.png', CROP) for i, t in enumerate(RT)]
bot = [grab(MINE, t, f'm{i}.png') for i, t in enumerate(MT)]

th = max(i.height for i in top)
bh = max(i.height for i in bot)
cols = max(len(top), len(bot))
W = 380 * cols + 6 * (cols - 1)
sheet = Image.new('RGB', (W, th + bh + 10), (26, 26, 26))
for k, im in enumerate(top):
    sheet.paste(im, (k * 386 + (380 - im.width) // 2, 0))
for k, im in enumerate(bot):
    sheet.paste(im, (k * 386 + (380 - im.width) // 2, th + 10))
sheet.save(OUT)
print(f'✓ {OUT}   top: reference {[round(x,2) for x in RT]}   bottom: ours {[round(x,2) for x in MT]}')
