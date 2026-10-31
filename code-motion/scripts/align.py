#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
align.py — **is the gap a time shift or a wrong visual model?**

    python3 align.py REF.mp4 OURS.mp4 --ranges 0:62,63:100,101:187 [--max-shift 5]
                     [--ref-crop W:H:X:Y] [--width 320] [--json out.json]
    python3 align.py --selftest

For each frame range: compares `ours[f]` against `ref[f+k]` for every k within ±max-shift, and reports
the k that minimises the difference. This decides between hypotheses that look identical in `sbs`:

| finding | meaning |
|---|---|
| best k ≠ 0, and a clear improvement over k=0 | **time shift** — a cut point / offset of k frames |
| best k = 0, and the difference is still high | **the visual model is wrong** — not timing |
| the k curve is almost **flat** | the content is simply different — shifting does not help at any k |
| `--hold` finds a clear period and residue | **hold phase** (e.g. 25→30fps) — not a constant offset |

⛔ The tool does not decide that the replication is faithful. It separates failure types so we don't "fix" timing
   when the problem is in the drawing, or the other way round.
"""
import sys, os, json, shutil, subprocess, argparse

try:
    import numpy as np
except ImportError:
    sys.exit('numpy missing:  pip3 install numpy')


def sh(a, binary=False, check=True):
    r = subprocess.run(a, capture_output=True, text=not binary)
    if check and r.returncode != 0:
        err = r.stderr if not binary else r.stderr.decode('utf-8', 'replace')
        sys.exit(f'failed: {" ".join(a[:6])}…\n{err[:400]}')
    return r


def load(path, w, crop=None, fps=None):
    """Decodes the whole video to grey at width w — an array (N, h, w)."""
    meta = json.loads(sh(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', path]).stdout)
    v = meta['streams'][0]
    sw, sh_ = int(v['width']), int(v['height'])
    if crop:
        cw, ch, _, _ = (int(x) for x in crop.split(':'))
        sw, sh_ = cw, ch
    h = int(round(w * sh_ / sw / 2)) * 2
    vf = ([f'crop={crop}'] if crop else []) + ([f'fps={fps}'] if fps else []) + \
         [f'scale={w}:{h}', 'setsar=1', 'format=gray']
    raw = sh(['ffmpeg', '-v', 'error', '-i', path, '-vf', ','.join(vf),
              '-f', 'rawvideo', '-'], binary=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w).astype(np.int16)


def probe_range(R, O, lo, hi, max_shift):
    """Returns a dict with the difference for each k, the best k, and the per-frame argmin."""
    per_k, frames = {}, list(range(lo, hi + 1))
    for k in range(-max_shift, max_shift + 1):
        vals = []
        for f in frames:
            if 0 <= f < len(O) and 0 <= f + k < len(R):
                vals.append(float(np.abs(O[f] - R[f + k]).mean()))
        per_k[k] = float(np.mean(vals)) if vals else float('inf')
    best = min(per_k, key=per_k.get)
    argmins = []
    for f in frames:
        cand = {k: float(np.abs(O[f] - R[f + k]).mean())
                for k in range(-max_shift, max_shift + 1)
                if 0 <= f < len(O) and 0 <= f + k < len(R)}
        argmins.append(min(cand, key=cand.get) if cand else None)
    return {'lo': lo, 'hi': hi, 'per_k': per_k, 'best_k': best,
            'at_0': per_k.get(0, float('inf')), 'at_best': per_k[best], 'argmins': argmins}


def verdict(r, gain_pct=8.0, still_high=12.0, flat_pct=8.0):
    """The verdict relies on the k CURVE, not on the per-frame argmin.
    The first version classified "hold phase" by argmin spread — and that caught
       NEAR-STATIC content: a clean V curve with a sharp minimum at 0 (22.3 vs
       27.9 on both sides), i.e. well aligned, yet only 34% of the argmin at 0.
       Per-frame argmin is noisy; the mean curve is not."""
    a0, ab, k = r['at_0'], r['at_best'], r['best_k']
    vals = list(r['per_k'].values())
    span = (max(vals) - min(vals)) / a0 * 100 if a0 else 0.0
    gain = 100.0 * (a0 - ab) / a0 if a0 else 0.0
    if k != 0 and gain >= gain_pct:
        return f'time shift of {k:+d} frames (improvement {gain:.0f}% vs k=0)', gain
    # "flat" is checked AFTER "aligned": identical-to-itself has difference 0 at every k, and the curve
    #    is technically flat — but that is a perfect match, not different content.
    if a0 < still_high:
        w = 'k=0' if k == 0 else f'k={k:+d} with only {gain:.1f}% improvement'
        return f'aligned ({w}, difference {a0:.1f})', gain
    # Report where the minimum REALLY is, and why it is not evidence of a shift
    #    (an older wording said "k=0 is best" even when best_k was −4).
    where = ('the minimum is at k=0' if k == 0
             else f'the minimum is at k={k:+d}, but the improvement is only {gain:.1f}%, below the {gain_pct:g}% threshold — '
                  f'not proof of a constant shift')
    if span < flat_pct:
        return (f'**visual model** — the k curve is flat ({span:.1f}%): shifting does not help at any k. '
                f'{where}. difference {a0:.1f}'), gain
    return f'**visual model** — {where}. the difference stays at {a0:.1f}', gain


def hold_probe(R, O, lo, hi, periods=range(2, 9)):
    """Hold phase is MEASURED: for each frame, does `ref[f-1]` match better than `ref[f]`.
    If the "yes" answers concentrate on one residue modulo p — that is a hold phase, and the residue is the phase."""
    hits = []
    for f in range(max(lo, 1), hi + 1):
        if f >= len(O) or f >= len(R):
            break
        d0 = float(np.abs(O[f] - R[f]).mean())
        dm = float(np.abs(O[f] - R[f - 1]).mean())
        hits.append((f, dm < d0 - 0.15))
    if not hits:
        return None
    best = None
    for p in periods:
        by = {}
        for f, h in hits:
            by.setdefault(f % p, []).append(h)
        fr = {r_: sum(v) / len(v) for r_, v in by.items() if len(v) >= 3}
        if not fr:
            continue
        r_ = max(fr, key=fr.get)
        others = [v for kk, v in fr.items() if kk != r_]
        avg_o = sum(others) / len(others) if others else 0.0
        if fr[r_] >= 0.6 and fr[r_] >= 2 * max(avg_o, 0.05):
            score = fr[r_] - avg_o
            if best is None or score > best['score']:
                best = {'period': p, 'residue': r_, 'frac': fr[r_], 'others': avg_o, 'score': score}
    return best


def run(ref, ours, ranges, max_shift, width, ref_crop, ours_crop, fps=None):
    R = load(ref, width, ref_crop, fps)
    O = load(ours, width, ours_crop, fps)
    out = []
    for lo, hi in ranges:
        r = probe_range(R, O, lo, min(hi, len(O) - 1), max_shift)
        r['verdict'], r['gain'] = verdict(r)
        r['hold'] = hold_probe(R, O, lo, min(hi, len(O) - 1))
        out.append(r)
    return out, len(R), len(O)


def fmt(rows, nR, nO):
    L = [f'source {nR} frames · ours {nO}', '']
    L.append(f"{'range':>13} | {'k=0':>7} | {'best k':>7} | {'diff':>7} | verdict")
    L.append('-' * 92)
    for r in rows:
        L.append(f"{r['lo']:5d}-{r['hi']:<7d} | {r['at_0']:7.2f} | {r['best_k']:+7d} | "
                 f"{r['at_best']:7.2f} | {r['verdict']}")
        if r.get('hold'):
            h = r['hold']
            L.append(f"{'':13} | {'':7} | {'':7} | {'':7} | ↳ hold phase: period {h['period']} · "
                     f"residue {h['residue']} ({h['frac'] * 100:.0f}% vs {h['others'] * 100:.0f}% elsewhere)")
    L.append('')
    L.append('⚠️ "aligned" = no shift found and no high difference at this size — not "identical".')
    return '\n'.join(L)


def selftest():
    import tempfile
    print('═══ selftest — every hypothesis with a control ═══')
    d = tempfile.mkdtemp(prefix='align_')
    cases, ok = [], True
    V = 'testsrc2=size=320x180:rate=25'
    try:
        base = os.path.join(d, 'base.mp4')
        sh(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-t', '4', '-i', V,
            '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', base])
        R = load(base, 160)

        # 1 · identical → k=0, "aligned"
        r = probe_range(R, R, 10, 60, 4); v, _ = verdict(r)
        cases.append(('1 · control: identical to itself → k=0 and "aligned"', r['best_k'] == 0 and 'aligned' in v, f"k={r['best_k']} · {v}"))

        # 2 · a +2 shift → caught as a shift, exactly +2
        O = np.concatenate([R[2:], R[-1:], R[-1:]])
        r = probe_range(R, O, 10, 60, 4); v, _ = verdict(r)
        cases.append(('2 · +2 shift → "time shift" with k=+2', r['best_k'] == 2 and 'time shift' in v, f"k={r['best_k']} · {v}"))

        # 3 · visual model: same timing, very different brightness → k=0 and "visual model"
        O = np.clip(R.astype(int) * 0.55, 0, 255).astype(np.int16)
        r = probe_range(R, O, 10, 60, 4); v, _ = verdict(r)
        cases.append(('3 · brightness change without a shift → k=0 and "visual model"',
                      r['best_k'] == 0 and 'visual model' in v, f"k={r['best_k']} · {v}"))

        # 4 · negative control: light noise only → "aligned", not "visual model"
        rng = np.random.default_rng(3)
        O = np.clip(R + rng.integers(-2, 3, R.shape), 0, 255).astype(np.int16)
        r = probe_range(R, O, 10, 60, 4); v, _ = verdict(r)
        cases.append(('4 · control: light encoding noise → "aligned", not "visual model"',
                      r['best_k'] == 0 and 'aligned' in v, f"k={r['best_k']} · {v}"))

        # 5 · hold phase: every second frame is held → argmin alternates, k is small
        idx = [i - (i % 2) for i in range(len(R))]
        O = R[idx]
        r = probe_range(R, O, 10, 60, 4)
        h = hold_probe(R, O, 10, 60)
        cases.append(('5 · every second frame held → the hold probe finds period 2, residue 1',
                      h is not None and h['period'] == 2 and h['residue'] == 1 and abs(r['best_k']) <= 1,
                      f"k={r['best_k']} · hold={h}"))

        # 6 · negative control for the hold probe: no hold → no finding
        h = hold_probe(R, R, 10, 60)
        cases.append(('6 · control: no hold → the probe finds nothing', h is None, f'hold={h}'))

        # 7 · flat curve (entirely different content) → "visual model", not "shift"
        rng2 = np.random.default_rng(9)
        O = rng2.integers(0, 255, R.shape).astype(np.int16)
        r = probe_range(R, O, 10, 60, 4); v, _ = verdict(r)
        cases.append(('7 · entirely different content → "visual model" (flat curve), not a shift',
                      'visual model' in v and 'flat' in v, v))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    for n, p_, det in cases:
        print(f"  {'✅' if p_ else '❌'} {n}")
        if not p_:
            print(f'      ⟵ {det}'); ok = False
    print(f"\n{'✅ selftest passed' if ok else '❌ selftest failed'} — {sum(1 for _, p_, _ in cases if p_)}/{len(cases)}")
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    ap = argparse.ArgumentParser(description='Time shift or visual model?')
    ap.add_argument('ref'); ap.add_argument('ours')
    ap.add_argument('--ranges', required=True, help='lo:hi,lo:hi — in frames')
    ap.add_argument('--max-shift', type=int, default=5)
    ap.add_argument('--width', type=int, default=320)
    ap.add_argument('--ref-crop'); ap.add_argument('--ours-crop')
    ap.add_argument('--fps', type=float)
    ap.add_argument('--json')
    a = ap.parse_args()
    for t in ('ffmpeg', 'ffprobe'):
        if not shutil.which(t):
            sys.exit(f'{t} missing')
    rg = [tuple(int(x) for x in p.split(':')) for p in a.ranges.split(',')]
    rows, nR, nO = run(a.ref, a.ours, rg, a.max_shift, a.width, a.ref_crop, a.ours_crop, a.fps)
    print(fmt(rows, nR, nO))
    if a.json:
        json.dump({'ref': a.ref, 'ours': a.ours, 'rows': rows}, open(a.json, 'w'), ensure_ascii=False, indent=1)
        print(f'wrote {a.json}')
