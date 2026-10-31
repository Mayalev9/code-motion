#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-frame difference between reference and replica — read as one continuous stream, with a full measurement signature.

Usage:
    perframe.py REF.mp4 OURS.mp4 [--width 1920] [--union mean|max]
                [--ranges "name:a-b,name:c-d"] [--ref-crop W:H:X:Y] [--ours-crop ...]
                [--allow-mismatch] [--frames] [--json out.json]
    perframe.py --selftest

Exit codes:  3 = hard failure (decode/argument) · 2 = mismatch (unless --allow-mismatch) · 0 = OK.

Three failures an earlier tool returned exit 0 on:
   · a 64×36 source vs a 64×64 replica — stretched into the same box, giving MAE 0.67.
   · 30fps vs 24fps with the same frame count — MAE 0.00, "perfect", while the motion differs.
   · `--union typo` — actually computed as mean, but written into the signature as typo.
   All three fail now, and each has a test case.

Why no `-ss`: `ffmpeg -ss` at a rounded time lands on the frame boundary and sometimes
   returns the NEXT frame. There is no seeking here at all.

⛔ MAE is a tool for FINDING, not a sign-off. A low number is not "checked".
⛔ A control showing other frames did not change proves no regression, not fidelity.
"""
import sys, os, json, tempfile, shutil, subprocess, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _compare_core import (probe, crop_dims, preflight, preflight_failed,      # noqa: E402
                           print_preflight, signature, print_signature,
                           Decoder, frames_of)

UNIONS = ('mean', 'max')


def measure(ref, ours, width=1920, union='mean', ref_crop=None, ours_crop=None,
            allow_mismatch=False, quiet=False):
    """Returns a dict with per_frame, checks, signature, hard, mismatch."""
    if union not in UNIONS:
        return {'hard': [f'invalid --union: {union!r} (allowed: {" · ".join(UNIONS)})'],
                'per_frame': [], 'checks': [], 'sig': None, 'mismatch': True}
    try:
        width = int(width)
    except Exception:
        return {'hard': [f'invalid --width: {width!r}'], 'per_frame': [], 'checks': [],
                'sig': None, 'mismatch': True}
    if width < 2:
        return {'hard': [f'--width must be ≥2: {width}'], 'per_frame': [], 'checks': [],
                'sig': None, 'mismatch': True}

    R, O = probe(ref), probe(ours)
    rdim = crop_dims(ref_crop, R['w'], R['h']) if ref_crop else (R['w'], R['h'])
    odim = crop_dims(ours_crop, O['w'], O['h']) if ours_crop else (O['w'], O['h'])
    checks = preflight(R, O, rdim, odim, check_counts=True)
    fails = preflight_failed(checks)

    # No stretching to another aspect ratio. If the aspect ratio fails — do not measure at all,
    #    because stretching into one box invents a match that does not exist.
    ar_fail = any(n == 'aspect ratio' for _, n, _ in fails)
    hard = []
    per = []
    sig = None
    if ar_fail:
        hard.append('different aspect ratio — measuring would invent a match; not measured')
    else:
        w = width
        h = int(round(width * rdim[1] / (rdim[0] * R['sar']) / 2)) * 2
        dr = Decoder(ref, w, h, ref_crop)
        do = Decoder(ours, w, h, ours_crop)
        n = w * h * 3
        extra_r = extra_o = 0
        while True:
            a, b = dr.read(), do.read()
            if a is None and b is None:
                break
            # ⛔ zip would drop a long tail SILENTLY. Here each side is counted.
            if a is None:
                extra_o += 1
                while do.read() is not None:
                    extra_o += 1
                break
            if b is None:
                extra_r += 1
                while dr.read() is not None:
                    extra_r += 1
                break
            A = np.frombuffer(a, np.uint8).reshape(h, w, 3).astype(np.int16)
            B = np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(np.int16)
            d = np.abs(A - B)
            per.append(float(d.max(axis=2).mean() if union == 'max' else d.mean()))
        rc_r, err_r = dr.close()
        rc_o, err_o = do.close()
        # ⛔ the decoder's exit code: a decode that failed midway is not "a short film".
        for nm, rc, err in (('source', rc_r, err_r), ('ours', rc_o, err_o)):
            if rc not in (0, None):
                hard.append(f'decoding {nm} failed (rc={rc}) {err.strip()[:160]}')
        # ⛔ fewer frames than the file declares = a PARTIAL stream, not a short film.
        nr0, no0 = frames_of(R), frames_of(O)
        if (nr0 and dr.count < nr0) or (no0 and do.count < no0):
            checks.append(('FAIL', 'decoded frames',
                           f'source {dr.count}/{nr0} · ours {do.count}/{no0} '
                           '⟵ the stream was cut — not a whole film measured'))
        if extra_r or extra_o:
            checks.append(('FAIL', 'extra frames',
                           f'source +{extra_r} · ours +{extra_o} ⟵ one side is longer; '
                           'the tail was NOT dropped silently'))
        nr, no = frames_of(R), frames_of(O)
        rng_txt = f'0–{len(per) - 1}' if per else '—'
        sig = signature('perframe.py', R, O, rdim, odim, (w, h), union, rng_txt,
                        (ref_crop, ours_crop), len(per), max(nr, no) or len(per))
    fails = preflight_failed(checks)
    mismatch = bool(fails)
    return {'per_frame': per, 'checks': checks, 'sig': sig, 'hard': hard,
            'mismatch': mismatch, 'R': R, 'O': O}


def parse_ranges(spec, n):
    """Returns (ranges, errors). An invalid range is an ERROR, not ignored."""
    out, errs = [], []
    for part in (spec or '').split(','):
        part = part.strip()
        if not part:
            continue
        if ':' not in part:
            errs.append(f'range without a name: {part!r} (form: name:a-b)'); continue
        name, rng = part.split(':', 1)
        if '-' not in rng:
            errs.append(f'range without a dash: {part!r}'); continue
        a, b = rng.split('-', 1)
        try:
            a, b = int(a), int(b)
        except ValueError:
            errs.append(f'non-numeric bounds: {part!r}'); continue
        if a > b:
            errs.append(f'reversed range: {part!r}'); continue
        if a < 0 or (n and b >= n):
            errs.append(f'range outside the film (0–{n - 1}): {part!r}'); continue
        out.append((name.strip(), a, b))
    return out, errs


def report(ref, ours, width, union, ranges, show_frames, json_out,
           ref_crop, ours_crop, allow_mismatch):
    r = measure(ref, ours, width, union, ref_crop, ours_crop)
    if r['hard']:
        for h in r['hard']:
            print(f'⛔ {h}')
        print_preflight(r['checks'])
        return 3
    per = r['per_frame']
    rows, errs = parse_ranges(ranges, len(per))
    if errs:
        for e in errs:
            print(f'⛔ {e}')
        return 3
    print_signature(r['sig'])
    print()
    print('preflight:')
    print_preflight(r['checks'])
    print()
    if not rows:
        rows = [('whole film', 0, len(per) - 1)]
    print(f'{"range":14s}| {"frames":11s} |  MAE  | worst       | state')
    for nm, a, b in rows:
        v = per[a:b + 1]
        k = int(np.argmax(v)) + a
        print(f'{nm:14s}| {f"{a}–{b}":11s} | {np.mean(v):5.2f} | f{k} = {max(v):5.1f} | ⚠️ not checked visually')
    if len(rows) > 1:
        print(f'{"whole film":14s}| {f"0–{len(per)-1}":11s} | {np.mean(per):5.2f} |')
    print()
    print('⛔ MAE is a finding tool. "Closed" requires: every sub-gap closed or declared,')
    print('   and the whole range checked visually. A "did not change" control = no regression, not fidelity.')
    if show_frames:
        print(' '.join(f'{i}:{v:.1f}' for i, v in enumerate(per)))
    if json_out:
        json.dump({'signature': r['sig'], 'per_frame': per,
                   'preflight': [{'status': s, 'name': n, 'detail': d} for s, n, d in r['checks']]},
                  open(json_out, 'w'), ensure_ascii=False, indent=1)
        print(f'✓ {json_out}')
    if r['mismatch'] and not allow_mismatch:
        print('\n⛔ preflight failed — the files are not comparable. '
              'Fix it, or allow explicitly with --allow-mismatch.')
        return 2
    return 0


# ── selftests ───────────────────────────────────────────────────────────────
def _mkvid(path, frames, fps=30, size=(64, 36)):
    d = tempfile.mkdtemp()
    try:
        from PIL import Image
        for i, c in enumerate(frames):
            (c if isinstance(c, Image.Image) else Image.new('RGB', size, c)).save(
                os.path.join(d, f'{i:04d}.png'))
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(fps),
                        '-i', os.path.join(d, '%04d.png'), '-c:v', 'libx264',
                        # `+faststart` moves the moov to the head of the file, so that a cut
                        #    in the middle leaves a file that PASSES probe and fails only in decoding —
                        #    exactly the case that must be caught.
                        '-qp', '0', '-pix_fmt', 'yuv444p',
                        '-movflags', '+faststart', path], check=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _junk_fails(good, junk):
    open(junk, 'wb').write(b'not a video at all' * 50)
    try:
        return bool(measure(good, junk, 64)['hard'])
    except SystemExit:
        return True


def selftest():
    from PIL import Image
    tmp = tempfile.mkdtemp()
    ok = fail = 0

    def chk(name, cond, detail=''):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
            print(f'  ❌ {name} — {detail}')
    try:
        N = 24
        ramp = [(i * 7 % 256,) * 3 for i in range(N)]
        P = lambda n: os.path.join(tmp, n)
        _mkvid(P('a.mp4'), ramp)
        _mkvid(P('b.mp4'), ramp)
        _mkvid(P('shift.mp4'), ramp[1:] + [ramp[-1]])
        _mkvid(P('sq.mp4'), ramp, size=(64, 64))                    # different aspect ratio
        _mkvid(P('f24.mp4'), ramp, fps=24)                          # different fps
        _mkvid(P('long.mp4'), ramp + ramp[:6])                      # one side longer
        _mkvid(P('col.mp4'), [(v[0], 0, 0) if i % 2 else (0, 0, v[0])
                              for i, v in enumerate(ramp)])
        _mkvid(P('grey2.mp4'), [(min(255, v[0] + 20),) * 3 for v in ramp])

        # 1 · positive control
        r = measure(P('a.mp4'), P('b.mp4'), 64)
        chk('1 identical to itself = 0 and exit 0', max(r['per_frame']) < 0.6 and not r['mismatch']
            and not r['hard'], f"max={max(r['per_frame']):.2f} mism={r['mismatch']}")

        # 2 · negative control
        r2 = measure(P('a.mp4'), P('shift.mp4'), 64)
        chk('2 frame offset ≠ 0', np.mean(r2['per_frame']) > 3)

        # 3 · sequential reading returns exactly frame k
        d = Decoder(P('a.mp4'), 64, 36)
        vals = []
        while True:
            b = d.read()
            if b is None: break
            vals.append(int(np.frombuffer(b, np.uint8)[0]))
        rc, _ = d.close()
        want = [v[0] for v in ramp]
        chk('3 sequential read = the right frame', vals == want and rc == 0,
            f'{vals[:6]}… rc={rc}')

        # 3b · a REAL fault injection: a mutant reader that skips the first frame —
        #      actually run, not just shifting a list.
        class MutantDecoder(Decoder):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.p.stdout.read(self.n)      # swallows a frame — exactly what `-ss` did
        md = MutantDecoder(P('a.mp4'), 64, 36)
        mvals = []
        while True:
            b = md.read()
            if b is None: break
            mvals.append(int(np.frombuffer(b, np.uint8)[0]))
        md.close()
        chk('3b the mutant reader (run) fails test 3', mvals != want,
            'the mutant returned exactly the sequence — test 3 has no teeth')

        # 4 · different aspect ratio = FAILURE, not stretching
        r4 = measure(P('a.mp4'), P('sq.mp4'), 64)
        st4 = dict((n, s) for s, n, _ in r4['checks'])
        chk('4 different aspect ratio → FAIL and not measured', st4.get('aspect ratio') == 'FAIL'
            and r4['hard'] and not r4['per_frame'], f"{st4.get('aspect ratio')} hard={r4['hard']}")

        # 5 · different fps = FAILURE
        r5 = measure(P('a.mp4'), P('f24.mp4'), 64)
        st5 = dict((n, s) for s, n, _ in r5['checks'])
        chk('5 different fps → FAIL', st5.get('frame rate') == 'FAIL' and r5['mismatch'],
            f"{st5.get('frame rate')}")
        chk('5b different fps: MAE is still 0 — i.e. the metric alone does not catch it',
            max(r5['per_frame'] or [9]) < 0.6)

        # 6 · one side longer → extra frames, not a silent drop
        r6 = measure(P('a.mp4'), P('long.mp4'), 64)
        st6 = dict((n, s) for s, n, _ in r6['checks'])
        chk('6 longer side → FAIL on frame count', st6.get('frame count') == 'FAIL')
        chk('6b longer side → extra frames recorded', st6.get('extra frames') == 'FAIL',
            f'{st6}')

        # 7 · crop changes the measurement, and an invalid crop fails
        r7 = measure(P('a.mp4'), P('grey2.mp4'), 64, ref_crop='32:18:0:0',
                     ours_crop='32:18:0:0')
        chk('7 a valid crop works', bool(r7['per_frame']) and not r7['hard'])
        chk('7b crop is recorded in the signature', r7['sig']['crop-source'] == '32:18:0:0')

        # 8 · invalid union → hard failure, NOT silently computed as mean
        r8 = measure(P('a.mp4'), P('b.mp4'), 64, union='typo')
        chk('8 invalid --union → failure', bool(r8['hard']) and not r8['per_frame'])

        # 9 · invalid range → error
        _, e1 = parse_ranges('a:5-2', N)
        _, e2 = parse_ranges('a:0-999', N)
        _, e3 = parse_ranges('bad', N)
        good, e4 = parse_ranges('a:0-5,b:6-9', N)
        chk('9 invalid ranges are caught', e1 and e2 and e3 and not e4
            and good == [('a', 0, 5), ('b', 6, 9)], f'{e1}{e2}{e3}{e4}')

        # 10 · decoder failure. A "junk file" only tests `probe`. The real case is
        #     a file that PASSES probe and is cut midway: without `-xerror` ffmpeg returns
        #     rc=0 and decodes partially, and the measurement looks fine.
        import numpy as _np
        from PIL import Image as _Im
        _mkvid(P('noise.mp4'), [_Im.fromarray((_np.random.RandomState(i).rand(180, 320, 3)
                                               * 255).astype('uint8')) for i in range(90)])
        trunc = P('trunc.mp4')
        shutil.copy(P('noise.mp4'), trunc)
        with open(trunc, 'r+b') as fh:
            fh.truncate(int(os.path.getsize(trunc) * 0.5))
        pr_t = probe(trunc)
        chk('10a the truncated file PASSES probe', pr_t['w'] == 320 and pr_t['nb'] == 90,
            f"{pr_t['w']}×{pr_t['h']} nb={pr_t['nb']}")
        # ⚠️ Three INDEPENDENT claims. A single "or" condition would survive each mutation on its own —
        #    i.e. a counter, not a gate.
        dtr = Decoder(trunc, 64, 36)
        while dtr.read() is not None:
            pass
        rc_t, _ = dtr.close()
        chk('10b the decoder returns rc≠0 on a truncated file (`-xerror`)', rc_t not in (0, None),
            f'rc={rc_t} — without -xerror ffmpeg decodes partially and returns 0')
        r10 = measure(P('noise.mp4'), trunc, 64)
        st10 = dict((n, s) for s, n, _ in r10['checks'])
        chk('10c the rc is turned into a hard failure', bool(r10['hard']), f"hard={r10['hard']}")
        chk('10d fewer frames than declared → a separate FAIL',
            st10.get('decoded frames') == 'FAIL', f'{st10}')
        chk('10e junk file → explicit failure', _junk_fails(P('a.mp4'), P('junk.mp4')))

        # 11 · signature: max and mean differ on a colour difference, coincide on grey
        pm = measure(P('a.mp4'), P('col.mp4'), 64, 'mean')['per_frame']
        px = measure(P('a.mp4'), P('col.mp4'), 64, 'max')['per_frame']
        gm = measure(P('a.mp4'), P('grey2.mp4'), 64, 'mean')['per_frame']
        gx = measure(P('a.mp4'), P('grey2.mp4'), 64, 'max')['per_frame']
        chk('11 max > mean on colour', np.mean(px) > np.mean(pm) * 1.2)
        chk('11b max ≈ mean on grey', abs(np.mean(gx) - np.mean(gm)) < 1.5)

        # 12 · measuring resolution changes the number (fine content) ⇒ it must be in the signature
        fine = P('fine.mp4')
        arr = (np.indices((36, 64)).sum(0) % 2 * 255).astype(np.uint8)
        _mkvid(fine, [Image.fromarray(np.dstack([arr] * 3)) for _ in range(N)])
        _mkvid(P('flat.mp4'), [(128, 128, 128)] * N)
        lo = measure(fine, P('flat.mp4'), 32)['per_frame']
        hi = measure(fine, P('flat.mp4'), 256)['per_frame']
        chk('12 resolution changes the number', abs(np.mean(hi) - np.mean(lo)) > 2,
            f'{np.mean(lo):.2f} / {np.mean(hi):.2f}')

        # 12b · an unknown flag must fail. `--bogus` used to be swallowed silently.
        import subprocess as _sp
        me = os.path.abspath(__file__)
        rb = _sp.run([sys.executable, me, P('a.mp4'), P('b.mp4'), '--bogus'],
                     capture_output=True)
        chk('12b --bogus → code≠0', rb.returncode != 0, f'rc={rb.returncode}')
        rv = _sp.run([sys.executable, me, P('a.mp4'), P('b.mp4'), '--union'],
                     capture_output=True)
        chk('12c --union without a value → code≠0', rv.returncode != 0, f'rc={rv.returncode}')
        ru = _sp.run([sys.executable, me, P('a.mp4'), P('b.mp4'), '--union', 'typo'],
                     capture_output=True)
        chk('12d --union typo on the CLI → code≠0', ru.returncode != 0, f'rc={ru.returncode}')

        # 13 · the signature is complete — every field requested
        sg = r['sig']
        need = ['algorithm-version', 'source-size', 'replica-size', 'fps-source', 'fps-replica',
                'crop-source', 'crop-replica', 'measure-resolution', 'scale-pipeline', 'alignment', 'SAR-source/replica',
                'pix_fmt-source', 'declared-colour-source', 'colour-conversion', 'channel-merge', 'ranges']
        miss = [k for k in need if k not in sg]
        chk('13 complete signature', not miss, f'missing: {miss}')
        chk('13b different signatures are not equal', measure(P('a.mp4'), P('b.mp4'), 64, 'max')['sig'] != sg)

        # 14 · proxy: same aspect ratio at a different resolution — ALLOWED, and recorded
        _mkvid(P('big.mp4'), ramp, size=(128, 72))
        r14 = measure(P('a.mp4'), P('big.mp4'), 64)
        st14 = dict((n, s) for s, n, _ in r14['checks'])
        chk('14 proxy allowed (same ratio)', st14.get('aspect ratio') == 'OK'
            and st14.get('size (after crop)') == 'WARN' and bool(r14['per_frame']),
            f'{st14}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'{"✅" if not fail else "❌"} selftest {"passed" if not fail else "failed"} — {ok}/{ok + fail}')
    return 0 if not fail else 1


def build_parser():
    """Hand-rolled argument parsing used to swallow flags silently: `--bogus` was not checked at all
    and the tool returned exit 0. argparse with `choices` fails on an unknown flag, a missing
    value and an invalid value — and returns code 2 by itself."""
    ap = argparse.ArgumentParser(
        prog='perframe.py', description='Per-frame difference, read as one continuous stream',
        allow_abbrev=False)
    ap.add_argument('ref'); ap.add_argument('ours')
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--union', choices=UNIONS, default='mean')
    ap.add_argument('--ranges', default=None)
    ap.add_argument('--ref-crop', default=None)
    ap.add_argument('--ours-crop', default=None)
    ap.add_argument('--allow-mismatch', action='store_true')
    ap.add_argument('--frames', action='store_true', help='print every value')
    ap.add_argument('--json', default=None)
    ap.add_argument('--selftest', action='store_true')
    return ap


if __name__ == '__main__':
    if '--selftest' in sys.argv[1:]:
        sys.exit(selftest())
    a = build_parser().parse_args()
    sys.exit(report(a.ref, a.ours, a.width, a.union, a.ranges, a.frames, a.json,
                    a.ref_crop, a.ours_crop, a.allow_mismatch))
