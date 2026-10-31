#!/usr/bin/env python3
"""
refmeasure — measuring a source for replication: extracting assets with alpha, tracking, reveal and fitting.

Built during real replications and generalised here so it is never written a fourth time.
Works on a **frame sequence** extracted from the source, and assumes the background can be
reconstructed — either it is static (gradient/flat), or it can be estimated with a per-pixel median.

┌─ The rule ─────────────────────────────────────────────────────────────┐
│ MEASURE.md §10: a profile that mixes two effects invents a third.       │
│    `fit` derives scale FROM HEIGHT on purpose — height is immune to a   │
│    horizontal typewriter reveal. If the reveal is vertical, flip the axis first. │
│ MEASURE.md §11: `--box` must contain ONE element. Two elements in one box │
│    ⇒ every statistic measures both.                                     │
└─────────────────────────────────────────────────────────────────────────┘

    python3 refmeasure.py bg     --frames DIR --range 0,120 [--out bg.png]
    python3 refmeasure.py asset  --frames DIR --bg bg.png --settle 121 \
                                 --box 40,300,680,520 --name hey --out assets/
    python3 refmeasure.py track  --frames DIR --bg bg.png --range 0,30  --box ...
    python3 refmeasure.py reveal --frames DIR --bg bg.png --range 0,30  --settle 21 --box ...
    python3 refmeasure.py fit    --frames DIR --bg bg.png --range 0,30  --settle 21 --box ...
    python3 refmeasure.py --selftest
"""
import sys, os, json, glob, argparse
import numpy as np
from PIL import Image


# ── loading ──────────────────────────────────────────────────────────────

def load_frames(d):
    fr = sorted(glob.glob(os.path.join(d, '*.png')) + glob.glob(os.path.join(d, '*.jpg')))
    if not fr:
        raise SystemExit(f'no frames in {d}')
    return fr


def img(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.float32)


class Ref:
    """A frame sequence + background. `diff(i)` is the mean difference from the background."""

    def __init__(self, frames_dir, bg_path=None, bg_array=None):
        self.fr = load_frames(frames_dir) if frames_dir else None
        if bg_array is not None:
            self.bg = bg_array.astype(np.float32)
        elif bg_path:
            self.bg = img(bg_path)
        else:
            raise SystemExit('background missing — run `bg` first')
        self._cache = {}

    def frame(self, i):
        if i not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[i] = img(self.fr[i])
        return self._cache[i]

    def diff(self, i):
        return np.abs(self.frame(i) - self.bg).mean(2)

    def diff_max(self, i):
        return np.abs(self.frame(i) - self.bg).max(2)


# ── background ───────────────────────────────────────────────────────────

def estimate_bg(frames_dir, f0, f1, step=1):
    """Per-pixel median. Valid when every pixel sees background in most frames."""
    fr = load_frames(frames_dir)[f0:f1:step]
    stack = np.stack([img(p) for p in fr], 0)
    return np.median(stack, 0)


# ── extracting an asset with alpha ───────────────────────────────────────

def _softfill(col, m, sigma=4):
    """Fills the soft edge with the nearest core colour. scipy if available, otherwise a box blur."""
    try:
        from scipy import ndimage
        blur = lambda a: ndimage.gaussian_filter(a, sigma)
    except ImportError:
        k = int(sigma) * 2 + 1

        def blur(a):
            out = a.astype(np.float32)
            for ax in (0, 1):
                c = np.cumsum(np.pad(out, [(k, k) if i == ax else (0, 0)
                                           for i in range(2)], mode='edge'), axis=ax)
                sl_hi = [slice(None)] * 2
                sl_lo = [slice(None)] * 2
                sl_hi[ax] = slice(k, k + a.shape[ax])
                sl_lo[ax] = slice(0, a.shape[ax])
                out = (c[tuple(sl_hi)] - c[tuple(sl_lo)]) / k
            return out
    mf = m.astype(np.float32)
    den = blur(mf) + 1e-6
    for c in range(3):
        col[:, :, c] = np.where(m, col[:, :, c], blur(col[:, :, c] * mf) / den)
    return col


def extract(ref, settle, box, name, out_dir, thr_hi=0.72, thr_lo=0.10):
    """
    A PNG asset with alpha from the settle frame.
    MEASURE.md §14: `settle` must come before any transform that will be applied to the asset again.
    """
    x0, y0, x1, y1 = box
    a = ref.frame(settle)[y0:y1, x0:x1]
    bg = ref.bg[y0:y1, x0:x1]
    dm = np.abs(a - bg).max(2)
    if (dm > 20).sum() < 20:
        raise SystemExit(f'{name}: no ink in the box — check the box and settle')
    core = dm > np.percentile(dm[dm > 20], 70)
    refv = float(np.median(dm[core]))
    alpha = np.clip((dm / refv - thr_lo) / (thr_hi - thr_lo), 0, 1)

    m = alpha > 0.85
    col = np.where(m[:, :, None], a, 0).astype(np.float32)
    col = _softfill(col, m)
    rgba = np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{name}.png')
    Image.fromarray(rgba, 'RGBA').save(path)

    ys, xs = np.nonzero(alpha > 0.5)
    return dict(name=name, path=path, settle=settle, box=[x0, y0, x1, y1],
                ink=[int(x0 + xs.min()), int(y0 + ys.min()),
                     int(x0 + xs.max()), int(y0 + ys.max())],
                w=x1 - x0, h=y1 - y0, alpha_mean=round(float(alpha.mean()), 4))


# ── per-frame tracking ───────────────────────────────────────────────────

def track(ref, f0, f1, box, thr=25):
    x0, y0, x1, y1 = box
    rows = []
    for i in range(f0, f1):
        d = ref.diff(i)[y0:y1, x0:x1]
        m = d > thr
        r = dict(f=i)
        if m.sum() > 100:
            ys, xs = np.nonzero(m)
            r.update(x0=int(x0 + xs.min()), x1=int(x0 + xs.max()),
                     y0=int(y0 + ys.min()), y1=int(y0 + ys.max()),
                     n=int(m.sum()), amp=round(float(np.percentile(d[m], 90)), 1))
        rows.append(r)
    return rows


# ── per-column reveal ⇒ letter boundaries ────────────────────────────────

def reveal(ref, f0, f1, settle, box, thr=35, axis='x'):
    """
    The reveal time of every column. The jumps in time are the LETTER BOUNDARIES — this is what solved
    lettering that touches itself, where splitting by gaps failed.
    Split into lines BEFORE splitting into letters: words stacked above each other ⇒ columns mix.
    """
    x0, y0, x1, y1 = box
    fin = ref.diff(settle)[y0:y1, x0:x1]
    mask = fin > thr
    ax = 0 if axis == 'x' else 1
    colsum = (fin * mask).sum(ax)
    valid = mask.sum(ax) > 3
    n = colsum.shape[0]
    t = np.full(n, -1)
    for i in range(f0, f1):
        d = ref.diff(i)[y0:y1, x0:x1]
        frac = np.where(valid, (d * mask).sum(ax) / np.maximum(colsum, 1e-6), 0)
        t[valid & (t < 0) & (frac > 0.5)] = i
    xs = np.nonzero(t >= 0)[0]
    if not len(xs):
        return []
    bounds = [xs[0]]
    for k in range(1, len(xs)):
        if t[xs[k]] - t[xs[k - 1]] >= 2 or xs[k] - xs[k - 1] > 4:
            bounds.append(xs[k])
    base = x0 if axis == 'x' else y0
    letters = []
    for k, b in enumerate(bounds):
        e = bounds[k + 1] if k + 1 < len(bounds) else xs[-1] + 1
        seg = t[b:e]
        seg = seg[seg >= 0]
        if len(seg):
            letters.append(dict(a=int(base + b), b=int(base + e), t=int(np.median(seg))))
    return letters


# ── fitting scale/position/opacity ───────────────────────────────────────

def fit(ref, f0, f1, settle, box, thr=28, pad=260, scale_from='h'):
    """
    For each frame: s (scale relative to settle) · L,T · op.
    MEASURE.md §10 lives here: `scale_from='h'` because height is immune to a horizontal reveal.
       Vertical reveal ⇒ `scale_from='w'`. Both effects on the same axis ⇒ no measurement possible.
    """
    x0, y0, x1, y1 = box
    H, W = ref.bg.shape[:2]
    fin = ref.diff(settle)
    fm = fin > thr
    sub0 = fm[y0:y1, x0:x1]
    if sub0.sum() < 50:
        raise SystemExit('the settle frame is empty inside the box')
    ys, xs = np.nonzero(sub0)
    ref_size = (ys.max() - ys.min() + 1) if scale_from == 'h' else (xs.max() - xs.min() + 1)
    amp0 = float(np.percentile(fin[y0:y1, x0:x1][sub0], 90))

    oy, ox = max(0, y0 - pad), max(0, x0 - pad)
    ey, ex = min(H, y1 + pad), min(W, x1 + pad)
    out = []
    for i in range(f0, f1):
        d = ref.diff(i)
        sub = (d > thr)[oy:ey, ox:ex]
        if sub.sum() < 150:
            out.append(dict(f=i, op=0.0))
            continue
        yy, xx = np.nonzero(sub)
        size = (yy.max() - yy.min() + 1) if scale_from == 'h' else (xx.max() - xx.min() + 1)
        amp = float(np.percentile(d[oy:ey, ox:ex][sub], 90))
        out.append(dict(f=i, s=round(size / float(ref_size), 4),
                        L=int(ox + xx.min()), T=int(oy + yy.min()),
                        op=round(min(1.0, amp / amp0), 3)))
    return out


# ── selftest — "a gate without a selftest is not a gate" ─────────────────

def selftest():
    """
    Builds a synthetic sequence with known true values and checks that every measurement recovers them.
    Every check also runs with the original bug injected, and must fail.
    """
    import tempfile
    W, H, N = 320, 200, 24
    yy, xx = np.mgrid[0:H, 0:W]
    bg = (120 + 40 * np.sin(xx / 47.0) + 30 * np.cos(yy / 31.0))
    bg = np.dstack([bg, bg * 0.9, bg * 1.05]).astype(np.float32)

    # truth: a bar revealed left→right, one letter every 2 frames, 6 letters
    LET, LW, GAP, X0, Y0, BH = 6, 30, 6, 40, 70, 40
    truth_t = {k: 2 * k for k in range(LET)}
    d = tempfile.mkdtemp(prefix='refmeasure_')
    for i in range(N):
        f = bg.copy()
        for k in range(LET):
            if i >= truth_t[k]:
                a = X0 + k * (LW + GAP)
                f[Y0:Y0 + BH, a:a + LW] = [250, 250, 250]
        Image.fromarray(f.astype(np.uint8)).save(os.path.join(d, f'{i:04d}.png'))

    ref = Ref(d, bg_array=bg)
    box = [X0 - 8, Y0 - 8, X0 + LET * (LW + GAP) + 8, Y0 + BH + 8]
    ok, fail = [], []

    # 1 · reveal returns 6 letters at the right times
    L = reveal(ref, 0, N, N - 1, box)
    got = [l['t'] for l in L]
    if len(L) == LET and got == [truth_t[k] for k in range(LET)]:
        ok.append(f'reveal · {LET} letters, times {got}')
    else:
        fail.append(f'reveal · got {len(L)} letters, times {got}')

    # 1b · inject the bug: a threshold that swallows the jumps ⇒ must stop returning 6
    Lb = reveal(ref, 0, N, N - 1, box, thr=250)
    if len(Lb) != LET:
        ok.append('reveal · threshold injection caught')
    else:
        fail.append('reveal · threshold injection NOT caught — the check immunises itself')

    # 2 · track catches the horizontal growth and the start moment
    T = track(ref, 0, N, box)
    w_first = T[0]['x1'] - T[0]['x0']
    w_last = T[-1]['x1'] - T[-1]['x0']
    if w_last > w_first * 4:
        ok.append(f'track · width {w_first}→{w_last}')
    else:
        fail.append(f'track · width did not grow as expected ({w_first}→{w_last})')

    # 3 · fit derives scale from height ⇒ constant 1.0 even though the width changes (MEASURE.md §10)
    F = fit(ref, 2, N, N - 1, box, pad=20, scale_from='h')
    s = [r['s'] for r in F if 's' in r]
    if s and max(abs(v - 1.0) for v in s) < 0.02:
        ok.append(f'fit · height is immune to a horizontal reveal (s∈[{min(s)},{max(s)}])')
    else:
        fail.append(f'fit · height moved when it should not have: {s[:6]}')

    # 3b · the same fit from width MUST show fake growth — that is exactly the trap
    Fw = fit(ref, 2, N, N - 1, box, pad=20, scale_from='w')
    sw = [r['s'] for r in Fw if 's' in r]
    if sw and (max(sw) - min(sw)) > 0.3:
        ok.append(f'fit · the non-immune axis does invent scale ({min(sw)}→{max(sw)})')
    else:
        fail.append('fit · the axis injection did not show the fake factor')

    # 4 · extract produces alpha that roughly covers the ink area
    meta = extract(ref, N - 1, box, 'selftest', d)
    exp = LET * LW * BH / float((box[2] - box[0]) * (box[3] - box[1]))
    if abs(meta['alpha_mean'] - exp) < 0.08:
        ok.append(f"extract · alpha {meta['alpha_mean']} ≈ expected {exp:.3f}")
    else:
        fail.append(f"extract · alpha {meta['alpha_mean']} vs expected {exp:.3f}")

    for line in ok:
        print(f'  \033[32m✓\033[0m {line}')
    for line in fail:
        print(f'  \033[31m✗\033[0m {line}')
    print(f"\n{'all passed' if not fail else f'{len(fail)} failed'}\n")
    return 0 if not fail else 1


# ── CLI ──────────────────────────────────────────────────────────────────

def _box(s):
    v = [int(x) for x in s.split(',')]
    if len(v) != 4:
        raise argparse.ArgumentTypeError('box = x0,y0,x1,y1')
    return v


def _rng(s):
    v = [int(x) for x in s.split(',')]
    return v[0], v[1]


def main():
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    p = argparse.ArgumentParser(description='Measure a source for replication')
    p.add_argument('cmd', choices=['bg', 'asset', 'track', 'reveal', 'fit'])
    p.add_argument('--frames', required=True)
    p.add_argument('--bg')
    p.add_argument('--range', type=_rng)
    p.add_argument('--settle', type=int)
    p.add_argument('--box', type=_box)
    p.add_argument('--name')
    p.add_argument('--out')
    p.add_argument('--thr', type=float)
    p.add_argument('--axis', default='x', choices=['x', 'y'])
    p.add_argument('--scale-from', default='h', choices=['h', 'w'])
    a = p.parse_args()

    if a.cmd == 'bg':
        f0, f1 = a.range or (0, len(load_frames(a.frames)))
        out = a.out or 'bg.png'
        Image.fromarray(estimate_bg(a.frames, f0, f1).astype(np.uint8)).save(out)
        print(json.dumps(dict(bg=out, frames=[f0, f1]), ensure_ascii=False))
        return

    ref = Ref(a.frames, bg_path=a.bg)
    kw = {} if a.thr is None else dict(thr=a.thr)

    if a.cmd == 'asset':
        r = extract(ref, a.settle, a.box, a.name, a.out or 'assets')
    elif a.cmd == 'track':
        r = track(ref, a.range[0], a.range[1], a.box, **kw)
    elif a.cmd == 'reveal':
        r = reveal(ref, a.range[0], a.range[1], a.settle, a.box, axis=a.axis, **kw)
    else:
        r = fit(ref, a.range[0], a.range[1], a.settle, a.box,
                scale_from=a.scale_from, **kw)

    s = json.dumps(r, ensure_ascii=False, indent=1)
    if a.out and a.cmd != 'asset':
        open(a.out, 'w').write(s)
        print(f'{a.out} · {len(r)} records')
    else:
        print(s)


if __name__ == '__main__':
    main()
