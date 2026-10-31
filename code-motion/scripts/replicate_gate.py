#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replicate_gate.py — the replication gate: compares a RENDERED OUTPUT against the SOURCE, frame by frame.

═══ What PASS says — and what it does not ═══
PASS = **no deviation of the six types checked here was found**. A necessary condition, not proof
of fidelity. All metrics are global per frame (or per region set with `--roi`): dominant background
colour, ink area, frame difference. They do NOT know whether the right object is
in the right place, whether the typography matches, or whether the content inside a screen is right.
⇒ After PASS you still must: `--roi` on the elements that matter in this replication, a side-by-side
   comparison, and watching it through at normal speed (SKILL.md → "delivery threshold").

═══ Why it exists ═══
In one real replication a sparse contact sheet said "9 beats ✅".
Watching all 707 frames revealed 25 gaps — including **5 whole scenes that were never built**.
A sheet sampled every 0.5s CANNOT show that a section is frozen.

═══ Usage ═══
    python3 replicate_gate.py REF.mp4 OURS.mp4 [--fps 30] [--ref-crop W:H:X:Y]
                              [--build-crop W:H:X:Y] [--roi NAME=x0,y0,x1,y1 ...] [--json out.json]
    python3 replicate_gate.py --selftest

`--roi` in fractions 0..1 of the frame (after crop), e.g. `--roi logo=0.3,0.4,0.7,0.6`.
Every region gets its own G1–G5, and each of them must pass.

═══ What it checks ═══
  G1 blank   blank frames — the same runs, at the same times; **missing or extra = FAIL**
  G2 bg      background-colour path (full RGB) frame by frame within ±0.1s: missing change · extra · colour · cut instead of fade
  G3 motion  ⭐ a section where the source moves and the output STANDS STILL
  G4 cuts    hard cuts — EVERY cut in the source is matched, and there are no extra cuts
  G5 ink     ink-area curve — maximum deviation, and correlation when the source has a curve
  G6 len     length

All windows and tolerances are defined IN SECONDS and converted to frames by `--fps`,
so their meaning does not change when you change the sampling rate.

⚠️ G3 catches FREEZING, not differences in strength. "Moves less than the source" is a WARN — because a gap
   in content (a rectangle instead of a video clip) lowers `diff` without any motion bug.
"""

import sys, os, json, shutil, subprocess, tempfile, argparse

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("numpy/Pillow missing:  pip3 install numpy pillow")

# ─── thresholds without time units ───
BLANK_INK     = 0.002   # ink area below which the frame counts as blank
INK_DELTA     = 40      # colour distance from the background above which a pixel counts as ink
INK_DELTA_HI  = 64      # stricter threshold — to confirm "missing/extra blank" (faint content at the border is not a contradiction)
CUT_DIFF      = 18.0    # mean frame difference above which it is a cut candidate (at 720×540)
INK_MAX_DEV   = 0.25    # maximum allowed deviation in the coverage curve
INK_CORR_MIN  = 0.75
INK_FLAT      = 0.02    # source-curve range below which there is "no curve" — correlation undefined
BG_TOL        = 12      # background change (any channel) above which a transition starts
BG_STABLE     = 3       # below this over a settle window = the background is at rest
BG_COLOR_TOL  = 24      # colour gap between source and our background that counts as "a different colour"
BG_RUN_S      = 0.067   # an unmatched run this long (2 frames at 30fps) = failure; a single frame = noise
BG_COCAND     = 0.6     # a colour covering ≥60% of the dominant area = an equal background candidate
# ─── confirmation at a second threshold (hysteresis) — "missing" only if the other side has not even a weak sign ───
CUT_SPREAD    = 2       # change energy within 2 frames = a cut; beyond that = a fade
FADE_RATIO    = 2.5     # two "different" fades = 2.5× in change spread
BLANK_CONFIRM = 3.0     # a blank is "missing" only if the other side did not drop below 3×BLANK_INK
CUT_CONFIRM   = 0.5     # a cut is "missing" only if the other side has no jump of half its size

# ─── thresholds in seconds — converted to frames by fps ───
MOVE_WIN_S   = 0.5      # motion window
TOL_S        = 0.10     # time tolerance for an event (3 frames at 30fps)
CUT_NEIGH_S  = 0.20     # neighbourhood against which a "sharp jump" is measured
SETTLE_S     = 0.10     # how long the background must rest for the transition to count as finished
LEN_TOL_S    = 0.10

# An absolute threshold on `diff` is a bug. `diff` depends on resolution and object size —
#   so "the source moves" is measured RELATIVE TO THE SOURCE'S OWN DYNAMIC RANGE.
MOVE_REF_FRAC = 0.25
MOVE_REF_MIN  = 1.0
MOVE_FAIL_R   = 0.15
MOVE_WARN_R   = 0.40


def fr(sec, fps, lo=1):
    return max(lo, int(round(sec * fps)))


# ─────────────────────────── measurement ───────────────────────────

def frame_stats(a):
    """Background colour = the median of ALL THREE CHANNELS of the pixels in the dominant colour bin.
    An earlier version kept only the red channel — a background that changed only in blue passed.
    `cands` = every colour covering ≥BG_COCAND of the dominant area (up to 3).
    A positive control (source vs. its own re-encode) failed 4/4: two colours tied
       (15.7% vs 15.2%) or a gradient split across bins — the encode flips "the winner",
       and every flip was counted as a background transition. A flip between candidates is NOT a change."""
    h, w, _ = a.shape
    q = (a >> 4).astype(np.int32)
    key = q[:, :, 0] * 256 + q[:, :, 1] * 16 + q[:, :, 2]
    vals, counts = np.unique(key, return_counts=True)
    order = np.argsort(-counts)[:3]
    top = counts[order[0]]
    cands = [[int(round(v)) for v in np.median(a[key == vals[i]].reshape(-1, 3), axis=0)]
             for i in order if counts[i] >= BG_COCAND * top]
    bg = np.array(cands[0])
    dist = np.abs(a.astype(np.int32) - bg).max(axis=2)
    return {'bg': cands[0], 'cands': cands,
            'ink': float((dist > INK_DELTA).sum()) / (w * h),
            'ink_hi': float((dist > INK_DELTA_HI).sum()) / (w * h)}


def roi_slice(a, box):
    h, w, _ = a.shape
    x0, y0, x1, y1 = box
    return a[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h)),
             int(x0 * w):max(int(x0 * w) + 1, int(x1 * w))]


def measure_frames(frames, rois=None):
    """frames = an iterator of RGB arrays.
    Without rois → a list of rows (one per frame). With rois → {'full': rows, name: rows}."""
    names = ['full'] + list((rois or {}).keys())
    out = {n: [] for n in names}
    prev = {}
    for a in frames:
        for n in names:
            sub = a if n == 'full' else roi_slice(a, rois[n])
            s = frame_stats(sub)
            g = sub.astype(np.int32).mean(axis=2)
            s['diff'] = 0.0 if n not in prev else float(np.abs(g - prev[n]).mean())
            prev[n] = g
            out[n].append(s)
    return out if rois else out['full']


def measure_video(path, fps=30.0, w=720, h=540, crop=None, rois=None):
    if not shutil.which('ffmpeg'):
        sys.exit("ffmpeg missing")
    d = tempfile.mkdtemp(prefix='repgate_')
    try:
        vf = (f'crop={crop},' if crop else '') + f'fps={fps},scale={w}:{h}'
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf,
                            '-start_number', '0', os.path.join(d, '%05d.png')],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ffmpeg failed on {path}:\n{r.stderr[:400]}")
        names = sorted(os.listdir(d))
        if not names:
            sys.exit(f"no frames extracted from {path}")
        return measure_frames((np.asarray(Image.open(os.path.join(d, n)).convert('RGB'))
                               for n in names), rois)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ─────────────────────────── comparison helpers ───────────────────────────

def cdist(c1, c2):
    return max(abs(int(x) - int(y)) for x, y in zip(c1, c2))


def near_bg(row, color, tol):
    """Is `color` one of the frame's background candidates (within tol)."""
    return any(cdist(c, color) <= tol for c in row.get('cands', [row['bg']]))


def same_bg(r1, r2, tol):
    return near_bg(r1, r2['bg'], tol) or near_bg(r2, r1['bg'], tol)


def runs(idxs):
    out = []
    for i in idxs:
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def blanks(rows):
    return runs([i for i, r in enumerate(rows) if r['ink'] < BLANK_INK])


def bg_edges(rows, fps):
    """A background transition = from the moment the background moves more than BG_TOL from the previous plateau, until it rests again
    for SETTLE_S. Returns (start, end, from_rgb, to_rgb).
    The length is the evidence: a 5-frame fade and a cut are the same transition in a point metric."""
    settle = fr(SETTLE_S, fps, lo=2)
    n = len(rows)
    ed = []
    if not n:
        return ed
    # The plateau = a SET of anchored background colours. A transition starts only when no colour is shared.
    # Positive control: a secondary colour leaving the candidate set (the dominant did not move) was counted as a transition,
    #    at 280 in the source and 275 in the re-encode ⇒ fake missing+extra.
    # An anchored colour is not updated while it is within BG_TOL ⇒ a slow fade still adds up to a transition.
    plateau, i = [c for c in rows[0].get('cands', [rows[0]['bg']])], 1
    while i < n:
        cs = rows[i].get('cands', [rows[i]['bg']])
        shared = [p for p in plateau if any(cdist(p, c) <= BG_TOL for c in cs)]
        if shared:
            plateau = shared + [c for c in cs if not any(cdist(p, c) <= BG_TOL for p in plateau)]
            i += 1
            continue
        s, j = i - 1, i
        while j < n:
            win = rows[j:j + settle]
            if len(win) < settle:
                j = n - 1
                break
            if all(near_bg(x, rows[j]['bg'], BG_STABLE) for x in win):
                break
            j += 1
        j = min(j, n - 1)
        ed.append((s, j, rows[s]['bg'], rows[j]['bg']))
        plateau, i = list(rows[j].get('cands', [rows[j]['bg']])), j + 1
    return ed


def cuts(rows, fps):
    """A cut = a SHARP JUMP RELATIVE TO ITS NEIGHBOURHOOD, not a high absolute value.
    An absolute threshold alone counted 90 "cuts" in a source that has only ~8."""
    k = fr(CUT_NEIGH_S, fps, lo=2)
    d = [r['diff'] for r in rows]
    out = []
    for i in range(1, len(d)):
        lo, hi = max(0, i - k), min(len(d), i + k + 1)
        nb = sorted(d[j] for j in range(lo, hi) if j != i)
        med = nb[len(nb) // 2] if nb else 0.0
        if d[i] > CUT_DIFF and d[i] > max(3.0 * med, 2.0):
            out.append(i)
    return [a for a, _ in runs(out)]


def spread(rows, a, b):
    """How many frames hold the change energy (80%) in the window, above the window's baseline.
    A cut ≈ 1 · a 5-frame fade ≈ 4–5."""
    d = np.array([r['diff'] for r in rows[a:b]])
    if len(d) == 0:
        return 0
    d = np.clip(d - np.median(d), 0, None)
    tot = d.sum()
    if tot <= 1e-9:
        return 0
    c = np.cumsum(np.sort(d)[::-1])
    return int(np.searchsorted(c, 0.8 * tot) + 1)


def dips(rows, run, tol):
    """Hysteresis confirmation for a blank: the other side is ALMOST blank in the same window ⇒ not "missing"."""
    a, b = max(0, run[0] - tol), min(len(rows), run[1] + tol + 1)
    return a < b and min(r.get('ink_hi', r['ink']) for r in rows[a:b]) < BLANK_INK * BLANK_CONFIRM


def jumps(rows, c, size, tol):
    """Hysteresis confirmation for a cut: the other side has a jump of at least CUT_CONFIRM of its size."""
    a, b = max(1, c - tol), min(len(rows), c + tol + 1)
    return a < b and max(r['diff'] for r in rows[a:b]) >= CUT_CONFIRM * size


def win_mean(rows, a, b):
    seg = [r['diff'] for r in rows[a:b]]
    return sum(seg) / len(seg) if seg else 0.0


def pair(A, B, tol, key=lambda x: x):
    """One-to-one matching within a tolerance. Returns (pairs, missing-from-A, extra-in-B)."""
    used, pairs, miss = set(), [], []
    for a in A:
        best = None
        for j, b in enumerate(B):
            if j in used:
                continue
            dd = abs(key(a) - key(b))
            if dd <= tol and (best is None or dd < best[0]):
                best = (dd, j)
        if best is None:
            miss.append(a)
        else:
            used.add(best[1]); pairs.append((a, B[best[1]]))
    extra = [b for j, b in enumerate(B) if j not in used]
    return pairs, miss, extra


# ─────────────────────────── the gates ───────────────────────────

def compare(ref, our, fps=30.0, with_len=True):
    g = []
    t = lambda f: round(f / fps, 2)
    tol = fr(TOL_S, fps)
    n = min(len(ref), len(our))

    # G6 · length
    if with_len:
        dn = abs(len(ref) - len(our))
        g.append(dict(id='G6', name='length', ok=dn <= fr(LEN_TOL_S, fps),
                      detail=f'source {len(ref)} · ours {len(our)} · difference {dn} fr'))

    # G1 · blank frames — missing OR EXTRA = failure
    br, bo = blanks(ref), blanks(our)
    miss = [r for r in br if not any(o[0] - tol <= r[1] and r[0] <= o[1] + tol for o in bo)
            and not dips(our, r, tol)]
    extra = [o for o in bo if not any(r[0] - tol <= o[1] and o[0] <= r[1] + tol for r in br)
             and not dips(ref, o, tol)]
    g.append(dict(id='G1', name='blank frames', ok=(not miss and not extra),
                  detail=f'source {len(br)} · ours {len(bo)}' +
                         (f' · missing: {", ".join(f"{t(a)}–{t(b)}" for a, b in miss)}' if miss else '') +
                         (f' · extra: {", ".join(f"{t(a)}–{t(b)}" for a, b in extra)}' if extra else '')))

    # G2 · background — the PATH of the background colour, frame by frame, within a time tolerance.
    # An earlier version matched "transitions" as discrete events. A positive control (source vs.
    #    its own re-encode) failed 4/4: in a slow fade, a multi-colour background and a one-frame
    #    flash, the same content produces "transitions" at different points. A discrete event is not
    #    well defined here — the path is. Every background frame on one side must appear as a candidate
    #    on the other side within ±TOL_S. A missing/extra transition, a wrong target colour and a cut-instead-of-fade
    #    all show up as a run of unmatched frames.
    def unmatched(A, B):
        return [i for i in range(n)
                if not any(same_bg(A[i], B[j], BG_COLOR_TOL)
                           for j in range(max(0, i - tol), min(n, i + tol + 1)))]
    bad = sorted(set(unmatched(ref, our)) | set(unmatched(our, ref)))
    minrun = fr(BG_RUN_S, fps, lo=2)
    bad_runs = [r for r in runs(bad) if r[1] - r[0] + 1 >= minrun]

    def changed(rows, a, b):
        return not same_bg(rows[max(0, a - tol)], rows[min(n - 1, b + tol)], BG_TOL)

    def label(a, b):
        cr, co = changed(ref, a, b), changed(our, a, b)
        if cr and not co:
            kind = 'missing background change'
        elif co and not cr:
            kind = 'extra background change'
        elif cr and co:
            lo, hi = max(1, a - tol), min(n, b + tol + 1)
            kr, ko = spread(ref, lo, hi), spread(our, lo, hi)
            k = lambda v: 'cut' if v <= CUT_SPREAD else f'fade ~{v}fr'
            if (kr <= CUT_SPREAD) != (ko <= CUT_SPREAD) or (
                    min(kr, ko) > 0 and max(kr, ko) > FADE_RATIO * min(kr, ko)):
                kind = f'fade length / cut instead of fade (source {k(kr)} · ours {k(ko)})'
            else:
                kind = 'transition to a different colour'
        else:
            kind = 'different background colour'
        m = (a + b) // 2
        return (f'{t(a)}–{t(b)} {kind}: source {tuple(ref[m]["bg"])} · ours {tuple(our[m]["bg"])}')
    er, eo = bg_edges(ref, fps), bg_edges(our, fps)
    g.append(dict(id='G2', name='background', ok=not bad_runs,
                  detail=f'transitions (info): source {len(er)} · ours {len(eo)} · ' +
                         (f'{len(bad)} unmatched frames · ' + ' · '.join(label(a, b) for a, b in bad_runs[:6]) +
                          (f' · and {len(bad_runs) - 6} more' if len(bad_runs) > 6 else '')
                          if bad_runs else 'the path matches' +
                          (f' ({len(bad)} single frames within the noise)' if bad else ''))))

    # G3 ⭐ · freeze — the output stands still where the source moves
    win = fr(MOVE_WIN_S, fps, lo=2)
    starts = list(range(0, max(1, n - win + 1), max(1, win // 3)))
    wins = [(s, win_mean(ref, s, s + win), win_mean(our, s, s + win)) for s in starts]
    peak = max((mr for _, mr, _ in wins), default=0.0)
    active = max(MOVE_REF_MIN, MOVE_REF_FRAC * peak)
    frozen = [(s, mr, mo) for s, mr, mo in wins if mr >= active and mo < MOVE_FAIL_R * mr]
    weak = [(s, mr, mo) for s, mr, mo in wins
            if mr >= active and MOVE_FAIL_R * mr <= mo < MOVE_WARN_R * mr]
    fz = []
    for s, mr, mo in frozen:
        if fz and s - fz[-1][1] <= win:
            fz[-1][1] = s
            fz[-1][2] = max(fz[-1][2], mr)
        else:
            fz.append([s, s, mr, mo])
    g.append(dict(id='G3', name='freeze ⭐', ok=(not fz), warn=bool(weak),
                  detail=(f'activity threshold {active:.1f} (source peak {peak:.1f}) · ' +
                          ('no freeze' if not fz else
                           ' · '.join(f'{t(a)}–{t(b + win)}: source {mr:.1f} → ours {mo:.1f}'
                                      for a, b, mr, mo in fz)) +
                          (f' · [WARN] {len(weak)} windows moving weakly' if weak else ''))))

    # G4 · cuts — every cut in the source, and no extra cut
    cr, co = cuts(ref, fps), cuts(our, fps)
    _, miss4, extra4 = pair(cr, co, tol)
    miss4 = [c for c in miss4 if not jumps(our, c, ref[c]['diff'], tol)]
    extra4 = [c for c in extra4 if not jumps(ref, c, our[c]['diff'], tol)]
    g.append(dict(id='G4', name='cuts', ok=(not miss4 and not extra4),
                  detail=f'source {len(cr)} · ours {len(co)}' +
                         (f' · missing at {", ".join(str(t(c)) for c in miss4)}' if miss4 else '') +
                         (f' · extra at {", ".join(str(t(c)) for c in extra4)}' if extra4 else '')))

    # G5 · ink-area curve
    a = np.array([r['ink'] for r in ref[:n]])
    b = np.array([r['ink'] for r in our[:n]])
    mx = float(np.abs(a - b).max()) if n else 1.0
    worst = int(np.argmax(np.abs(a - b))) if n else 0
    flat = n < 3 or float(a.max() - a.min()) < INK_FLAT
    # Correlation is undefined when the source curve is flat. An earlier version set it to 0 ⇒
    #    a static video against ITSELF failed. When there is no curve — measure deviation only.
    if flat:
        corr, corr_ok = None, True
    else:
        corr = float(np.corrcoef(a, b)[0, 1]) if b.std() > 0 else 0.0
        corr_ok = corr >= INK_CORR_MIN
    # Both conditions are needed: correlation alone also passes when one curve STOPS HALFWAY.
    g.append(dict(id='G5', name='coverage curve', ok=(corr_ok and mx <= INK_MAX_DEV),
                  detail=(f'correlation {corr:.3f}' if corr is not None else 'flat source — correlation not relevant') +
                         f' · max deviation {mx:.3f} at {t(worst)}'
                         f' (source {a[worst]:.3f} · ours {b[worst]:.3f})' if n else ''))
    return g


def compare_all(ref, our, fps=30.0):
    """ref/our = rows or {'full': rows, roi: rows}. Regions get their own G1–G5."""
    if isinstance(ref, list):
        return compare(ref, our, fps)
    gates = compare(ref['full'], our['full'], fps)
    for name in ref:
        if name == 'full':
            continue
        for x in compare(ref[name], our[name], fps, with_len=False):
            x['id'] = f"{x['id']}@{name}"
            gates.append(x)
    return gates


def report(gates, title='replication gate'):
    print(f'\n╔═══ {title} ═══')
    npass = 0
    for g in gates:
        if g['ok']:
            tag, npass = ('⚠️ WARN' if g.get('warn') else '✅ PASS'), npass + 1
        else:
            tag = '❌ FAIL'
        print(f"║ {tag}  {g['id']} · {g['name']}")
        print(f"║        {g['detail']}")
    print(f'╚═══ {npass}/{len(gates)} passed')
    print('   PASS = no deviation of the checked types was found. It is NOT a fidelity sign-off:\n'
          '   object position, typography and content-inside-screens were not checked. → --roi, side-by-side, watch it through.')
    return all(g['ok'] for g in gates)


# ─────────────────────────── selftest ───────────────────────────
# "A gate without a selftest is decoration." For every failure case: a POSITIVE CONTROL that must
#     pass, and a check that the REASON for rejection is the right one (not an accidental failure on another gate).

def _f(color, boxes=()):
    a = np.full((120, 160, 3), color, dtype=np.uint8)
    for x, y, w, h, c in boxes:
        a[y:y+h, x:x+w] = c
    return a

def _seq_moving(n=90, step=3):
    return [_f(250, [(6 + int(i * step) % 120, 40, 30, 30, 20)]) for i in range(n)]

def _seq_grow(n=60, cap=1.0):
    out = []
    for i in range(n):
        h = int(120 * min(cap, i / (n - 1)))
        out.append(_f(250, [(0, 0, 160, h, 20)] if h > 0 else []))
    return out

def _seq_static(n=90):
    return [_f(250, [(60, 40, 30, 30, 20)]) for _ in range(n)]

def _seq_fade(n=30):
    out = []
    for i in range(n):
        v = 250 if i < 12 else (10 if i > 17 else int(250 - (i - 12) * 48))
        out.append(_f(v, [(60, 40, 30, 30, 250 - v)]))
    return out

def _seq_cut(n=30, at=15):
    out = []
    for i in range(n):
        v = 250 if i < at else 10
        out.append(_f(v, [(60, 40, 30, 30, 250 - v)]))
    return out

def _seq_twocuts(n=60):
    """Two hard cuts: 20 and 40."""
    return [_f(250 if i < 20 or i >= 40 else 10,
               [(60, 40, 30, 30, 10 if i < 20 or i >= 40 else 250)]) for i in range(n)]

def _seq_fivecuts(drop=None, n=60):
    """Five cuts (10·20·30·40·50) between three alternating tones.
    drop=30 ⇒ the 30–40 segment keeps the tone of 20–30: one cut disappears, the rest remain.
    This is the case "70% is enough" let through: 4/5 = 80%."""
    tones = [250, 130, 10]
    out = []
    for i in range(n):
        seg = i // 10
        if drop is not None and seg == drop // 10:
            seg -= 1
        v = tones[seg % 3]
        out.append(_f(v, [(60, 40, 30, 30, 250 - v)]))
    return out

def _seq_blank(n=40, rng=(10, 15)):
    return [_f(250) if rng[0] <= i <= rng[1] else _f(250, [(60, 40, 30, 30, 20)])
            for i in range(n)]

def _seq_noblank(n=40):
    return [_f(250, [(60, 40, 30, 30, 20)]) for _ in range(n)]

def _seq_blue(n=30, at=15):
    """A white background that changes ONLY in the blue channel."""
    out = []
    for i in range(n):
        a = _f(250, [(60, 40, 30, 30, 20)])
        if i >= at:
            a[:, :, 2] = np.where(a[:, :, 2] == 250, 120, a[:, :, 2])
        out.append(a)
    return out

def _seq_tie(n=60, flip=False):
    """Two background colours tied (half-half ±1 column). flip ⇒ "the winner" alternates every frame —
    which is what re-encoding does to such a background. It is THE SAME FILM."""
    out = []
    for i in range(n):
        a = _f(240)
        split = 80 + ((1 if i % 2 else -1) if flip else 1)
        a[:, split:] = (200, 210, 230)
        a[40:70, 65:95] = 20      # on the dividing line — subtracts equally from both sides
        out.append(a)
    return out

def _seq_two_boxes(n=90, second_moves=True):
    """Box A always moves (top-left); box B (bottom-right) moves only in the source."""
    out = []
    for i in range(n):
        ax = 4 + (i * 2) % 40
        by = 70 + ((i * 2) % 30 if second_moves else 0)
        out.append(_f(250, [(ax, 10, 20, 20, 20), (110, by, 20, 20, 20)]))
    return out


def selftest():
    print('═══ selftest — every failure case must fail FOR THE RIGHT REASON, and every control must pass ═══')
    cases = []
    mf = measure_frames

    def gate(gs, gid):
        return next(x for x in gs if x['id'] == gid)

    def expect_fail(name, gs, gid, why):
        x = gate(gs, gid)
        cases.append((name, (not x['ok']) and why in x['detail'], x['detail']))

    def expect_pass(name, gs, gid=None):
        xs = gs if gid is None else [gate(gs, gid)]
        cases.append((name, all(x['ok'] for x in xs),
                      ' · '.join(f"{x['id']}{'✓' if x['ok'] else '✗ ' + x['detail']}" for x in xs)))

    M, S = mf(_seq_moving()), mf(_seq_static())
    F, C = mf(_seq_fade()), mf(_seq_cut())
    B, N = mf(_seq_blank()), mf(_seq_noblank())

    expect_fail('1 · frozen output vs moving source → G3', compare(M, S), 'G3', 'source')
    expect_pass('2 · control: moving vs itself → everything passes', compare(M, M))
    expect_fail('3 · cut instead of fade → G2 (fade length)', compare(F, C), 'G2', 'fade length')
    expect_pass('4 · control: fade vs fade → everything passes', compare(F, F))
    expect_fail('5 · missing blank frame → G1 (missing)', compare(B, N), 'G1', 'missing')
    expect_fail('6 · extra blank frame → G1 (extra)', compare(N, B), 'G1', 'extra')
    expect_pass('7 · control: identical blanks → everything passes', compare(B, B))
    expect_fail('8 · different length → G6', compare(M, M[:40]), 'G6', 'difference')

    GF, GH = mf(_seq_grow(cap=1.0)), mf(_seq_grow(cap=0.6))
    expect_fail('9 · coverage that stops halfway → G5 (deviation)', compare(GF, GH), 'G5', 'max deviation')
    expect_pass('10 · control: same curve → everything passes', compare(GF, GF))

    # ─── cases found by an external review ───
    expect_pass('11 · static vs itself → everything passes (G5 used to fail on correlation=0)', compare(S, S))
    BL = mf(_seq_blue())
    expect_fail('12 · background that changed only in blue → G2 (missing transition)', compare(BL, mf(_seq_blue(at=999))), 'G2', 'missing background change')
    expect_fail('13 · extra background transition in the output → G2 (extra)', compare(mf(_seq_blue(at=999)), BL), 'G2', 'extra background change')
    expect_fail('14 · different background colour for the whole film → G2', compare(mf(_seq_blue(at=0)), S[:30]), 'G2', 'different background colour')
    T2, T1 = mf(_seq_twocuts()), mf([*_seq_twocuts()[:40], *[_seq_twocuts()[39]] * 20])
    expect_fail('15 · missing cut (1 of 5, 80% matched) → G4 (missing)',
                compare(mf(_seq_fivecuts()), mf(_seq_fivecuts(drop=30))), 'G4', 'missing')
    expect_fail('15b · missing cut (1 of 2) → G4 (missing)', compare(T2, T1), 'G4', 'missing')
    expect_fail('16 · extra cut → G4 (extra)', compare(T1, T2), 'G4', 'extra')
    expect_pass('17 · control: two cuts vs themselves → everything passes', compare(T2, T2))

    # ─── a positive control from real material: two background colours tied ───
    expect_pass('17b · control: a tied background whose "winner" alternates → everything passes',
                compare(mf(_seq_tie()), mf(_seq_tie(flip=True))))

    # ─── fps dependence: same seconds, 2× the frames ───
    M60 = mf(_seq_moving(180, step=1.5))
    S60 = mf(_seq_static(180))
    expect_fail('18 · frozen vs moving at 60fps → G3', compare(M60, S60, fps=60), 'G3', 'source')
    expect_pass('19 · control: moving vs itself at 60fps → everything passes', compare(M60, M60, fps=60))
    L = mf(_seq_moving(90))
    expect_fail('20 · 0.2s difference at 60fps → G6 (tolerance in seconds)',
                compare(mf(_seq_moving(180, 1.5)), mf(_seq_moving(168, 1.5)), fps=60), 'G6', 'difference')
    expect_pass('21 · control: 0.05s difference at 60fps → G6 passes',
                compare(mf(_seq_moving(180, 1.5)), mf(_seq_moving(177, 1.5)), fps=60), 'G6')

    # ─── regions: a freeze the global metric misses ───
    rois = {'b': (0.6, 0.5, 1.0, 1.0)}
    R1 = mf(_seq_two_boxes(second_moves=True), rois)
    R0 = mf(_seq_two_boxes(second_moves=False), rois)
    glob = compare(R1['full'], R0['full'])
    cases.append(('22 · (documentation) the global metric MISSES a box that froze while another moved',
                  gate(glob, 'G3')['ok'], gate(glob, 'G3')['detail']))
    expect_fail('23 · --roi on the box → G3@b fails', compare_all(R1, R0), 'G3@b', 'source')
    expect_pass('24 · control: --roi identical to itself → everything passes', compare_all(R1, R1))

    ok = True
    for name, passed, detail in cases:
        print(f"  {'✅' if passed else '❌'} {name}")
        if not passed:
            print(f'      ⟵ {detail}')
            ok = False
    print(f"\n{'✅ selftest passed' if ok else '❌ selftest failed'} — {sum(1 for _, p, _ in cases if p)}/{len(cases)}")
    return ok


# ─────────────────────────── main ───────────────────────────

def parse_roi(s):
    try:
        name, box = s.split('=', 1)
        x0, y0, x1, y1 = (float(v) for v in box.split(','))
    except ValueError:
        raise argparse.ArgumentTypeError(f'--roi must be NAME=x0,y0,x1,y1 (fractions 0..1): {s}')
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1) or not name:
        raise argparse.ArgumentTypeError(f'--roi outside 0..1 or empty: {s}')
    return name, (x0, y0, x1, y1)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    parser = argparse.ArgumentParser(description='Replication gate over every frame')
    parser.add_argument('ref')
    parser.add_argument('build')
    parser.add_argument('--fps', type=float, default=None, help='sampling rate; default = the source file own frame rate (no resampling)')
    parser.add_argument('--ref-crop', help='W:H:X:Y to crop the source before comparing')
    parser.add_argument('--build-crop', help='W:H:X:Y to crop the output before comparing')
    parser.add_argument('--roi', action='append', type=parse_roi, default=[],
                        help='NAME=x0,y0,x1,y1 in fractions — a region that gets its own G1–G5 (repeatable)')
    parser.add_argument('--json')
    a = parser.parse_args()
    if a.fps is not None and a.fps <= 0:
        parser.error('--fps must be positive')
    rois = dict(a.roi) or None
    if a.fps is None:                     # default: the source's own rate, so no frame is resampled
        r_ = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                             '-of', 'csv=p=0', a.ref], capture_output=True, text=True).stdout.strip()
        n_, d_ = (r_.split('/') + ['1'])[:2]
        a.fps = float(n_) / float(d_) if r_ else 30.0
        print(f'fps: {a.fps:g} (from the source)')
    print(f'measuring {a.ref} …'); ref = measure_video(a.ref, fps=a.fps, crop=a.ref_crop, rois=rois)
    print(f'measuring {a.build} …'); our = measure_video(a.build, fps=a.fps, crop=a.build_crop, rois=rois)
    gates = compare_all(ref, our, a.fps)
    passed = report(gates)
    if a.json:
        full_r = ref['full'] if rois else ref
        full_o = our['full'] if rois else our
        json.dump({'gates': gates, 'nref': len(full_r), 'nours': len(full_o),
                   'scope': 'PASS = no deviation of the checked kinds; not proof of fidelity'},
                  open(a.json, 'w'), ensure_ascii=False, indent=2)
        print(f'wrote {a.json}')
    sys.exit(0 if passed else 1)
