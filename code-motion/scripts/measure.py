#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reads a reference video and outputs a measured spec — everything done by hand, encoded.

Usage:
    python3 measure.py <video> [--crop W:H:X:Y] [--fps N] [--min-seg S] [--out spec]

By default it samples at the source rate (up to 30fps) and merges only segments shorter than 0.1s —
so a 0.23s shot stays a segment. `--fps 6` gives a **quick overview map only**:
at that rate segments shorter than ~0.33s cannot be separated, and the report marks this.

Outputs spec.json + spec.md:
  · split into segments (when what you see changes)
  · per segment: palette, brightness, saturation, motion energy
  · circle fit for a bright arc, if there is one — with a residual that says whether to trust it
"""
import subprocess, json, sys, os, math, tempfile, atexit, shutil
import numpy as np
from PIL import Image, ImageDraw

args = sys.argv[1:]
if not args:
    sys.exit("usage: measure.py <video> [--crop W:H:X:Y] [--fps N] [--min-seg S] [--out spec]")
VIDEO = args[0]
def flag(n, d=None):
    return args[args.index('--' + n) + 1] if '--' + n in args else d
CROP = flag('crop')
OUT = flag('out', 'spec')

probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height,r_frame_rate',
                        '-show_entries', 'format=duration', '-of', 'json', VIDEO],
                       capture_output=True, text=True)
if probe.returncode != 0:
    sys.exit(f'ffprobe failed on {VIDEO}:\n{probe.stderr[:400]}')
info = json.loads(probe.stdout)
src_w = info['streams'][0]['width']; src_h = info['streams'][0]['height']
num, den = info['streams'][0]['r_frame_rate'].split('/')
src_fps = float(num) / float(den)
duration = float(info['format']['duration'])

FPS = float(flag('fps', min(src_fps, 30.0)))
MIN_SEG = float(flag('min-seg', 0.1))   # seconds — not frames, so it does not change with --fps
if FPS <= 0 or MIN_SEG < 0:
    sys.exit('--fps must be positive and --min-seg non-negative')
COARSE = FPS < 24

# ── extract frames ────────────────────────────────────────────────────────
tmp = tempfile.mkdtemp(prefix='code-motion-measure-')
atexit.register(shutil.rmtree, tmp, ignore_errors=True)

vf = f"fps={FPS}"
if CROP:
    vf = f"crop={CROP}," + vf
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', VIDEO, '-vf', vf,
                os.path.join(tmp, '%04d.png')], check=True)
files = sorted(os.listdir(tmp))
if not files:
    sys.exit('no frames were extracted')

def frame(index):
    with Image.open(os.path.join(tmp, files[index])) as im:
        return np.asarray(im.convert('RGB'), dtype=float)

H, W, _ = frame(0).shape

def lum(a):  # 0..255
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]

def sat(a):
    mx = a.max(axis=2); mn = a.min(axis=2)
    return np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)

# ── split into segments: a jump in the difference between consecutive frames ──
diffs = [0.0]
previous = frame(0)
for i in range(1, len(files)):
    current = frame(i)
    diffs.append(float(np.abs(current - previous).mean()))
    previous = current
d = np.array(diffs)
thr = float(np.percentile(d, 78)) + d.std() * 0.55
cuts = [0] + [i for i in range(1, len(d)) if d[i] > thr and d[i] > 6.0] + [len(files)]
# merge segments shorter than MIN_SEG (default 0.1s).
# Previously a fixed 0.6s ⇒ shots of 0.23–0.27s were swallowed by the neighbouring segment.
min_frames = max(1, int(round(FPS * MIN_SEG)))
merged = [cuts[0]]
for c in cuts[1:]:
    if c - merged[-1] >= min_frames or c == len(files):
        merged.append(c)
cuts = merged

def palette(a, k=5, iters=12):
    """A short k-means on a pixel sample — the colours that really carry the frame."""
    px = a.reshape(-1, 3)
    px = px[lum(a).reshape(-1) > 18]          # ignore background black
    if len(px) < k:
        return []
    px = px[np.random.default_rng(7).choice(len(px), min(4000, len(px)), replace=False)]
    C = px[np.random.default_rng(11).choice(len(px), k, replace=False)].copy()
    for _ in range(iters):
        lab = np.argmin(((px[:, None, :] - C[None]) ** 2).sum(2), axis=1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = px[m].mean(0)
    lab = np.argmin(((px[:, None, :] - C[None]) ** 2).sum(2), axis=1)
    order = np.argsort(-np.bincount(lab, minlength=k))
    return [{'hex': '#%02x%02x%02x' % tuple(int(v) for v in C[j]),
             'share': round(float((lab == j).mean()), 3)} for j in order]

def fit_circle(a):
    """Fits a circle to the bright arc in the top half.
    Also returns a residual — if it is large, there is no arc there and the numbers must not be trusted."""
    L = lum(a)
    pts = []
    # not the brightest pixel in the row — a ridge: the maximum of local contrast.
    # the brightest pixel lands on text and soft blobs; only a thin line is a ridge.
    k = 9
    for y in range(1, int(H * 0.55)):
        row = L[y]
        smooth = np.convolve(row, np.ones(2 * k + 1) / (2 * k + 1), mode='same')
        ridge = row - smooth
        x = int(np.argmax(ridge))
        if ridge[x] > 12 and row[x] > 120 and 2 < x < W - 3:
            pts.append((x, y))
    if len(pts) < 25:
        return None
    P = np.array(pts, float)

    def fit(Q):
        A = np.c_[2 * Q[:, 0], 2 * Q[:, 1], np.ones(len(Q))]
        sol, *_ = np.linalg.lstsq(A, (Q ** 2).sum(1), rcond=None)
        cx, cy, c = sol
        return cx, cy, math.sqrt(max(0.0, c + cx * cx + cy * cy))

    # three rounds of outlier rejection: text, flashes and sparks land on the same row
    # and fake the fit. Cut everything far from the median and fit again.
    for _ in range(3):
        cx, cy, r = fit(P)
        e = np.abs(np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r)
        med = np.median(e)
        keep = e <= max(2.0, med * 2.2)
        if keep.sum() < 20 or keep.all():
            break
        P = P[keep]

    cx, cy, r = fit(P)
    resid = float(np.abs(np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r).mean())
    pts = P.tolist()
    return {'cx_frac': round(cx / W, 4), 'cy_frac': round(cy / H, 4),
            'r_over_w': round(r / W, 4), 'residual_px': round(resid, 2),
            'points': len(pts), 'tight': resid < max(3.0, r * 0.05),
            # A low residual means "a tight fit", not "a fit to the right thing".
            # Tested: the tool locks onto a soft slope or a local detail and gets a 0.7px residual
            # while missing the rim completely. So — checking by eye is mandatory.
            'verified': False}

segments = []
for i in range(len(cuts) - 1):
    a0, a1 = cuts[i], cuts[i + 1]
    mid = frame((a0 + a1) // 2)
    seg_motion = float(np.mean(d[a0 + 1:a1])) if a1 - a0 > 1 else 0.0
    segments.append({
        'index': i,
        'start_s': round(a0 / FPS, 2),
        'end_s': round(a1 / FPS, 2),
        'duration_s': round((a1 - a0) / FPS, 2),
        'mean_luminance': round(float(lum(mid).mean()), 1),
        'mean_saturation': round(float(sat(mid).mean()), 3),
        'motion_energy': round(seg_motion, 2),
        'palette': palette(mid),
        'circle': fit_circle(mid),
    })

spec = {
    'source': os.path.basename(VIDEO),
    'width': src_w, 'height': src_h, 'fps': round(src_fps, 3),
    'duration_s': round(duration, 3),
    'sampled_fps': FPS,
    'min_segment_s': MIN_SEG,
    'coarse': COARSE,   # True ⇒ overview map; not for cut timing
    'crop': CROP,
    'segment_count': len(segments),
    'segments': segments,
}
json.dump(spec, open(OUT + '.json', 'w'), ensure_ascii=False, indent=1)

# ── readable report ───────────────────────────────────────────────────────
L = []
L.append(f"# Measured spec — {spec['source']}\n")
L.append(f"{src_w}×{src_h} · {src_fps:.2f}fps · {duration:.2f}s · {len(segments)} segments"
         f" · sampled at {FPS:g}fps · minimum segment {MIN_SEG:g}s\n")
if COARSE:
    L.append(f"> ⚠️ **Overview map only.** At {FPS:g}fps segments shorter than {max(1 / FPS, MIN_SEG):.2f}s "
             "cannot be separated. For cut timing — run again without `--fps`.\n")
L.append('| # | from | to | length | brightness | saturation | motion | palette |')
L.append('|---|---|---|---|---|---|---|---|')
for s in segments:
    pal = ' '.join(p['hex'] for p in s['palette'][:4])
    L.append(f"| {s['index']} | {s['start_s']}s | {s['end_s']}s | {s['duration_s']}s | "
             f"{s['mean_luminance']} | {s['mean_saturation']} | {s['motion_energy']} | `{pal}` |")
fits = [s for s in segments if s['circle'] and s['circle']['tight']]
if fits:
    L.append('\n## Circle fits — **to verify by eye, not to use as they are**\n')
    L.append('A low residual = a tight fit, not a fit to the right thing. '
             'Tested: the tool gets a 0.7px residual on a detail that is not the rim. '
             'Check `<out>-fit-<i>.png` before taking a number from here.\n')
    L.append('| segment | centre | radius | residual | points | overlay |')
    L.append('|---|---|---|---|---|---|')
    for s in fits:
        c = s['circle']
        # overlay: the only way to know whether the fit caught the rim or something else
        ov = Image.fromarray(frame((cuts[s['index']] + cuts[s['index'] + 1]) // 2)
                             .astype('uint8')).convert('RGB').resize((W * 2, H * 2))
        dr = ImageDraw.Draw(ov)
        ccx, ccy, rr = c['cx_frac'] * W * 2, c['cy_frac'] * H * 2, c['r_over_w'] * W * 2
        dr.ellipse([ccx - rr, ccy - rr, ccx + rr, ccy + rr], outline=(255, 60, 60), width=3)
        png = f"{OUT}-fit-{s['index']}.png"
        ov.save(png)
        L.append(f"| {s['index']} | ({c['cx_frac']}W, {c['cy_frac']}H) | {c['r_over_w']}W "
                 f"| {c['residual_px']}px | {c['points']} | `{os.path.basename(png)}` |")
else:
    L.append('\n_No bright arc was found that a circle fit can be trusted on._')
open(OUT + '.md', 'w').write('\n'.join(L) + '\n')

print(f'✓ {OUT}.json · {OUT}.md   ({len(segments)} segments)')
