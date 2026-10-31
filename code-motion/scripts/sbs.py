#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sbs.py — source vs. replica: preflight · a comparison video to watch through · blink · full-resolution frames.

    python3 sbs.py REF.mp4 OURS.mp4 [--out DIR]
        [--ref-from A] [--ours-from B] [--duration D]      # source time ≠ our file's time
        [--ref-crop W:H:X:Y] [--ours-crop W:H:X:Y]
        [--every 0.1] [--width 360] [--metric-width 720]
        [--at 3.3,7.1] [--hires 3] [--allow-mismatch]
    python3 sbs.py --selftest

Writes to DIR (default: <OURS>-sbs/):
  preflight.txt  length · fps · size · aspect ratio · audio — **every difference shows up as a warning or a failure**
  sbs.mp4        REF | OURS | |diff| — at the same speed, each side's timecode, **A/B audio** (source left · ours right)
  blink.mp4      for each key moment: the same frame **frozen**, REF↔OURS alternating ×3 —
                 for typography, spacing and offset (time does NOT advance during the swap)
  hires/         for each key moment: REF · OURS · red/cyan overlay — **at source resolution, 1:1**
  frames*.png    a downscaled sheet — **for overview only**, not for judging typography
  gaps.json      for each moment: difference · affected area · measured severity (critical/significant/minor/encoding-noise)
  worst.txt      the outlier moments

═══ What the tool does NOT do (on purpose) ═══
⛔ It does not silently trim to the shorter length. The comparison window = the maximum of both sides; a side that ends early gets
   red `MISSING` frames that are counted. A missing ending cannot disappear.
⛔ It does not stretch to a common aspect ratio. Each side keeps its own ratio, padded into a shared box in a visible pad colour,
   and the gap is reported in the preflight.
⛔ It does not decide that the replication is faithful. "A low difference" is not "identical" — the tool shows, the eye decides.
"""
import sys, os, json, shutil, subprocess, argparse, math, glob, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _compare_core import (sh, probe, crop_dims, preflight, DUR_TOL, FPS_TOL, AR_TOL,  # noqa: E402
                           ALGO_VERSION, frames_of, signature, Decoder, extract_frame,
                           frame_chain)

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('numpy/Pillow missing:  pip3 install numpy pillow')

PAD_RGB = (86, 0, 86)        # pad colour — visible on purpose, so a different aspect ratio shows
MISS_RGB = (120, 24, 24)     # a frame missing on one side
# DUR_TOL · FPS_TOL · AR_TOL — from the core
DIFF_PX = 24                 # pixel difference above which the pixel counts as "affected"
SEV = [                      # (name, affected area above, or mean difference above)
    ('critical', 0.05, 25.0),
    ('significant', 0.005, 8.0),
    ('minor', 0.0002, 2.0),
]


# `sh` is imported from `_compare_core` — one core for both tools.


# `probe` is imported from `_compare_core` — one core for both tools.


def font(sz):
    for f in ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, sz)
            except Exception:
                pass
    return ImageFont.load_default()


# `crop_dims` is imported from `_compare_core` — one core for both tools.


# ─────────────────────────── preflight ───────────────────────────

# `preflight` is imported from `_compare_core` — one core for both tools.


# ─────────────────────────── measured severity ───────────────────────────

def severity(diff):
    """diff = an HxW array of the max per-channel difference. Returns (name, affected area, mean)."""
    area = float((diff > DIFF_PX).mean())
    mean = float(diff.mean())
    for name, a_th, m_th in SEV:
        if area >= a_th or mean >= m_th:
            return name, area, mean
    return 'encoding-noise', area, mean


def fit(arr, bw, bh):
    """Resize KEEPING THE RATIO + pad into the centre of a bw×bh box."""
    h, w = arr.shape[:2]
    k = min(bw / w, bh / h)
    nw, nh = max(1, int(round(w * k))), max(1, int(round(h * k)))
    im = Image.fromarray(arr).resize((nw, nh), Image.LANCZOS)
    box = Image.new('RGB', (bw, bh), PAD_RGB)
    box.paste(im, ((bw - nw) // 2, (bh - nh) // 2))
    return np.asarray(box)


# ─────────────────────────── the comparison ───────────────────────────

def run_compare(a):
    for t in ('ffmpeg', 'ffprobe'):
        if not shutil.which(t):
            sys.exit(f'{t} missing')
    R, O = probe(a.ref), probe(a.ours)
    rf, of = a.ref_from, a.ours_from
    if rf < 0 or of < 0:
        sys.exit('--ref-from / --ours-from must be non-negative')
    # `max(1, a.frames)` used to turn an invalid value into a one-frame window silently.
    #    Also: the bounds checks were in seconds, i.e. BEFORE the parameters were converted
    #    to frame indices — so `--ref-frame` was not checked at all.
    if a.frames is not None and a.frames < 1:
        sys.exit(f'--frames must be ≥1 (got {a.frames})')
    for nm_, v_ in (('--ref-frame', a.ref_frame), ('--ours-frame', a.ours_frame)):
        if v_ is not None and v_ < 0:
            sys.exit(f'{nm_} must be non-negative (got {v_})')
    if a.hires is not None and a.hires < 0:
        sys.exit(f'--hires must be ≥0 (0 = off; got {a.hires})')
    nfr_R, nfr_O = frames_of(R), frames_of(O)
    if a.ref_frame is not None and nfr_R and a.ref_frame >= nfr_R:
        sys.exit(f'--ref-frame {a.ref_frame} is past the end of the source ({nfr_R} frames)')
    if a.ours_frame is not None and nfr_O and a.ours_frame >= nfr_O:
        sys.exit(f'--ours-frame {a.ours_frame} is past the end of our file ({nfr_O} frames)')
    if a.ref_frame is None and rf >= R['dur']:
        sys.exit(f'--ref-from {rf} is past the length of the source ({R["dur"]:.3f})')
    if a.ours_frame is None and of >= O['dur']:
        sys.exit(f'--ours-from {of} is past the length of our file ({O["dur"]:.3f})')
    rdim = crop_dims(a.ref_crop, R['w'], R['h']) if a.ref_crop else (R['w'], R['h'])
    odim = crop_dims(a.ours_crop, O['w'], O['h']) if a.ours_crop else (O['w'], O['h'])
    # ⛔ the comparison window = the MAXIMUM, not the minimum — otherwise a missing ending disappears
    avail_r, avail_o = R['dur'] - rf, O['dur'] - of
    dur = a.duration if a.duration else max(avail_r, avail_o)
    if dur <= 0:
        sys.exit('empty comparison window')
    fps = R['fps'] or 25.0
    # THE WINDOW IS DEFINED IN FRAMES. Seconds stay for convenience, but they are converted
    #    to an index once, here — and from then on everything is indices.
    rfN = a.ref_frame if a.ref_frame is not None else int(round(rf * fps))
    ofN = a.ours_frame if a.ours_frame is not None else int(round(of * (O['fps'] or fps)))
    if a.frames:
        n_frames = max(1, a.frames)
        dur = n_frames / fps
    elif a.ref_frame is not None or a.ours_frame is not None:
        # The default used to take the full file length. `--ref-frame 530` on
        #    a 541-frame file asked for 541 frames from f530 (f530..1070) and returned 530
        #    MISSING frames. The window is derived from the REMAINDER, just like the window in seconds.
        rem_r, rem_o = max(0, nfr_R - rfN), max(0, nfr_O - ofN)
        n_frames = max(1, rem_r, rem_o)
        dur = n_frames / fps
    else:
        n_frames = max(1, int(round(dur * fps)))
    if a.ref_frame is not None:
        rf = rfN / fps
    if a.ours_frame is not None:
        of = ofN / (O['fps'] or fps)

    out = os.path.abspath(a.out or os.path.splitext(a.ours)[0] + '-sbs')
    os.makedirs(out, exist_ok=True)
    # ⛔ Only known comparison outputs are cleaned, so that hires/ or a sheet from an earlier run
    #    is not shown as a new result. No other file in the folder is deleted.
    for nm in ('sbs.mp4', 'blink.mp4', 'gaps.json', 'worst.txt', 'preflight.txt'):
        f_ = os.path.join(out, nm)
        if os.path.isfile(f_):
            os.remove(f_)
    for f_ in glob.glob(os.path.join(out, 'frames*.png')):
        os.remove(f_)
    hd = os.path.join(out, 'hires')
    if os.path.isdir(hd):
        shutil.rmtree(hd)
    os.makedirs(hd, exist_ok=True)

    # ⚠️ When a window is set (`--ref-from`/`--ours-from`/`--duration`), comparing the
    #    total frame count is meaningless, so it is skipped.
    # `--frames` was not counted as a "window": a 100-frame source vs a 50-frame replica,
    #    asking for only the first 10 — the tool returned exit 2 on comparing the full
    #    lengths, even though the window existed in full on both sides.
    win = None
    if a.frames is not None or a.ref_frame is not None or a.ours_frame is not None:
        win = (rfN, ofN, n_frames)
    windowed = win is not None or a.duration is not None or rf or of
    checks = preflight(R, O, rdim, odim, rf=rf, of=of, req_dur=a.duration, dur=dur,
                       check_counts=not windowed, win=win)
    lines = ['preflight — source vs. replica', f'  source: {a.ref}  (from {rf:g}s)',
             f'  ours: {a.ours}  (from {of:g}s)', f'  window: {dur:.3f}s · {n_frames} frames @ {fps:g}fps', '']
    for st, n, d in checks:
        lines.append(f'  [{st:4s}] {n}: {d}')
    n_fail = sum(1 for st, _, _ in checks if st == 'FAIL')
    n_warn = sum(1 for st, _, _ in checks if st == 'WARN')

    # ── decode both sides at the measuring resolution, keeping the ratio ──
    mw = a.metric_width
    bw = mw
    bh = int(round(mw / max(rdim[0] * R['sar'] / rdim[1], odim[0] * O['sar'] / odim[1]) / 2)) * 2
    bh = max(2, bh)

    # ONE DECODER FOR EVERY PATH. The main comparison, `hires/` and blink all use
    #    `_compare_core.Decoder`/`extract_frame` with the same `frame_chain`.
    #    When there was another local decoder here, one path used a variable left over from
    #    another loop and every hires image came out as THE SAME FRAME. The duplication is what allowed it.
    def scale_of(dims, sar):
        tw = max(2, int(round(dims[0] * sar)))
        return f'scale={tw}:{dims[1]},setsar=1'

    rw_px = max(2, int(round(rdim[0] * R['sar'])))
    ow_px = max(2, int(round(odim[0] * O['sar'])))
    pr = Decoder(a.ref, rw_px, rdim[1], crop=a.ref_crop, vf_extra=f'fps={fps}',
                 start_frame=rfN, count=n_frames, scale=scale_of(rdim, R['sar']))
    po = Decoder(a.ours, ow_px, odim[1], crop=a.ours_crop, vf_extra=f'fps={fps}',
                 start_frame=ofN, count=n_frames, scale=scale_of(odim, O['sar']))
    rb, ob = rw_px * rdim[1] * 3, ow_px * odim[1] * 3

    # ── the video encoder ──
    w = a.width
    ph = int(round(w * bh / bw / 2)) * 2
    head = 30
    vid = os.path.join(out, 'sbs.mp4')
    enc_in = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
              '-s', f'{3 * w}x{ph + head}', '-r', f'{fps}', '-i', '-']
    amap, ai = [], 1
    if R['audio'] or O['audio']:
        graph = []
        for side, info, start, has in (('l', R, rf, bool(R['audio'])), ('r', O, of, bool(O['audio']))):
            if has:
                enc_in += ['-ss', f'{start:.6f}', '-i', info['path']]
                graph.append(f'[{ai}:a]aresample=48000,aformat=channel_layouts=mono,'
                             f'atrim=duration={dur:.6f},asetpts=PTS-STARTPTS,apad[a{side}]')
                ai += 1
            else:
                enc_in += ['-f', 'lavfi', '-t', f'{dur:.6f}', '-i', 'anullsrc=r=48000:cl=mono']
                graph.append(f'[{ai}:a]asetpts=PTS-STARTPTS[a{side}]')
                ai += 1
        graph.append('[al][ar]join=inputs=2:channel_layout=stereo[a]')
        amap = ['-filter_complex', ';'.join(graph), '-map', '0:v', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k']
    enc = subprocess.Popen(enc_in + amap + ['-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
                                            '-movflags', '+faststart', '-t', f'{dur:.6f}', vid],
                           stdin=subprocess.PIPE)
    # ⛔ no -shortest: the length is set by -t, so a missing ending stays visible as MISSING

    blink_path = os.path.join(out, 'blink.mp4')

    f16, f14 = font(16), font(14)
    every_n = max(1, int(round(a.every * fps)))
    blink_n = max(1, int(round(0.25 * fps)))
    rows, gaps, missing_r, missing_o = [], [], 0, 0
    # An encoder that crashed midway used to raise `BrokenPipeError` and take down THE WHOLE tool (caught
    #    by fault injection). Now: stop writing to it, carry on, and report it as a hard failure.
    enc_broken = False
    keep_native = {}     # index ⇒ (ref_native, ours_native) for hires moments
    at_idx = {int(round((t - rf) * fps)) for t in (a.at or [])}

    for i in range(n_frames):
        br, bo = pr.read(), po.read()
        rok, ook = br is not None, bo is not None
        if rok:
            A_nat = np.frombuffer(br, np.uint8).reshape(rdim[1], rw_px, 3)
            A = fit(A_nat, bw, bh)
        else:
            missing_r += 1
            A_nat = None
            A = np.full((bh, bw, 3), MISS_RGB, np.uint8)
        if ook:
            B_nat = np.frombuffer(bo, np.uint8).reshape(odim[1], ow_px, 3)
            B = fit(B_nat, bw, bh)
        else:
            missing_o += 1
            B_nat = None
            B = np.full((bh, bw, 3), MISS_RGB, np.uint8)

        dmap = np.abs(A.astype(np.int16) - B.astype(np.int16)).max(axis=2)
        sev, area, mean = severity(dmap)
        if not (rok and ook):
            sev, area, mean = 'critical', 1.0, 255.0
        tr, to = rf + i / fps, of + i / fps
        gaps.append({'i': i, 'ref_t': round(tr, 4), 'ours_t': round(to, 4),
                     'ref_frame': int(round(tr * fps)), 'mean': round(mean, 2),
                     'area': round(area, 5), 'severity': sev,
                     'missing': (None if rok and ook else ('source' if not rok else 'ours'))})

        D = np.clip(dmap.astype(np.int16) * 2.2, 0, 255).astype(np.uint8)
        D = np.repeat(D[:, :, None], 3, axis=2)
        panel = Image.new('RGB', (3 * w, ph + head), (16, 16, 18))
        panel.paste(Image.fromarray(np.hstack([A, B, D])).resize((3 * w, ph), Image.LANCZOS), (0, head))
        dr = ImageDraw.Draw(panel)
        dr.text((8, 6), f'REF  {tr:7.3f}s  f{int(round(tr * fps))}' + ('' if rok else '  ⚠ MISSING'),
                fill=(240, 240, 235), font=f16)
        dr.text((w + 8, 6), f'OURS  {to:7.3f}s' + ('' if ook else '  ⚠ MISSING'), fill=(240, 240, 235), font=f16)
        dr.text((2 * w + 8, 6), f'|DIFF|x2.2   {mean:5.1f}   {sev}', fill=(240, 240, 235), font=f16)
        if not enc_broken:
            try:
                enc.stdin.write(panel.tobytes())
            except (BrokenPipeError, OSError):
                enc_broken = True

        if i % every_n == 0:
            rows.append((tr, to, mean, sev, A.copy(), B.copy(), D.copy()))
        if i in at_idx and A_nat is not None and B_nat is not None:
            keep_native[i] = (A_nat.copy(), B_nat.copy())

    # With `-frames:v <window>` the decoder EXITS BY ITSELF at the end of the window, so
    #    `close()` returns the real exit code. Previously, when the window was cut with `-t`,
    #    closing the pipe + terminate returned rc=255 even on a healthy decoder — which is where
    #    the `poll()` check before closing came from. It is no longer needed.
    rc_r, err_r = pr.close()
    rc_o, err_o = po.close()
    try:
        enc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    enc.wait()
    hard = []
    # A BROKEN FILE USED TO PASS. A file declaring 100 frames and cut midway passed
    #    the whole preflight, produced 47 MISSING frames and returned 2 — and with
    #    `--allow-mismatch` returned 0. With `-xerror` the decoder fails, and that is a HARD
    #    FAILURE (3) THAT CANNOT BE OVERRIDDEN: a file that cannot be decoded is not "a mismatch".
    for nm_, rc_, e_ in (('source decoder', rc_r, err_r), ('replica decoder', rc_o, err_o)):
        if rc_ is not None and rc_ > 0:
            first = e_.strip().splitlines()[0][:120] if e_.strip() else ''
            hard.append(f'{nm_} failed (rc={rc_}) {first}')
    if enc.returncode != 0 or enc_broken:
        hard.append('encoding sbs.mp4 failed')


    # ── full-resolution frames for the outlier moments (+ --at) ──
    ranked = sorted((g for g in gaps if g['missing'] is None), key=lambda g: -g['mean'])
    # `--hires 0` = OFF. Without `--at`, neither `hires/` nor `blink.mp4` is created,
    #    and there is no hard failure. With `--at` there is no automatic selection, but the explicit moments
    #    ARE extracted. Previously `--hires 0` crashed the tool with "no valid moments
    #    for blink" and code 3 — i.e. "off" was an error.
    hires_off = (a.hires == 0) and not at_idx
    picks, seen = [], set()
    for g in ranked:
        if len(picks) >= a.hires:
            break
        if any(abs(g['i'] - s) < max(1, int(0.3 * fps)) for s in seen):
            continue
        picks.append(g['i']); seen.add(g['i'])
    picks += [i for i in sorted(at_idx) if 0 <= i < n_frames and i not in seen]
    hires_files = []
    moments = []          # for each moment: an explicit state — 'ok' or 'extraction-failed'
    if hires_off:
        picks = []
        # the folder was created during setup (before `--at` is known) — removed when "off" applies
        try:
            shutil.rmtree(hd)
        except Exception:
            pass
    for i in sorted(set(picks)):
        tr, to = rf + i / fps, of + i / fps
        rp = os.path.join(out, 'hires', f'{i:05d}_ref.png')
        op = os.path.join(out, 'hires', f'{i:05d}_ours.png')
        # THE BUG THAT WAS HERE: `ir, io = rfN + g['i'], ofN + g['i']` — `g`
        #    was left over from ANOTHER loop, so every hires file was pulled from the same
        #    frame, with different file names and times. Reproduced: asking for frames 10 and 30
        #    produced `00010_ref.png` and `00030_ref.png` with IDENTICAL SHA. The right
        #    index is the `i` of this loop.
        ir, io = rfN + i, ofN + i
        gotr = extract_frame(a.ref, ir, rp, a.ref_crop, f'scale={rw_px}:{rdim[1]},setsar=1')
        goto = extract_frame(a.ours, io, op, a.ours_crop, f'scale={ow_px}:{odim[1]},setsar=1')
        # An extraction failure used to be a silent `continue`. Two moments were requested, one failed —
        #    and an evidence package was produced that was PARTIAL BUT LOOKED COMPLETE, with blink built from what was left.
        #    Now every moment has an explicit state, and a failure goes into `hard`.
        if not (gotr and goto):
            side = 'source' if not gotr else 'ours'
            moments.append({'i': i, 'ref_frame': ir, 'ours_frame': io,
                            'status': 'extraction-failed', 'side': side})
            hard.append(f'hires extraction failed at moment i={i} (source f{ir} · ours f{io}) — side {side}')
            continue
        try:
            RA, OA = np.asarray(Image.open(rp).convert('RGB')), np.asarray(Image.open(op).convert('RGB'))
        except Exception as e:
            moments.append({'i': i, 'ref_frame': ir, 'ours_frame': io,
                            'status': 'extraction-failed', 'side': 'PNG read'})
            hard.append(f'reading hires failed at moment i={i}: {e}')
            continue
        moments.append({'i': i, 'ref_frame': ir, 'ours_frame': io, 'status': 'ok'})
        # a red/cyan overlay at the larger shared resolution — an offset shows as coloured fringes
        H_, W_ = max(RA.shape[0], OA.shape[0]), max(RA.shape[1], OA.shape[1])
        ra = np.asarray(Image.fromarray(RA).resize((W_, H_), Image.LANCZOS)).astype(np.int16)
        oa = np.asarray(Image.fromarray(OA).resize((W_, H_), Image.LANCZOS)).astype(np.int16)
        ov = np.dstack([ra.mean(2), oa.mean(2), oa.mean(2)]).clip(0, 255).astype(np.uint8)
        ovp = os.path.join(out, 'hires', f'{i:05d}_overlay.png')
        Image.fromarray(ov).save(ovp)
        hires_files.append((i, tr, to, rp, op, ovp))

    # ── blink.mp4: pairs FROM THE SAME MOMENT, frozen, alternating ──────────
    # An earlier version swapped REF/OURS WHILE TIME ADVANCED — both the side and
    #    the frame changed, which is exactly what makes a blink useless for comparing typography.
    #    Now: every key moment is frozen, and the two sides swap on top of it.
    pairs = []
    for (_i, tr_, to_, rp_, op_, _ov) in hires_files:
        try:
            pairs.append((tr_, to_, Image.open(rp_).convert('RGB'), Image.open(op_).convert('RGB')))
        except Exception:
            continue
    if pairs:
        bwx = min(720, max(max(a_.width for _, _, a_, _ in pairs),
                           max(b_.width for _, _, _, b_ in pairs)))
        bhx = int(round(bwx * max(max(a_.height / a_.width for _, _, a_, _ in pairs),
                                  max(b_.height / b_.width for _, _, _, b_ in pairs)) / 2)) * 2
        BFPS, HOLD, CYCLES = 10, 3, 3
        benc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                 '-s', f'{bwx}x{bhx + head}', '-r', str(BFPS), '-i', '-',
                                 '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p',
                                 '-movflags', '+faststart', blink_path], stdin=subprocess.PIPE)
        broke = False
        for tr_, to_, RA_, OA_ in pairs:
            cards = []
            for lbl, im_, col in (('REF', RA_, (120, 255, 120)), ('OURS', OA_, (255, 180, 120))):
                c_ = Image.new('RGB', (bwx, bhx + head), (16, 16, 18))
                k_ = min(bwx / im_.width, bhx / im_.height)
                rz = im_.resize((max(1, int(im_.width * k_)), max(1, int(im_.height * k_))), Image.LANCZOS)
                c_.paste(rz, ((bwx - rz.width) // 2, head + (bhx - rz.height) // 2))
                ImageDraw.Draw(c_).text((8, 6), f'{lbl}  ·  REF {tr_:.3f}s / OURS {to_:.3f}s  (frozen)',
                                        fill=col, font=f16)
                cards.append(c_)
            for _c in range(CYCLES):
                for c_ in cards:
                    for _h in range(HOLD):
                        if not broke:
                            try:
                                benc.stdin.write(c_.tobytes())
                            except (BrokenPipeError, OSError):
                                broke = True
        try:
            benc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        benc.wait()
        if benc.returncode != 0 or broke or not os.path.isfile(blink_path) or os.path.getsize(blink_path) == 0:
            hard.append('creating blink.mp4 failed')
    elif not hires_off:
        hard.append('no valid moments for blink')

    # ── downscaled sheet (overview only) ──
    if rows:
        tw = 240
        th = int(round(tw * bh / bw))
        cards = []
        for tr, to, mean, sev, A, B, D in rows:
            card = Image.new('RGB', (3 * tw + 8, th + 20), (20, 20, 22))
            for k, im in enumerate((A, B, D)):
                card.paste(Image.fromarray(im).resize((tw, th), Image.LANCZOS), (k * (tw + 4), 20))
            ImageDraw.Draw(card).text((4, 2), f'REF {tr:6.2f}s · OURS {to:6.2f}s · {mean:5.1f} · {sev}',
                                      fill=(230, 230, 225), font=f14)
            cards.append(card)
        cols, per = 4, 48
        pages = (len(cards) + per - 1) // per
        for p in range(pages):
            ch = cards[p * per:(p + 1) * per]
            ln = (len(ch) + cols - 1) // cols
            cw_, chh = ch[0].width, ch[0].height
            sheet = Image.new('RGB', (cols * (cw_ + 10), ln * (chh + 8) + 24), (10, 10, 12))
            ImageDraw.Draw(sheet).text((8, 6), 'overview only — for typography and spacing: hires/ + blink.mp4',
                                       fill=(200, 200, 200), font=f14)
            for i, c in enumerate(ch):
                sheet.paste(c, ((i % cols) * (cw_ + 10), 24 + (i // cols) * (chh + 8)))
            sheet.save(os.path.join(out, f'frames-{p + 1:02d}.png' if pages > 1 else 'frames.png'))

    # ── reports ──
    counts = {}
    for g in gaps:
        counts[g['severity']] = counts.get(g['severity'], 0) + 1
    lines += ['', f'  missing frames: source {missing_r} · ours {missing_o}'
              + ('  ⛔ the comparison is partial' if (missing_r or missing_o) else ''),]
    if hard:
        lines += ['', '  ⛔ hard failures: ' + ' · '.join(hard)]
    lines += [
              '  measured severity (per frame): ' + ' · '.join(f'{k} {v}' for k, v in counts.items()),
              '', '  ⚠️ "severity" comes from pixels — it points where to look, not what matters.',
              '  ⚠️ the downscaled sheet is for overview; typography and spacing are judged in hires/ and the blink.']
    # THE SIGNATURE IS BUILT BEFORE ANY REPORT IS WRITTEN. Previously it was created AFTER
    #    `preflight.txt`, so the claim that "every report carries a signature" simply did not hold there.
    #    This is the SBS signature, not perframe's: here there is padding for the aspect ratio, conversion
    #    to square pixels by SAR, Pillow LANCZOS downscaling to the panel, and channel merge
    #    by MAX. There: ffmpeg-scale only and RGB mean.
    #    ⛔ A number from here and a number from there are not comparable.
    sig = signature('sbs.py', R, O, rdim, odim, (bw, bh), 'max per channel',
                    f'{rfN}–{rfN + n_frames - 1} (source) · {ofN}–{ofN + n_frames - 1} (ours)',
                    (a.ref_crop, a.ours_crop), n_frames - max(missing_r, missing_o), n_frames,
                    pipeline=('ffmpeg: crop → trim(start_frame) → scale to square pixels by SAR '
                              f'→ fps={fps:g} · then Pillow LANCZOS to the panel and padding '
                              f'with {PAD_RGB}, no stretching'),
                    align=f'frame index: source f{rfN} · ours f{ofN} · {n_frames} frames')
    lines += ['', 'measurement signature (sbs):'] + [f'  · {k}: {v}' for k, v in sig.items()]
    # a short signature id — so reports can be linked without duplicating the whole thing
    sig_id = hashlib.sha1('|'.join(f'{k}={v}' for k, v in sig.items())
                          .encode('utf-8')).hexdigest()[:12]
    sig['signature-id'] = sig_id
    txt = '\n'.join(lines)
    open(os.path.join(out, 'preflight.txt'), 'w', encoding='utf-8').write(txt + '\n')
    json.dump({'signature': sig, 'hires_off': hires_off, 'moments': moments,
               'ref': a.ref, 'ours': a.ours, 'ref_from': rf, 'ours_from': of, 'duration': dur,
               'fps': fps, 'preflight': [{'status': s, 'name': n, 'detail': d} for s, n, d in checks],
               'missing_ref': missing_r, 'missing_ours': missing_o, 'counts': counts,
               'frames': gaps}, open(os.path.join(out, 'gaps.json'), 'w'), ensure_ascii=False, indent=1)
    worst = sorted(gaps, key=lambda g: -g['mean'])[:15]
    with open(os.path.join(out, 'worst.txt'), 'w', encoding='utf-8') as f:
        f.write(f'The outlier moments — a place to start, not an importance ranking\n'
                f'measurement signature {sig_id} · {sig["tool"]} v{sig["algorithm-version"]} · '
                f'{sig["measure-resolution"]} · merge {sig["channel-merge"]} · '
                f'alignment {sig["alignment"]}\n'
                f'⛔ never compare to numbers from another signature.\n')
        for g in worst:
            f.write(f"  REF {g['ref_t']:7.3f}s (f{g['ref_frame']}) · OURS {g['ours_t']:7.3f}s · "
                    f"diff {g['mean']:6.2f} · area {g['area'] * 100:5.2f}% · {g['severity']}"
                    + (f" · missing in {g['missing']}" if g['missing'] else '') + '\n')
    return {'out': out, 'checks': checks, 'n_fail': n_fail, 'n_warn': n_warn, 'gaps': gaps,
            'missing_ref': missing_r, 'missing_ours': missing_o, 'counts': counts,
            'missing_total': missing_r + missing_o, 'hard': hard,
            'video': vid, 'blink': blink_path, 'hires': hires_files, 'text': txt,
            'hires_off': hires_off, 'moments': moments,
            'box': (bw, bh), 'frames': n_frames, 'fps': fps}


# ─────────────────────────── selftest ───────────────────────────

def _ns(**kw):
    d = dict(ref=None, ours=None, out=None, ref_crop=None, ours_crop=None, ref_from=0.0,
             ours_from=0.0, duration=None, every=0.5, width=240, metric_width=320,
             at=None, hires=1, allow_mismatch=True,
             ref_frame=None, ours_frame=None, frames=None)
    d.update(kw)
    return argparse.Namespace(**d)


def selftest():
    import tempfile
    print('═══ selftest — every case with a control: what must be caught, and what must pass clean ═══')
    d = tempfile.mkdtemp(prefix='sbstest_')
    cases, ok = [], True

    def mk(name, vsrc, extra=(), audio=None, t=2.0):
        p = os.path.join(d, name + '.mp4')
        c = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-t', str(t), '-i', vsrc]
        if audio:
            c += ['-f', 'lavfi', '-t', str(t), '-i', audio]
        # `+faststart` — the moov at the head, so a truncated file still PASSES probe
        # and fails only in decoding. That is the case that must be caught.
        c += list(extra) + ['-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p',
                            '-movflags', '+faststart']
        if audio:
            c += ['-c:a', 'aac']
        sh(c + [p])
        return p

    V = 'testsrc2=size=320x180:rate=25'
    try:
        base = mk('base', V)
        # 1 · identical to itself
        r = run_compare(_ns(ref=base, ours=base, out=os.path.join(d, 'o1')))
        mx = max(g['mean'] for g in r['gaps'])
        cases.append(('1 · control: identical to itself → zero failures, diff≈0, no MISSING',
                      r['n_fail'] == 0 and mx < 1.0 and r['missing_ref'] == 0 and r['missing_ours'] == 0,
                      f"fails {r['n_fail']} · max {mx:.2f} · missing {r['missing_ref']}/{r['missing_ours']}"))

        # 2 · a one-frame offset — must be caught
        off = mk('off', V, extra=['-vf', 'trim=start_frame=1,setpts=PTS-STARTPTS'])
        r = run_compare(_ns(ref=base, ours=off, out=os.path.join(d, 'o2')))
        sev = [g for g in r['gaps'] if g['severity'] in ('critical', 'significant')]
        cases.append(('2 · one-frame offset → caught as significant/critical', len(sev) >= 3,
                      f"{len(sev)} outlier frames out of {len(r['gaps'])}"))

        # 3 · a shot that starts at a non-zero time — correct alignment vs a negative control
        tail = mk('tail', V, extra=['-vf', 'trim=start=1.0,setpts=PTS-STARTPTS'], t=2.0)
        good = run_compare(_ns(ref=base, ours=tail, ref_from=1.0, ours_from=0.0, duration=0.9,
                               out=os.path.join(d, 'o3a')))
        bad = run_compare(_ns(ref=base, ours=tail, ref_from=0.0, ours_from=0.0, duration=0.9,
                              out=os.path.join(d, 'o3b')))
        gm = max(g['mean'] for g in good['gaps']); bm = max(g['mean'] for g in bad['gaps'])
        cases.append(('3 · --ref-from aligns a shot starting at 1.0 (control: without it there is a gap)',
                      gm < 3.0 and bm > gm * 3, f'aligned {gm:.2f} · not aligned {bm:.2f}'))

        # 4 · different lengths — failure + MISSING frames, no silent trimming
        short = mk('short', V, t=1.0)
        r = run_compare(_ns(ref=base, ours=short, out=os.path.join(d, 'o4')))
        st = dict((n, s) for s, n, _ in r['checks'])
        cases.append(('4 · different length → FAIL + MISSING frames counted',
                      st.get('length (from start point)') == 'FAIL' and r['missing_ours'] > 20,
                      f"status {st.get('length (from start point)')} · missing-ours {r['missing_ours']}"))

        # 5 · different aspect ratio → FAIL, and no stretching (padding visible in the frame)
        tall = mk('tall', 'testsrc2=size=180x320:rate=25')
        r = run_compare(_ns(ref=base, ours=tall, out=os.path.join(d, 'o5'), hires=1))
        st = dict((n, s) for s, n, _ in r['checks'])
        pad_seen = False
        if r['hires']:
            pass
        frame = sh(['ffmpeg', '-v', 'error', '-ss', '0.2', '-i', r['video'], '-frames:v', '1',
                    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], binary=True).stdout
        arr = np.frombuffer(frame, np.uint8)
        pad_seen = bool(((np.abs(arr.reshape(-1, 3).astype(int) - np.array(PAD_RGB)).max(1)) < 30).any())
        cases.append(('5 · different aspect ratio → FAIL + visible padding (not stretching)',
                      st.get('aspect ratio') == 'FAIL' and pad_seen,
                      f"status {st.get('aspect ratio')} · padding-seen {pad_seen}"))

        # 6 · crop — the real frame is embedded; with --ref-crop identical, without it a gap
        boxed = mk('boxed', V, extra=['-vf', 'pad=480:280:80:50:color=white'])
        g2 = run_compare(_ns(ref=boxed, ours=base, ref_crop='320:180:80:50', out=os.path.join(d, 'o6a')))
        b2 = run_compare(_ns(ref=boxed, ours=base, out=os.path.join(d, 'o6b')))
        gm2 = max(g['mean'] for g in g2['gaps']); bm2 = max(g['mean'] for g in b2['gaps'])
        cases.append(('6 · --ref-crop recovers an embedded frame (control: without it a large gap)',
                      gm2 < 3.0 and bm2 > 15, f'with crop {gm2:.2f} · without {bm2:.2f}'))

        # 7 · audio on both sides → stereo, left=source right=ours
        ra = mk('ra', V, audio='sine=frequency=440:sample_rate=48000')
        oa = mk('oa', V, audio='sine=frequency=880:sample_rate=48000')
        r = run_compare(_ns(ref=ra, ours=oa, out=os.path.join(d, 'o7')))
        chans = sh(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries',
                    'stream=channels', '-of', 'csv=p=0', r['video']]).stdout.strip()

        def chan_peak_freq(path, ch):
            raw = sh(['ffmpeg', '-v', 'error', '-i', path, '-af', f'pan=mono|c0=c{ch}',
                      '-ar', '48000', '-f', 's16le', '-'], binary=True).stdout
            x = np.frombuffer(raw, np.int16).astype(float)[:48000]
            if x.size < 1000:
                return 0.0
            sp = np.abs(np.fft.rfft(x * np.hanning(x.size)))
            return float(np.fft.rfftfreq(x.size, 1 / 48000)[int(np.argmax(sp))])
        fl, fr = chan_peak_freq(r['video'], 0), chan_peak_freq(r['video'], 1)
        cases.append(('7 · audio on both sides → stereo · left=source(440) · right=ours(880)',
                      chans == '2' and abs(fl - 440) < 25 and abs(fr - 880) < 25,
                      f'channels {chans} · left {fl:.0f}Hz · right {fr:.0f}Hz'))

        # 8 · audio on one side only → a warning, the missing side silent, the source kept
        r = run_compare(_ns(ref=ra, ours=base, out=os.path.join(d, 'o8')))
        st = dict((n, s) for s, n, _ in r['checks'])
        fl2 = chan_peak_freq(r['video'], 0)
        raw_r = sh(['ffmpeg', '-v', 'error', '-i', r['video'], '-af', 'pan=mono|c0=c1',
                    '-ar', '48000', '-f', 's16le', '-'], binary=True).stdout
        rms_r = float(np.sqrt((np.frombuffer(raw_r, np.int16).astype(float) ** 2).mean() + 1e-9))
        cases.append(('8 · audio only in the source → WARN · left kept · right silent',
                      st.get('audio') == 'WARN' and abs(fl2 - 440) < 25 and rms_r < 50,
                      f"status {st.get('audio')} · left {fl2:.0f}Hz · rms-right {rms_r:.1f}"))

        # 9 · no audio on either side → a warning, and no audio channel in the output
        r = run_compare(_ns(ref=base, ours=base, out=os.path.join(d, 'o9')))
        st = dict((n, s) for s, n, _ in r['checks'])
        na = sh(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries',
                 'stream=index', '-of', 'csv=p=0', r['video']]).stdout.strip()
        cases.append(('9 · no audio on either side → WARN · output without an audio channel',
                      st.get('audio') == 'WARN' and na == '', f"status {st.get('audio')} · audio channels '{na}'"))

        # 10 · different frame rate → FAIL, and exit code ≠ 0 without --allow-mismatch.
        # This used to be a WARN: two files with the same frame count but different fps
        #    return a perfect metric while the motion IN TIME is completely different. ⇒ a failure.
        f30 = mk('f30', 'testsrc2=size=320x180:rate=30')
        r = run_compare(_ns(ref=base, ours=f30, out=os.path.join(d, 'o10')))
        st = dict((n, s) for s, n, _ in r['checks'])
        cases.append(('10 · different fps → FAIL (not WARN)', st.get('frame rate') == 'FAIL',
                      f"status {st.get('frame rate')}"))
        cases.append(('10b · different fps → code≠0, and --allow-mismatch approves',
                      exit_code(r, False) != 0 and exit_code(r, True) == 0,
                      f'{exit_code(r, False)} / {exit_code(r, True)}'))

        # ══ 24 · THE REQUESTED FRAME IS THE ONE EXTRACTED ═══════════════════
        #    The bug: `ir, io = rfN + g['i'], …` — `g` was left over from ANOTHER loop, so
        #    every hires image was pulled from the same frame. Reproduced: asking for frames 10 and 30
        #    gave `00010_ref.png` and `00030_ref.png` with IDENTICAL SHA.
        #    ⛔ "the two images differ" alone is not enough — the test also checks that every
        #    image is the EXACT frame requested, against a counter film in which frame k
        #    is painted with value k.
        cnt = os.path.join(d, 'counter.mp4')
        cdir = os.path.join(d, 'cf'); os.makedirs(cdir, exist_ok=True)
        for k in range(40):
            Image.new('RGB', (64, 64), (k * 6 % 256, k * 6 % 256, k * 6 % 256)).save(
                os.path.join(cdir, f'{k:04d}.png'))
        sh(['ffmpeg', '-v', 'error', '-y', '-framerate', '25', '-i',
            os.path.join(cdir, '%04d.png'), '-c:v', 'libx264', '-qp', '0',
            '-pix_fmt', 'yuv444p', '-movflags', '+faststart', cnt])
        o24 = os.path.join(d, 'o24')
        r24 = run_compare(_ns(ref=cnt, ours=cnt, out=o24, at=[10 / 25, 30 / 25], hires=0))
        import hashlib as _hl
        def _sha(f_):
            return _hl.sha1(open(f_, 'rb').read()).hexdigest()
        def _val(f_):
            return int(np.asarray(Image.open(f_).convert('RGB'))[32, 32, 0])
        f10 = os.path.join(o24, 'hires', '00010_ref.png')
        f30 = os.path.join(o24, 'hires', '00030_ref.png')
        o10 = os.path.join(o24, 'hires', '00010_ours.png')
        o30 = os.path.join(o24, 'hires', '00030_ours.png')
        have = all(os.path.isfile(x) for x in (f10, f30, o10, o30))
        cases.append(('24 · two hires frames were created', have, f'{os.listdir(os.path.join(o24, "hires"))}'))
        if have:
            cases.append(('24b · the two ref images are NOT identical', _sha(f10) != _sha(f30),
                          f'sha {_sha(f10)[:8]} / {_sha(f30)[:8]}'))
            cases.append(('24c · the two ours images are NOT identical', _sha(o10) != _sha(o30),
                          f'sha {_sha(o10)[:8]} / {_sha(o30)[:8]}'))
            # The strong claim: every image is the EXACT frame (value k·6 mod 256)
            cases.append(('24d · 00010 is exactly frame 10', abs(_val(f10) - 60) <= 2,
                          f'value {_val(f10)} instead of 60'))
            cases.append(('24e · 00030 is exactly frame 30', abs(_val(f30) - 180) <= 2,
                          f'value {_val(f30)} instead of 180'))
            cases.append(('24f · ours is exact too', abs(_val(o10) - 60) <= 2 and abs(_val(o30) - 180) <= 2,
                          f'{_val(o10)} / {_val(o30)}'))

        # ══ 25 · `--frames` is judged as a WINDOW, not as a whole film ═════
        #    A 100-frame source vs a 50-frame replica, asking for the first 10 — the ten
        #    frames exist and are identical and there is no MISSING, yet the tool returned exit 2
        #    on comparing the full lengths.
        long100 = mk('long100', 'testsrc2=size=320x180:rate=25', t=4.0)     # 100 frames
        short50 = mk('short50', 'testsrc2=size=320x180:rate=25', t=2.0)     # 50 frames
        r25 = run_compare(_ns(ref=long100, ours=short50, out=os.path.join(d, 'o25'),
                              frames=10, allow_mismatch=False))
        st25 = dict((n, st) for st, n, _ in r25['checks'])
        cases.append(('25 · positive control: different lengths, the window exists on both → code 0',
                      exit_code(r25, False) == 0 and r25['missing_total'] == 0,
                      f"code {exit_code(r25, False)} · MISSING {r25['missing_total']} · {st25}"))
        cases.append(('25b · the FRAME WINDOW is checked, not the file lengths',
                      'frame window' in st25 and 'frame count' not in st25, f'{list(st25)}'))
        # negative control: the window exceeds the shorter side
        r25c = run_compare(_ns(ref=long100, ours=short50, out=os.path.join(d, 'o25c'),
                               frames=80, allow_mismatch=False))
        st25c = dict((n, st) for st, n, _ in r25c['checks'])
        cases.append(('25c · negative control: window exceeds → FAIL + MISSING + code 2',
                      st25c.get('frame window') == 'FAIL' and r25c['missing_total'] > 0
                      and exit_code(r25c, False) == 2,
                      f"{st25c.get('frame window')} · MISSING {r25c['missing_total']} · "
                      f'code {exit_code(r25c, False)}'))

        # ══ 26 · argument validation ═══════════════════════════════════════
        #    `max(1, a.frames)` turned an invalid value into a one-frame window SILENTLY,
        #       and the bounds checks were in seconds — i.e. before conversion to indices.
        def _rejects(**kw):
            try:
                run_compare(_ns(ref=long100, ours=long100,
                                out=os.path.join(d, 'oarg'), **kw))
                return False
            except SystemExit:
                return True
        bad = {'--frames 0': _rejects(frames=0), '--frames -5': _rejects(frames=-5),
               '--ref-frame -1': _rejects(ref_frame=-1), '--ours-frame -3': _rejects(ours_frame=-3),
               '--ref-frame past the end': _rejects(ref_frame=9999),
               '--hires -1': _rejects(hires=-1)}
        cases.append(('26 · invalid arguments are rejected explicitly', all(bad.values()),
                      ' · '.join(f'{k}={v}' for k, v in bad.items() if not v)))
        # ══ 26b · `--hires 0` = REALLY OFF ═══════════════════════════════
        #    The earlier test only checked `isinstance(r26, dict)` — i.e. a counter.
        #    In reality `--frames 1 --hires 0` crashed with "no valid moments for blink"
        #    and returned RC=3, i.e. "off" was an error.
        o26 = os.path.join(d, 'o26')
        r26 = run_compare(_ns(ref=long100, ours=long100, out=o26, frames=1, hires=0))
        cases.append(('26b · --hires 0 → no hard failure and code 0',
                      not r26['hard'] and exit_code(r26, False) == 0,
                      f"hard={r26['hard']} code={exit_code(r26, False)}"))
        cases.append(('26c · --hires 0 → no blink.mp4 and no hires/',
                      not os.path.exists(r26['blink']) and not r26['hires']
                      and not os.path.isdir(os.path.join(o26, 'hires')),
                      f"blink={os.path.exists(r26['blink'])} hires={r26['hires']}"))
        msg26 = final_message(r26)
        # ⚠️ The test is on the LIST OF OUTPUTS (up to the bracket) and on the pointer line — not on
        #    the note itself, which mentions the names in the context of "off".
        prod26 = msg26.strip().split('\n')[0].split('(')[0]
        hint26 = msg26.strip().split('\n')[1]
        cases.append(('26d · the TEXT of the final message does not announce outputs that are off',
                      'blink.mp4' not in prod26 and 'hires/' not in prod26
                      and 'hires/' not in hint26 and 'off' in msg26,
                      f'products={prod26!r} hint={hint26!r}'))
        msg26on = final_message(r24)
        cases.append(('26d2 · positive control: when they are on, the message DOES announce them',
                      'blink.mp4' in msg26on and 'hires/' in msg26on,
                      msg26on.replace('\n', ' | ')))
        # `--hires 0` WITH `--at`: no automatic selection, but the explicit moments are
        o26e = os.path.join(d, 'o26e')
        r26e = run_compare(_ns(ref=cnt, ours=cnt, out=o26e, hires=0, at=[10 / 25, 30 / 25]))
        cases.append(('26e · --hires 0 + --at → only the explicit moments',
                      len(r26e['hires']) == 2 and not r26e['hard'],
                      f"{len(r26e['hires'])} · {r26e['hard']}"))

        # ══ 28 · the default window = the REMAINDER after the start index ═══
        #    `--ref-frame 530` on a 541-frame file asked for 541 frames from f530
        #       and returned 530 MISSING frames.
        r28 = run_compare(_ns(ref=cnt, ours=cnt, out=os.path.join(d, 'o28'),
                              ref_frame=30, ours_frame=30, hires=0))
        cases.append(('28 · start at f30 out of 40 → 10 frames, no MISSING',
                      r28['frames'] == 10 and r28['missing_total'] == 0
                      and exit_code(r28, False) == 0,
                      f"frames={r28['frames']} missing={r28['missing_total']} "
                      f'code={exit_code(r28, False)}'))
        # one side shorter after the start point ⇒ the maximum of the two remainders, MISSING only on the short side
        cnt20 = os.path.join(d, 'counter20.mp4')
        c20 = os.path.join(d, 'cf20'); os.makedirs(c20, exist_ok=True)
        for k in range(20):
            Image.new('RGB', (64, 64), (k * 6 % 256,) * 3).save(os.path.join(c20, f'{k:04d}.png'))
        sh(['ffmpeg', '-v', 'error', '-y', '-framerate', '25', '-i',
            os.path.join(c20, '%04d.png'), '-c:v', 'libx264', '-qp', '0',
            '-pix_fmt', 'yuv444p', '-movflags', '+faststart', cnt20])
        r28b = run_compare(_ns(ref=cnt, ours=cnt20, out=os.path.join(d, 'o28b'),
                               ref_frame=10, ours_frame=10, hires=0))
        cases.append(('28b · remainders 30 and 10 → window 30, MISSING only on the short side',
                      r28b['frames'] == 30 and r28b['missing_ours'] == 20
                      and r28b['missing_ref'] == 0,
                      f"frames={r28b['frames']} miss_ref={r28b['missing_ref']} "
                      f"miss_ours={r28b['missing_ours']}"))

        # ══ 29 · an extraction failure at one moment = a HARD FAILURE, not a partial package ══
        #    `extract_frame` returned None and the loop did `continue` silently:
        #       two moments were requested, one failed — and an evidence package was produced that was PARTIAL
        #       BUT LOOKED COMPLETE, with blink built from what was left.
        import _compare_core as _cc
        _orig_ef = _cc.extract_frame
        calls = {'n': 0}
        def _flaky(path, idx, outp, crop=None, scale=None):
            calls['n'] += 1
            if calls['n'] == 3:          # the second moment, source side
                return None
            return _orig_ef(path, idx, outp, crop, scale)
        import sbs as _self  # noqa: F401
        globals()['extract_frame'] = _flaky
        try:
            r29 = run_compare(_ns(ref=cnt, ours=cnt, out=os.path.join(d, 'o29'),
                                  hires=0, at=[10 / 25, 30 / 25]))
            ok29 = (bool(r29['hard']) and exit_code(r29, True) == 3
                    and any(m['status'] == 'extraction-failed' for m in r29['moments']))
            det29 = f"hard={r29['hard']} moments={r29['moments']}"
        finally:
            globals()['extract_frame'] = _orig_ef
        cases.append(('29 · fault injection: one moment fails → code 3 and an explicit state', ok29, det29))

        # ══ 27 · the signature in every report ═════════════════════════════
        o27 = r24['out'] if isinstance(r24, dict) else o24
        pf = open(os.path.join(o27, 'preflight.txt'), encoding='utf-8').read()
        wt = open(os.path.join(o27, 'worst.txt'), encoding='utf-8').read()
        gj = json.load(open(os.path.join(o27, 'gaps.json')))
        sid = gj.get('signature', {}).get('signature-id', '')
        cases.append(('27 · signature in gaps.json', bool(gj.get('signature')) and bool(sid), f'sid={sid!r}'))
        cases.append(('27b · signature in preflight.txt', 'measurement signature' in pf, pf[:80]))
        cases.append(('27c · signature id in worst.txt', sid and sid in wt, wt[:120]))

        # 10c · A TRUNCATED FILE — a hard failure that cannot be overridden.
        #     Without `-xerror` it passed the whole preflight, produced MISSING frames
        #     and returned 2 — and with `--allow-mismatch` returned 0. A file that cannot
        #     be decoded is not "a mismatch" but a failure: code 3, in every case.
        noisy = mk('noisy', 'testsrc2=size=320x180:rate=25', t=4.0)
        trunc = os.path.join(d, 'trunc.mp4')
        shutil.copyfile(noisy, trunc)
        with open(trunc, 'r+b') as fh:
            fh.truncate(int(os.path.getsize(trunc) * 0.5))
        pt = probe(trunc)
        cases.append(('10c · the truncated file passes probe (otherwise the test checks probe)',
                      pt['w'] == 320 and (pt['nb'] or 0) >= 90, f"{pt['w']} nb={pt['nb']}"))
        rt = run_compare(_ns(ref=noisy, ours=trunc, out=os.path.join(d, 'o10c')))
        # ⚠️ The claim is SPECIFIC TO THE DECODER. "hard is not empty" alone survived the mutation
        #    of removing `-xerror` — because the encoder failed too, and that masked the check.
        cases.append(('10d · truncated file → a failure OF THE DECODER (rc)',
                      any('decoder' in h for h in rt['hard']), f"hard={rt['hard']}"))
        cases.append(('10e · truncated file → code 3 EVEN with --allow-mismatch',
                      exit_code(rt, True) == 3 and exit_code(rt, False) == 3,
                      f'{exit_code(rt, True)} / {exit_code(rt, False)}'))

        # 11 · a missing ending is not hidden: the video length = the full window
        r = run_compare(_ns(ref=base, ours=short, out=os.path.join(d, 'o11')))
        vd = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                       'csv=p=0', r['video']]).stdout.strip())
        cases.append(('11 · missing ending: sbs.mp4 at full length (2.0), not trimmed to 1.0', vd > 1.8,
                      f'output length {vd:.2f}s'))

        # 14 · A REQUESTED WINDOW: an identical section from a long source — must pass without --allow-mismatch
        r = run_compare(_ns(ref=base, ours=tail, ref_from=1.0, ours_from=0.0, duration=0.9,
                            out=os.path.join(d, 'o14'), allow_mismatch=False))
        mx14 = max(g['mean'] for g in r['gaps'])
        cases.append(('14 · a 0.9s window from a 2.0s source vs a 1.0s shot → passes clean (code 0)',
                      exit_code(r, False) == 0 and r['n_fail'] == 0 and r['missing_total'] == 0 and mx14 < 3.0,
                      f"code {exit_code(r, False)} · fails {r['n_fail']} · missing {r['missing_total']} · max {mx14:.2f}"))

        # 15 · reverse control: a window longer than available → FAIL
        r = run_compare(_ns(ref=base, ours=tail, ref_from=1.0, ours_from=0.0, duration=1.5,
                            out=os.path.join(d, 'o15'), allow_mismatch=False))
        st = dict((n, s_) for s_, n, _ in r['checks'])
        cases.append(('15 · control: a 1.5s window vs 1.0 available → FAIL + error code',
                      st.get('requested window') == 'FAIL' and exit_code(r, False) != 0,
                      f"status {st.get('requested window')} · code {exit_code(r, False)}"))

        # 16 · audio only in OURS — the direction not checked before
        r = run_compare(_ns(ref=base, ours=oa, out=os.path.join(d, 'o16')))
        st = dict((n, s_) for s_, n, _ in r['checks'])
        fr16 = chan_peak_freq(r['video'], 1)
        raw_l = sh(['ffmpeg', '-v', 'error', '-i', r['video'], '-af', 'pan=mono|c0=c0',
                    '-ar', '48000', '-f', 's16le', '-'], binary=True).stdout
        rms_l = float(np.sqrt((np.frombuffer(raw_l, np.int16).astype(float) ** 2).mean() + 1e-9))
        cases.append(('16 · audio only in ours → WARN · right kept(880) · left silent',
                      st.get('audio') == 'WARN' and abs(fr16 - 880) < 25 and rms_l < 50,
                      f"status {st.get('audio')} · right {fr16:.0f}Hz · rms-left {rms_l:.1f}"))

        # 17 · stereo MIXED FROM BOTH CHANNELS, not "left only"
        st2 = os.path.join(d, 'st2.mp4')
        sh(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-t', '2.0', '-i', V,
            '-f', 'lavfi', '-t', '2.0', '-i', 'sine=frequency=440:sample_rate=48000',
            '-f', 'lavfi', '-t', '2.0', '-i', 'sine=frequency=1200:sample_rate=48000',
            '-filter_complex', '[1:a][2:a]join=inputs=2:channel_layout=stereo[a]',
            '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-crf', '14',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', st2])

        def band(path, ch, f0):
            raw = sh(['ffmpeg', '-v', 'error', '-i', path, '-af', f'pan=mono|c0=c{ch}',
                      '-ar', '48000', '-f', 's16le', '-'], binary=True).stdout
            x = np.frombuffer(raw, np.int16).astype(float)[:48000]
            sp = np.abs(np.fft.rfft(x * np.hanning(x.size)))
            fr_ = np.fft.rfftfreq(x.size, 1 / 48000)
            sel = (fr_ > f0 - 20) & (fr_ < f0 + 20)
            return float(sp[sel].max() / (sp.max() + 1e-9))
        r = run_compare(_ns(ref=st2, ours=base, out=os.path.join(d, 'o17')))
        e440, e1200 = band(r['video'], 0, 440), band(r['video'], 0, 1200)
        cases.append(('17 · stereo source (L 440 · R 1200) → the left contains BOTH',
                      e440 > 0.2 and e1200 > 0.2, f'440 {e440:.2f} · 1200 {e1200:.2f} (ratio to peak)'))

        # 18 · MISSING frames → an error exit code
        r = run_compare(_ns(ref=base, ours=short, out=os.path.join(d, 'o18'), allow_mismatch=False))
        cases.append(('18 · MISSING frames → an error exit code', r['missing_total'] > 0 and exit_code(r, False) != 0,
                      f"missing {r['missing_total']} · code {exit_code(r, False)}"))

        # 18b · MISSING ON ITS OWN — with no preflight failure — must return an error code
        #      (case 18 is not isolated: there the preflight fails too)
        fake = {'hard': [], 'n_fail': 0, 'missing_total': 3}
        cases.append(('18b · MISSING alone (clean preflight) → code≠0, and --allow-mismatch approves',
                      exit_code(fake, False) != 0 and exit_code(fake, True) == 0,
                      f'without approval {exit_code(fake, False)} · with approval {exit_code(fake, True)}'))

        # 21 · blink is FROZEN: for each moment only two distinct frames, not a flowing sequence
        r = run_compare(_ns(ref=base, ours=off, out=os.path.join(d, 'o21'), hires=1))
        raw_b = sh(['ffmpeg', '-v', 'error', '-i', r['blink'], '-vf', 'scale=64:36',
                    '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], binary=True).stdout
        fb_ = np.frombuffer(raw_b, np.uint8).reshape(-1, 36 * 64).astype(int)
        # ⚠️ lossy encoding changes bytes even in identical frames ⇒ count TRANSITIONS, not bytes.
        trans = sum(1 for i_ in range(1, len(fb_)) if np.abs(fb_[i_] - fb_[i_ - 1]).mean() > 3)
        cases.append(('21 · blink freezes the moment: few transitions (side swaps), not a flowing sequence',
                      len(fb_) >= 12 and trans <= 6, f'{len(fb_)} frames · {trans} transitions'))

        # 20 · FAULT INJECTION: encoding blink fails → hard failure + code 3, even with --allow-mismatch
        _orig_popen = subprocess.Popen

        def _broken(args, **kw):
            if isinstance(args, list) and any(str(x).endswith('blink.mp4') for x in args):
                args = list(args)
                args[args.index('libx264')] = 'no_such_codec_zz'
            return _orig_popen(args, **kw)
        subprocess.Popen = _broken
        try:
            r = run_compare(_ns(ref=base, ours=base, out=os.path.join(d, 'o20')))
        finally:
            subprocess.Popen = _orig_popen
        cases.append(('20 · fault injection: encoding blink fails → hard failure + code 3',
                      bool(r['hard']) and exit_code(r, True) == 3,
                      f"hard {r['hard']} · code {exit_code(r, True)}"))

        # 19 · cleanup: an old output from an earlier run does not survive
        stale = os.path.join(d, 'o18', 'hires', 'ZZZZ_stale.png')
        Image.new('RGB', (4, 4)).save(stale)
        open(os.path.join(d, 'o18', 'frames-99.png'), 'wb').write(b'x')
        run_compare(_ns(ref=base, ours=short, out=os.path.join(d, 'o18')))
        cases.append(('19 · a re-run cleans old hires/ and sheets',
                      not os.path.exists(stale) and not os.path.exists(os.path.join(d, 'o18', 'frames-99.png')),
                      f"stale {os.path.exists(stale)}"))

        # 13 · audio shorter than the video on one side → THE ENDING IS NOT CUT (apad + -t, no -shortest)
        shortaud = os.path.join(d, 'shortaud.mp4')
        sh(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-t', '2.0', '-i', V,
            '-f', 'lavfi', '-t', '0.8', '-i', 'sine=frequency=440:sample_rate=48000',
            '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', '-c:a', 'aac', shortaud])
        r = run_compare(_ns(ref=shortaud, ours=oa, out=os.path.join(d, 'o13')))
        vd13 = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                         'csv=p=0', r['video']]).stdout.strip())
        tail = sh(['ffmpeg', '-v', 'error', '-ss', '1.6', '-i', r['video'], '-af', 'pan=mono|c0=c1',
                   '-ar', '48000', '-f', 's16le', '-'], binary=True).stdout
        tail_rms = float(np.sqrt((np.frombuffer(tail, np.int16).astype(float) ** 2).mean() + 1e-9))
        cases.append(('13 · source audio shorter than the video → full-length output, and the ending is heard',
                      vd13 > 1.9 and tail_rms > 500, f'length {vd13:.2f} · rms-end {tail_rms:.0f}'))

        # 12 · full-resolution frames + overlay are created
        r = run_compare(_ns(ref=base, ours=off, out=os.path.join(d, 'o12'), hires=2, at=[0.4]))
        hs = r['hires']
        allok = len(hs) >= 2 and all(os.path.getsize(p) > 0 for _, _, _, a1, b1, c1 in hs for p in (a1, b1, c1))
        native = Image.open(hs[0][3]).size if hs else (0, 0)
        cases.append(('12 · hires/ at source resolution + red/cyan overlay',
                      allok and native == (320, 180), f'{len(hs)} moments · size {native}'))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    for name, passed, detail in cases:
        print(f"  {'✅' if passed else '❌'} {name}")
        if not passed:
            print(f'      ⟵ {detail}'); ok = False
    print(f"\n{'✅ selftest passed' if ok else '❌ selftest failed'} — "
          f"{sum(1 for _, p, _ in cases if p)}/{len(cases)}")
    return ok


# ─────────────────────────── main ───────────────────────────

def final_message(r):
    """The final message as a PURE FUNCTION, so the text itself can be tested.
    The test "the final message does not announce outputs that are off" used to check only
       `hires_off is True` — i.e. the flag, not the message. Now it checks the text."""
    made = ['sbs.mp4']
    if r.get('blink') and os.path.isfile(r['blink']):
        made.append('blink.mp4')
    if r.get('hires'):
        made.append('hires/')
    made += ['frames*.png', 'gaps.json', 'worst.txt']
    line1 = f"\n✓ {r['out']}/" + ' · '.join(made) + \
        ('   (--hires 0: hires/ and blink are off)' if r.get('hires_off') else '')
    line2 = '  watch sbs.mp4 through at normal speed' + \
        ('' if r.get('hires_off') else ' · typography and spacing ⇐ hires/ and blink.mp4')
    return line1 + '\n' + line2


def exit_code(r, allow_mismatch, verbose=False):
    """3 = hard failure (always) · 2 = mismatch or missing frames (unless --allow-mismatch) · 0 = OK."""
    if r['hard']:
        if verbose:
            print('\n⛔ hard failure: ' + ' · '.join(r['hard']) + ' — the outputs are not complete.')
        return 3
    if (r['n_fail'] or r['missing_total']) and not allow_mismatch:
        if verbose:
            why = []
            if r['n_fail']:
                why.append(f"{r['n_fail']} preflight failures")
            if r['missing_total']:
                why.append(f"{r['missing_total']} MISSING frames")
            print(f"\n⛔ {' · '.join(why)} — the comparison was produced, but it is not complete/aligned. "
                  f"Fix the alignment (--ref-from/--ours-from/--duration/crop) or approve with --allow-mismatch.")
        return 2
    return 0


def main():
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    p = argparse.ArgumentParser(description='Source vs. replica — preflight, watch-through, blink, full-resolution frames')
    p.add_argument('ref'); p.add_argument('ours')
    p.add_argument('--out')
    p.add_argument('--ref-from', type=float, default=0.0, help='start time IN THE SOURCE')
    p.add_argument('--ours-from', type=float, default=0.0, help='start time IN OUR FILE (for a shot rendered on its own)')
    p.add_argument('--duration', type=float, help='window length; default = the maximum of both sides')
    p.add_argument('--ref-crop', help='W:H:X:Y in the source')
    p.add_argument('--ours-crop', help='W:H:X:Y in ours')
    p.add_argument('--every', type=float, default=0.1, help='spacing of the downscaled sheet')
    p.add_argument('--width', type=int, default=360, help='column width in the video')
    p.add_argument('--metric-width', type=int, default=720, help='measuring width (the difference is measured here)')
    p.add_argument('--at', type=lambda s: [float(x) for x in s.split(',')], help='source times for hires')
    p.add_argument('--hires', type=int, default=3, help='how many outlier moments to extract at full resolution')
    p.add_argument('--ref-frame', type=int, default=None,
                   help='frame index in the source (exact; overrides --ref-from)')
    p.add_argument('--ours-frame', type=int, default=None,
                   help='frame index in the replica (exact; overrides --ours-from)')
    p.add_argument('--frames', type=int, default=None,
                   help='window length in frames (overrides --duration)')
    p.add_argument('--allow-mismatch', action='store_true', help='a preflight mismatch will not return an error code')
    a = p.parse_args()
    r = run_compare(a)
    print(r['text'])
    print(final_message(r))
    sys.exit(exit_code(r, a.allow_mismatch, verbose=True))


if __name__ == '__main__':
    main()
