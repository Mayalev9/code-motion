#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deliver_gate.py — the delivery gate: checks THE MP4 FILE THAT WILL BE DELIVERED, not the scene.

═══ Why it exists ═══
`gate.mjs` checks the engine (negative time, determinism, orientation) — not a whole film.
`replicate_gate.py` compares to the source — it does not check that the file itself is fit for delivery.
A contact sheet does not reveal a short freeze, black at the end, a missing soundtrack or a colour that shifted in encoding.
This gate checks what can be measured on the file, and prints what ONLY WATCHING can check.

═══ Usage ═══
    python3 deliver_gate.py OUT.mp4 --audio yes|no [--duration S] [--fps N] [--size WxH]
                            [--hold A-B ...] [--hex '#rrggbb@x,y@t' ...] [--checklist FILE]
    python3 deliver_gate.py --selftest

  --audio      **Required.** An explicit decision whether the film should be heard. yes ⇒ a channel exists, not silent,
               as long as the video. no ⇒ a warning if there is a channel.
  --hold A-B   an intended hold (seconds). Every freeze ≥0.5s that was not declared ⇒ FAIL.
  --hex        a colour measured on the canvas, checked again AFTER yuv420p. x,y in fractions 0..1, t in seconds.

═══ What is checked ═══
  D1 file     h264 · yuv420p · even dimensions · constant rate · expected length/rate/size · [WARN] faststart
  D2 audio    per --audio: present · silence · length vs the video · peak and loudness (reported)
  D3 freeze   freezedetect — every freeze not declared with --hold
  D4 black    black frames at the start or the end
  D5 ending   [WARN] the film ends mid-motion — no moment to take it in
  D6 colour   --hex after encoding

⚠️ PASS here = the file is technically sound. It is NOT a delivery sign-off: the watch-list at the end of the output
   (legibility · margins · pacing · message · sync) is checked only by watching THIS MP4, from start to finish.
"""

import sys, os, re, json, shutil, subprocess, tempfile, argparse

FREEZE_MIN = 0.5      # seconds — a freeze shorter than this is not perceived as "stuck"
FREEZE_NOISE = 0.003  # freezedetect noise threshold (grain/compression do not count as motion)
HOLD_TOL = 0.15       # tolerance between --hold and the measured freeze
DUR_TOL = 0.10
AUDIO_SILENT_DB = -45.0
AUDIO_TP_WARN = -1.0
HEX_TOL = 8           # per channel — yuv420p+crf17 shifts a flat area by 1–4 levels
END_WIN = 0.5
END_MOTION = 1.0      # mean frame difference (0..255) in the last half second

# ── D3 · source-matched hold ──────────────────────────────────────────────
# Encoding noise is not motion. Measured on a real reference in four corners
#    that are certainly static: the frame difference there is 0.017–0.349, while a render from code
#    gives 0.0004–0.0008 — 33 to 613 times less. So a section that "moves" in the source may
#    be completely static in content, with the whole difference being compression and grain.
# ⇒ `--ref` checks, for every freeze found, whether THE SOURCE IS AT REST THERE TOO after
#    removing noise (a soft blur before the difference: uncorrelated noise disappears, structural motion survives).
#    Such a freeze is a SOURCE-MATCHED HOLD and passes without a manual `--hold`.
# ⛔ This is NOT permission to freeze: if the source does move there, the gate fails.
# The first threshold was tuned on one clip only — and failed a cross-check. 13
#    synthetic clips (1px shift · slow gradient · blurred object · dim image ·
#    noise at crf 20/28/30/35) showed that `motion(σ=3) < 0.35` classifies BACKWARDS:
#    "static dim with noise" gave 0.534 and "1px shift" gave 0.125.
# The difference is not in size but in BEHAVIOUR UNDER BLUR: uncorrelated pixel noise
#    disappears as sigma grows, and object motion survives. ⇒ two conditions:
#      `motion(σ=10) ≥ REF_FLOOR`  AND  `motion(σ=10)/motion(σ=3) ≥ REF_RATIO`
#    measured on the same 13 cases: ratio when static 0.00–0.14 · when moving 0.28–0.99.
REF_BLUR_LO = 3       # soft blur  — keeps noise
REF_BLUR_HI = 10      # heavy blur — removes noise, keeps structural motion
REF_FLOOR = 0.10      # below this there is no motion at all
REF_RATIO = 0.20     # survives heavy blur ⇒ real motion
MATCH_RATIO = 0.70   # our motion vs the source — less than this = we are really frozen

# ── profiles ──────────────────────────────────────────────────────────────
# Master and delivery are not the same file and not the same test. H.264 in yuv420p is
#    a delivery requirement (phone players, social networks) and INVALID for a master: 8-bit and 4:2:0 chroma
#    subsampling are lossy. FFV1/ProRes in 4:4:4 or RGB are a master requirement and INVALID
#    for delivery. ⛔ The pair is symmetric: the master profile on h264 must fail, and the delivery profile
#    on ffv1 must fail. Without both directions, `--profile` would be an escape hatch.
MASTER_CODECS = ('ffv1', 'prores', 'v210', 'utvideo', 'ffvhuff', 'png', 'rawvideo')
MASTER_PIX_OK = ('gbr', 'bgr', 'rgb', '444', '422p10', '422p12')


def need_tools():
    for t in ('ffmpeg', 'ffprobe'):
        if not shutil.which(t):
            sys.exit(f'{t} missing')


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'ffprobe failed on {path}:\n{r.stderr[:400]}')
    return json.loads(r.stdout)


def ff_stderr(args):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *args],
                          capture_output=True, text=True).stderr


def rate(s):
    n, d = s.split('/')
    return float(n) / float(d) if float(d) else 0.0


def faststart(path):
    """moov before mdat ⇒ the player starts before the whole file has downloaded."""
    with open(path, 'rb') as f:
        while True:
            h = f.read(8)
            if len(h) < 8:
                return None
            size = int.from_bytes(h[:4], 'big'); kind = h[4:8]
            if kind == b'moov':
                return True
            if kind == b'mdat':
                return False
            if size == 1:
                size = int.from_bytes(f.read(8), 'big'); f.seek(size - 16, 1)
            elif size < 8:
                return None
            else:
                f.seek(size - 8, 1)


def spans(text, key):
    """freezedetect/blackdetect → [(start, end)]."""
    if key == 'freeze':
        st = [float(x) for x in re.findall(r'freeze_start:\s*([\d.]+)', text)]
        en = [float(x) for x in re.findall(r'freeze_end:\s*([\d.]+)', text)]
        return [(s, en[i] if i < len(en) else None) for i, s in enumerate(st)]
    return [(float(a), float(b)) for a, b in
            re.findall(r'black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)', text)]


def sample_rgb(path, t, x, y, w, h):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.4f}', '-i', path, '-frames:v', '1',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    if len(raw) < w * h * 3:
        return None
    cx, cy = min(w - 3, max(2, int(x * w))), min(h - 3, max(2, int(y * h)))
    acc = [0, 0, 0]
    for yy in range(cy - 2, cy + 3):
        for xx in range(cx - 2, cx + 3):
            o = (yy * w + xx) * 3
            for k in range(3):
                acc[k] += raw[o + k]
    return tuple(round(v / 25) for v in acc)


def decode_all_video(path):
    """Decodes ALL of the video with `-xerror` and returns (rc, frame count, stderr).
    ⛔ Without `-xerror` ffmpeg decodes "as much as it can" from a broken file and returns rc=0."""
    w = 64
    r = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', path,
                        '-vf', f'scale={w}:-2', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                       capture_output=True)
    sz = probe_size_cache.get(path)
    if not sz:
        return r.returncode, None, r.stderr.decode('utf-8', 'replace')
    h = int(round(sz[1] * w / sz[0] / 2)) * 2
    return r.returncode, len(r.stdout) // (w * h), r.stderr.decode('utf-8', 'replace')


def decode_all_audio(path):
    """Decodes ALL of the audio with `-xerror` and returns (rc, sample count, stderr)."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', path, '-vn',
                        '-f', 's16le', '-ac', '1', '-ar', '48000', '-'],
                       capture_output=True)
    return r.returncode, len(r.stdout) // 2, r.stderr.decode('utf-8', 'replace')


def integrity(path, v, info, has_audio, expect_frames=None):
    """D0 · FILE INTEGRITY — does it decode from start to finish.

    A file physically cut at 45% once passed 5/5 and was even reported as ending "at rest". The causes:
       ffmpeg's exit code was thrown away · decoding ran without `-xerror` · `end_motion`
       returned 0.0 when frames were missing at the end (and 0 read as "frozen", not as a failure) · and D1
       checked mainly the HEADER, not the decoding.
    ⛔ A failure here is HARD: the other gates are not reported at all, because measuring a partial
       stream is not measuring.
    """
    prob = []
    fps = rate(v['r_frame_rate'])
    vdur = float(v.get('duration') or info['format']['duration'])
    # `round(fps * vdur)` is not a "declaration" — it is a guess, and it lied.
    #    MKV holds no frame table ⇒ `nb_frames=N/A`, and `duration` is taken
    #    from the container — where the audio (18.09s) is longer than the video (18.03s) ⇒ the guess
    #    came out 543 vs 541 that decode, and the gate reported "the stream was cut" on a complete
    #    master whose losslessness was proven with framemd5.
    # ⛔ And do not count packets instead: truncation DELETES packets, so self-counting
    #    can never detect it. A declaration must come from a source that IS NOT THE DATA:
    #    the container's table, or the operator's declaration (`--duration`/`--fps`).
    nb = v.get('nb_frames')
    if nb and str(nb).isdigit():
        declared, dsrc = int(nb), 'container'
    elif expect_frames:
        declared, dsrc = int(expect_frames), 'operator declaration'
    else:
        declared, dsrc = None, None
    rc, n, err = decode_all_video(path)
    first = err.strip().splitlines()[0][:110] if err.strip() else ''
    if rc != 0:
        prob.append(f'video decoding failed (rc={rc}) {first}')
    if n is not None and declared and n < declared:
        prob.append(f'decoded {n} frames out of {declared} ({dsrc}) — **the stream was cut**')
    if declared is None:
        # ⚠️ NOT "passed" — there is simply nothing to check against. Said explicitly.
        prob.append('⚠️ no declared frame count (not in the container and not via --duration/--fps) '
                    '⇒ **truncation not checked**')
    det = (f'video: {n}/{declared} frames ({dsrc}) · rc={rc}' if declared
           else f'video: {n} frames · rc={rc}')
    if has_audio:
        arc, ns, aerr = decode_all_audio(path)
        afirst = aerr.strip().splitlines()[0][:110] if aerr.strip() else ''
        adur = ns / 48000 if ns else 0.0
        if arc != 0:
            prob.append(f'audio decoding failed (rc={arc}) {afirst}')
        # ⚠️ AUDIO LENGTH is not checked here — a file whose audio is shorter than the video is
        #    fine as far as decoding goes, and that is exactly D2's question. D0 checks ONLY whether
        #    the stream decodes from start to finish.
        det += f' · audio: {adur:.2f}s · rc={arc}'
    return dict(id='D0', name='file integrity', ok=not prob,
                detail=det + (' · ' + ' · '.join(prob) if prob else ''))


def structured_motion(path, t0, t1, blur=REF_BLUR_LO):
    """Structural motion over a time range: frame difference AFTER A SOFT BLUR.
    The blur is the separation: encoding noise is uncorrelated between pixels and disappears in it,
       and object motion survives. Without it every "motion" measurement on a compressed source
       mostly measures the codec.
    ⛔ Returns None if fewer than two frames were read — "no data" is not zero."""
    import numpy as np
    w, h = 320, 180
    vf = (f'trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS,'
          f'scale={w}:{h},gblur=sigma={blur}')
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf,
                        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                       capture_output=True)
    n = w * h
    fr = [np.frombuffer(p.stdout[i * n:(i + 1) * n], np.uint8).astype(float).reshape(h, w)
          for i in range(len(p.stdout) // n)]
    if len(fr) < 2:
        return None
    return float(np.mean([np.abs(fr[i] - fr[i - 1]).mean() for i in range(1, len(fr))]))


TP_TOL = 0.2          # dB — measurement tolerance when comparing peak with the source


def true_peak(path):
    """True peak in dBTP, or None when there is no audio / no measurement."""
    st = ff_stderr(['-i', path, '-map', '0:a:0', '-af',
                    'aresample=48000,ebur128=peak=true', '-f', 'null', '-'])
    tp = re.findall(r'Peak:\s*(-?\+?[\d.]+|-inf) dBFS', st)
    if not tp or tp[-1] == '-inf':
        return None
    try:
        return float(tp[-1])
    except ValueError:
        return None


def ref_moves(path, t0, t1):
    """Returns (moving?, description). ⛔ Returns (None, reason) when there is not enough data."""
    lo = structured_motion(path, t0, t1, REF_BLUR_LO)
    hi = structured_motion(path, t0, t1, REF_BLUR_HI)
    if lo is None or hi is None:
        return None, 'not enough frames'
    if lo <= 1e-6:
        return False, f'{hi:.2f}/{lo:.2f}'
    ratio = hi / lo
    moving = hi >= REF_FLOOR and ratio >= REF_RATIO
    return moving, f'{hi:.2f} · survives blur {ratio:.2f}'


def motion_matches_ref(path, ref, t0, t1):
    """Does OUR MOTION in the section match the source's motion?

    Why this is needed, and why `ref_moves` alone is not enough: `freezedetect`
       flags a section by an ABSOLUTE threshold (`n=FREEZE_NOISE`). In a section where the film moves
       very slowly — text starting to appear, a slow fade — both files move almost identically, but
       ours happens to fall below the threshold and `ref_moves` marks the source as "moving". The result is
       a red flag on A GAP THAT DOES NOT EXIST: measured on a real clip, OUR motion
       (0.170) was larger than the SOURCE's (0.140).
    ⇒ The right question is not "is the source static" but "do we move like the source".
    ⛔ There is no threshold tuned to pass here: the negative control is a COMPLETELY FROZEN file against
       a moving source — the ratio is 0 there and the gate must fail. Injected in the selftest.
    """
    om = structured_motion(path, t0, t1, REF_BLUR_HI)
    rm = structured_motion(ref, t0, t1, REF_BLUR_HI)
    if om is None or rm is None or rm <= 1e-6:
        return None, 'not enough data'
    r = om / rm
    return r >= MATCH_RATIO, f'ours {om:.2f} vs source {rm:.2f} · ratio {r:.2f}'


def end_motion(path, dur):
    """Mean frame difference in the last half second, at 160 pixels wide."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, dur - END_WIN):.4f}', '-i', path,
                          '-vf', 'scale=160:-2,format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True).stdout
    p = probe_size_cache.get(path)
    if not p:
        return 0.0
    w, h = 160, int(round(p[1] * 160 / p[0] / 2)) * 2
    n = len(raw) // (w * h)
    if n < 2:
        # Previously 0.0 was returned — and that read as "frozen", i.e. a VALID ending.
        #    Missing frames are not a measurement; None is returned and the checker reports it.
        return None
    tot = 0.0
    for i in range(1, n):
        a = raw[(i - 1) * w * h:i * w * h]; b = raw[i * w * h:(i + 1) * w * h]
        tot += sum(abs(a[j] - b[j]) for j in range(0, w * h, 7)) / len(range(0, w * h, 7))
    return tot / (n - 1)


probe_size_cache = {}


def check(path, audio, duration=None, fps=None, size=None, holds=(), hexes=(),
          freeze_min=FREEZE_MIN, ref=None, profile='delivery'):
    if not os.path.isfile(path):
        sys.exit(f'no such file: {path}')
    info = probe(path)
    vs = [s for s in info['streams'] if s['codec_type'] == 'video']
    as_ = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if not vs:
        return [dict(id='D1', name='file', ok=False, detail='no video stream')]
    v = vs[0]
    W, H = int(v['width']), int(v['height'])
    probe_size_cache[path] = (W, H)
    vdur = float(v.get('duration') or info['format']['duration'])
    # ⛔ D0 FIRST. If the file does not decode completely, every other measurement is
    #    a measurement on a partial stream — so it is NOT REPORTED AT ALL.
    exp_fr = (int(round(duration * fps)) if duration and fps else None)
    d0 = integrity(path, v, info, bool(as_), expect_frames=exp_fr)
    if not d0['ok']:
        return [d0]
    g = [d0]

    # D1 · file
    prob = []
    pf = v.get('pix_fmt') or ''
    if profile == 'master':
        if not any(v['codec_name'].startswith(c) for c in MASTER_CODECS):
            prob.append(f"codec {v['codec_name']} — not lossless "
                        f"(expected one of {'/'.join(MASTER_CODECS)})")
        if not any(k in pf for k in MASTER_PIX_OK):
            prob.append(f'pix_fmt {pf} — chroma subsampling in a master is lossy '
                        '(expected RGB or 4:4:4)')
    else:
        if v['codec_name'] != 'h264':
            prob.append(f"codec {v['codec_name']} (expected h264)")
        if pf != 'yuv420p':
            prob.append(f'pix_fmt {pf} (expected yuv420p — phone players and social networks)')
    if W % 2 or H % 2:
        prob.append(f'odd dimensions {W}×{H}')
    rf, af = rate(v['r_frame_rate']), rate(v.get('avg_frame_rate', '0/1'))
    if af and abs(rf - af) > 0.01:
        prob.append(f'variable frame rate (r {rf:.3f} · avg {af:.3f})')
    # faststart = a warning only: networks re-encode on upload; it matters only for playback from the web
    fs_warn = faststart(path) is False
    if duration is not None and abs(vdur - duration) > DUR_TOL:
        prob.append(f'length {vdur:.2f}s (expected {duration:g})')
    if fps is not None and abs(rf - fps) > 0.01:
        prob.append(f'rate {rf:g} (expected {fps:g})')
    if size is not None and (W, H) != size:
        prob.append(f'size {W}×{H} (expected {size[0]}×{size[1]})')
    g.append(dict(id='D1', name='file', ok=not prob, warn=fs_warn,
                  detail=f"{v['codec_name']} · {v.get('pix_fmt')} · {W}×{H} · {rf:g}fps · {vdur:.2f}s" +
                         (' · ' + ' · '.join(prob) if prob else '') +
                         (' · [WARN] no faststart (moov after mdat)' if fs_warn else '')))

    # D2 · audio — by explicit decision
    if audio == 'yes':
        if not as_:
            g.append(dict(id='D2', name='audio', ok=False, detail='no audio channel — and --audio yes was declared'))
        else:
            a = as_[0]
            adur = float(a.get('duration') or vdur)
            st = ff_stderr(['-i', path, '-map', '0:a:0', '-af', 'volumedetect,ebur128=peak=true', '-f', 'null', '-'])
            mv = re.search(r'max_volume:\s*(-?[\d.]+|-inf) dB', st)
            maxv = float(mv.group(1)) if mv and mv.group(1) != '-inf' else -999.0
            li = re.findall(r'I:\s*(-?[\d.]+) LUFS', st)
            tp = re.findall(r'Peak:\s*(-?[\d.]+|-inf) dBFS', st)
            lufs = float(li[-1]) if li else None
            peak = float(tp[-1]) if tp and tp[-1] != '-inf' else None
            prob = []
            if maxv < AUDIO_SILENT_DB:
                prob.append(f'silent (peak {maxv:.1f}dB)')
            if abs(adur - vdur) > DUR_TOL:
                prob.append(f'audio length {adur:.2f} vs video {vdur:.2f}')
            warn = peak is not None and peak > AUDIO_TP_WARN
            extra = ''
            # ⛔ NOT `and warn`. The rule "the master is not louder than the source" does not depend
            #    on the delivery threshold: a master quieter than −1 but louder than the source once passed here silently —
            #    caught by D2n (peak −5.7 vs source −17.7, with no warning).
            if profile == 'master' and ref:
                # In a master, −1 dBTP is not a rule — the master passes the source audio
                #    through as it is (a real source measured +0.2 dBTP).
                #    ⛔ But not a blanket exemption: a master LOUDER THAN THE SOURCE is a failure.
                rp = true_peak(ref)
                if rp is None:
                    prob.append('no source peak to measure against')
                elif peak > rp + TP_TOL:
                    prob.append(f'peak {peak:.1f} **above** the source peak {rp:.1f}dBTP')
                else:
                    warn = False
                    extra = f' · source-matched (source {rp:.1f}dBTP · −1 is a delivery rule)'
            g.append(dict(id='D2', name='audio', ok=not prob, warn=warn,
                          detail=f"{a['codec_name']} · {adur:.2f}s · peak {maxv:.1f}dB" +
                                 (f' · {lufs:.1f} LUFS' if lufs is not None else '') +
                                 (f' · true-peak {peak:.1f}dBTP' + (' [WARN] above -1' if warn else '')
                                  if peak is not None else '') +
                                 extra +
                                 (' · ' + ' · '.join(prob) if prob else '')))
    else:
        g.append(dict(id='D2', name='audio', ok=True, warn=bool(as_),
                      detail='declared silent' + (' · [WARN] the file has an audio channel' if as_ else ' · no audio channel')))

    # D3 · freeze
    st = ff_stderr(['-i', path, '-map', '0:v:0', '-vf',
                    f'freezedetect=n={FREEZE_NOISE}:d={freeze_min}', '-f', 'null', '-'])
    fz = [(s, e if e is not None else vdur) for s, e in spans(st, 'freeze')]
    undeclared, declared, matched = [], [], []
    for s, e in fz:
        cov = any(a - HOLD_TOL <= s and e <= b + HOLD_TOL for a, b in holds)
        if cov:
            declared.append(f'{s:.2f}–{e:.2f}')
            continue
        # ⇒ a SOURCE-MATCHED hold: the source is at rest there too, after removing noise.
        if ref:
            mv, why = ref_moves(ref, s, e)
            if mv is False:
                matched.append(f'{s:.2f}–{e:.2f} ({why})')
                continue
            if mv is True:
                # the source moves — but do WE move less than it?
                ok_m, why_m = motion_matches_ref(path, ref, s, e)
                if ok_m:
                    matched.append(f'{s:.2f}–{e:.2f} (slow motion · {why_m})')
                else:
                    undeclared.append(f'{s:.2f}–{e:.2f} (the source moves {why}'
                                      + (f' · {why_m}' if why_m else '') + ')')
                continue
        undeclared.append(f'{s:.2f}–{e:.2f}')
    g.append(dict(id='D3', name='freeze', ok=not undeclared,
                  detail=(f'{len(fz)} sections ≥{freeze_min:g}s' if fz else 'no freeze') +
                         (f' · declared: {", ".join(declared)}' if declared else '') +
                         (f' · source-matched: {", ".join(matched)}' if matched else '') +
                         (f' · undeclared freeze: {", ".join(undeclared)} (an intended hold? --hold A-B)'
                          if undeclared else '')))

    # D4 · black at the edges
    st = ff_stderr(['-i', path, '-map', '0:v:0', '-vf', 'blackdetect=d=0.05:pix_th=0.10', '-f', 'null', '-'])
    edge = [(s, e) for s, e in spans(st, 'black') if s < 0.05 or e > vdur - 0.1]
    g.append(dict(id='D4', name='black at the edges', ok=not edge,
                  detail='none' if not edge else
                  'black at ' + ', '.join(f'{s:.2f}–{e:.2f}' for s, e in edge) +
                  (' (at the end)' if any(e > vdur - 0.1 for _, e in edge) else ' (at the start)')))

    # D5 · the ending
    em = end_motion(path, vdur)
    if em is None:
        # ⛔ no frames to read at the end — that is a FAILURE, not "at rest".
        g.append(dict(id='D5', name='ending', ok=False,
                      detail='cannot read the last half second — fewer than two frames'))
    else:
        g.append(dict(id='D5', name='ending', ok=True, warn=em > END_MOTION,
                      detail=f'motion in the last half second {em:.2f}' +
                             (' · [WARN] ends mid-motion — no moment to take it in?' if em > END_MOTION else ' · at rest')))

    # D6 · colour after encoding
    if hexes:
        bad, got = [], []
        for hx, x, y, t in hexes:
            want = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
            m = sample_rgb(path, t, x, y, W, H)
            if m is None:
                bad.append(f'{hx}@{t:g}: frame not read'); continue
            d = max(abs(a - b) for a, b in zip(want, m))
            s = f"{hx}→#{''.join(f'{c:02x}' for c in m)} (Δ{d})"
            (bad if d > HEX_TOL else got).append(s)
        g.append(dict(id='D6', name='colour after encoding', ok=not bad,
                      detail=' · '.join(got + bad) + (f' · exceeds ±{HEX_TOL}' if bad else '')))
    return g


CHECKLIST = """\
## Watch-list — only an eye can check this (the delivery gate cannot)
File: {path}

- [ ] I watched **this file** (not the player, not the contact sheet) from start to finish, at normal speed, **with sound**
- [ ] at phone size (a window ~390px wide, or on the phone itself)
- [ ] every text can be read while it is on screen, at this size, without pausing
- [ ] nothing important in the margins — not cut off, not under the Instagram/TikTok/Shorts UI (top ~12% · bottom ~20%)
- [ ] no unplanned jump, flicker or cut; smooth transitions
- [ ] the ending gives a moment to take it in — not cut off, not dragging
- [ ] sound: in sync with the events, no clipping, no unintended silence (or: silence was decided ⇒ checked without sound)
- [ ] without sound: does the message still come through? are captions needed?
- [ ] **the message:** someone who watches once understands what we meant to say; the pacing serves the story
- [ ] against the brief: aspect ratio · length · language · format — as agreed
"""


def report(gates, path, checklist=None):
    print(f'\n╔═══ delivery gate · {os.path.basename(path)} ═══')
    npass = 0
    for g in gates:
        tag = ('⚠️ WARN' if g.get('warn') else '✅ PASS') if g['ok'] else '❌ FAIL'
        npass += g['ok']
        print(f"║ {tag}  {g['id']} · {g['name']}")
        print(f"║        {g['detail']}")
    ok = all(g['ok'] for g in gates)
    print(f'╚═══ {npass}/{len(gates)} passed')
    print('\n' + ('The mechanical checks passed. **Delivery depends on the watch-list:**' if ok else
                  'The mechanical checks failed — fix before watching.') + '\n')
    text = CHECKLIST.format(path=path)
    print(text)
    if checklist:
        with open(checklist, 'w') as f:
            f.write(f'# Delivery · {os.path.basename(path)}\n\n## Mechanical\n')
            for g in gates:
                f.write(f"- {'FAIL' if not g['ok'] else 'WARN' if g.get('warn') else 'PASS'} "
                        f"{g['id']} {g['name']}: {g['detail']}\n")
            f.write('\n' + text)
        print(f'wrote {checklist}')
    return ok


# ─────────────────────────── selftest ───────────────────────────

def selftest():
    need_tools()
    print('═══ selftest — synthetic files; every failure must fail for the right reason ═══')
    d = tempfile.mkdtemp(prefix='delgate_')
    cases = []
    V = 'testsrc2=s=320x568:r=30:d={d}'

    def mk(name, vsrc, asrc=None, vf=None, pix='yuv420p', extra=()):
        p = os.path.join(d, name + '.mp4')
        a = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', vsrc]
        if asrc:
            a += ['-f', 'lavfi', '-i', asrc]
        if vf:
            a += ['-vf', vf]
        a += ['-c:v', 'libx264', '-pix_fmt', pix, '-movflags', '+faststart', *extra]
        if asrc:
            a += ['-c:a', 'aac']
        subprocess.run(a + [p], check=True)
        return p

    def gate(gs, gid):
        return next(x for x in gs if x['id'] == gid)

    def expect(name, gs, gid, ok, why=''):
        x = gate(gs, gid)
        cases.append((name, x['ok'] == ok and why in x['detail'], x['detail']))

    try:
        good = mk('good', V.format(d=3), 'sine=f=440:d=3')
        gs = check(good, 'yes', duration=3, fps=30, size=(320, 568))
        cases.append(('0 · positive control: a sound file passes D0',
                      gate(gs, 'D0')['ok'], gate(gs, 'D0')['detail']))

        # ══ A physically cut file once passed 5/5 and was reported as ending "at rest" ══
        #    the exit code was thrown away · no `-xerror` · `end_motion` returned 0.0 on
        #    missing frames · and D1 checked the header, not the decoding.
        cut = os.path.join(d, 'cut.mp4')
        shutil.copyfile(good, cut)
        with open(cut, 'r+b') as fh:
            fh.truncate(int(os.path.getsize(cut) * 0.55))
        gcut = check(cut, 'yes')
        cases.append(('0b · truncated file → D0 fails', not gate(gcut, 'D0')['ok'],
                      gate(gcut, 'D0')['detail']))
        cases.append(('0c · and the other gates are NOT REPORTED (measuring a partial stream is not measuring)',
                      len(gcut) == 1 and gcut[0]['id'] == 'D0',
                      f"{[x['id'] for x in gcut]}"))
        cases.append(('0d · the report returns a failure', not all(x['ok'] for x in gcut), 'passed'))
        # the two claims separately: rc and frame count — each must catch on its own
        rc_, n_, _ = decode_all_video(cut)
        cases.append(('0e · the decoder returns rc≠0 on the truncated file', rc_ != 0, f'rc={rc_}'))
        cases.append(('0f · fewer frames decoded than declared', (n_ or 0) < 90, f'n={n_}'))
        # 0g · `end_motion` on a VALID one-frame file: nothing to compare ⇒ None.
        #      Previously 0.0 was returned, which read as "at rest" — i.e. a valid ending.
        one = os.path.join(d, 'one.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
                        '-i', 'color=c=red:s=320x568:d=0.04:r=30', '-frames:v', '1',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', one], check=True)
        probe_size_cache[one] = (320, 568)
        cases.append(('0g · end_motion → None when there are not two frames (not 0.0)',
                      end_motion(one, 0.04) is None, f'{end_motion(one, 0.04)}'))
        g_one = check(one, 'no')
        cases.append(('0h · and in the gate: D5 fails and does not report "at rest"',
                      not gate(g_one, 'D5')['ok'] if any(x['id'] == 'D5' for x in g_one) else True,
                      f"{[x['id'] for x in g_one]}"))

        # 0i · THE FRAME-COUNT CHECK ON ITS OWN. Inject a decoder that returns rc=0 but
        #      fewer frames than declared — so the claim does not rely on the rc.
        _real_dav = decode_all_video
        globals()['decode_all_video'] = lambda pth: (0, 5, '')
        try:
            g_short = check(good, 'yes')
            short_ok = (not gate(g_short, 'D0')['ok']
                        and 'the stream was cut' in gate(g_short, 'D0')['detail'])
            short_det = gate(g_short, 'D0')['detail']
        finally:
            globals()['decode_all_video'] = _real_dav
        cases.append(('0i · rc=0 but fewer frames than declared → D0 fails', short_ok, short_det))
        cases.append(('1 · control: a sound file with audio → D1–D4 pass',
                      all(x['ok'] for x in gs), ' · '.join(f"{x['id']}:{x['detail']}" for x in gs if not x['ok'])))
        expect('2 · no audio channel but --audio yes → D2', check(mk('noaud', V.format(d=3)), 'yes'),
               'D2', False, 'no audio channel')
        expect('3 · silent audio channel → D2', check(mk('silent', V.format(d=3), 'anullsrc=r=48000:cl=stereo', extra=['-t', '3']), 'yes'),
               'D2', False, 'silent')
        expect('4 · audio shorter than the video → D2', check(mk('short', V.format(d=3), 'sine=f=440:d=1.5'), 'yes'),
               'D2', False, 'audio length')
        fz = mk('freeze', V.format(d=1.5), vf='tpad=stop_mode=clone:stop_duration=1.5')
        expect('5 · undeclared 1.5s freeze → D3', check(fz, 'no'), 'D3', False, 'undeclared')
        expect('6 · control: the same freeze declared with --hold → D3 passes', check(fz, 'no', holds=[(1.5, 3.0)]), 'D3', True, 'declared')
        expect('7 · black at the end → D4', check(mk('black', V.format(d=2), vf='tpad=stop_mode=add:stop_duration=1:color=black'), 'no'),
               'D4', False, 'at the end')
        expect('8 · yuv444p → D1', check(mk('p444', V.format(d=1), pix='yuv444p', extra=['-profile:v', 'high444']), 'no'),
               'D1', False, 'pix_fmt')
        expect('9 · different expected length → D1', check(good, 'yes', duration=5), 'D1', False, 'expected 5')
        solid = mk('solid', 'color=c=0xc8f24a:s=320x568:r=30:d=1')
        expect('10 · control: correct HEX after encoding → D6 passes', check(solid, 'no', hexes=[('#c8f24a', .5, .5, .5)]), 'D6', True)
        expect('11 · wrong HEX → D6', check(solid, 'no', hexes=[('#4a7af2', .5, .5, .5)]), 'D6', False, 'exceeds')
        expect('12 · control: --audio no on a silent file → D2 passes', check(mk('mute', V.format(d=1)), 'no'), 'D2', True, 'no audio channel')
        x = gate(check(good, 'yes'), 'D5')
        cases.append(('13 · ends mid-motion → D5 warns', bool(x.get('warn')), x['detail']))
        x = gate(check(fz, 'no', holds=[(1.5, 3.0)]), 'D5')
        cases.append(('14 · control: ends on a hold → D5 does not warn', not x.get('warn'), x['detail']))
        # ── D3 · source-matched hold ────────────────────────────────────
        # ⛔ A pair: a STATIC-WITH-NOISE source must pass · a MOVING source must fail.
        import numpy as np

        def synth(path, mover, noise):
            fr, rng = [], np.random.default_rng(3)
            for k in range(45):
                im = np.full((180, 320), 120, np.uint8)
                if mover:
                    x = 40 + (k * 4) % 200
                    im[:, x:x + 20] = 220
                if noise:
                    # ⚠️ ±6, not ±14: noise stronger than reality would make a test
                    #    that fails on a valid threshold. The norm was measured on a real source.
                    im = np.clip(im.astype(int) + rng.integers(-6, 7, im.shape),
                                 0, 255).astype(np.uint8)
                fr.append(im)
            pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo',
                                   '-pix_fmt', 'gray', '-s', '320x180', '-framerate', '30',
                                   '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                                   '-crf', '20', path], stdin=subprocess.PIPE)
            pr.communicate(b''.join(f.tobytes() for f in fr))
            return path

        still = synth(os.path.join(d, 'still.mp4'), False, False)
        rnoise = synth(os.path.join(d, 'rn.mp4'), False, True)
        rmove = synth(os.path.join(d, 'rm.mp4'), True, False)
        mn = structured_motion(rnoise, 0.1, 1.4)
        mm = structured_motion(rmove, 0.1, 1.4)
        cases.append(('D3a · structural motion separates noise from motion',
                      mn is not None and mm is not None and mm > mn * 3,
                      f'noise {mn:.3f} · motion {mm:.3f}'))
        x = gate(check(still, 'no', ref=rnoise), 'D3')
        cases.append(('D3b · static-with-noise source ⇒ source-matched hold', x['ok'], x['detail']))
        cases.append(('D3c · the report says "source-matched"', 'source-matched' in x['detail'], x['detail']))
        x = gate(check(still, 'no', ref=rmove), 'D3')
        cases.append(('D3d · ⛔ moving source ⇒ the gate fails', not x['ok'], x['detail']))
        cases.append(('D3e · and the report says how much the source moves', 'the source moves' in x['detail'], x['detail']))
        # ── D0 · a container that does not declare a frame count (MKV/FFV1) ─────
        # The gate once reported "the stream was cut" on a COMPLETE master because it derived 543 from the
        #    container length. ⛔ A triple: complete→passes · truncated→fails · no declaration→says
        #    it was not checked (and not "passed").
        mkv = os.path.join(d, 'm.mkv')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', good,
                        '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'gbrp',
                        '-g', '1', '-c:a', 'flac', mkv], check=True)
        nbf = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_frames', '-of',
                              'default=nw=1:nk=1', mkv],
                             capture_output=True, text=True).stdout.strip()
        cases.append(('D0j · precondition: MKV indeed does not declare nb_frames',
                      not nbf.isdigit(), f'nb_frames={nbf!r}'))
        nfr = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                              '-count_packets', '-show_entries',
                              'stream=nb_read_packets', '-of',
                              'default=nw=1:nk=1', mkv],
                             capture_output=True, text=True).stdout.strip()
        nfr = int(nfr)
        x = gate(check(mkv, 'yes', duration=nfr / 30, fps=30), 'D0')
        cases.append(('D0k · complete MKV ⇒ D0 passes by the operator declaration',
                      x['ok'] and 'operator declaration' in x['detail'], x['detail']))
        x = gate(check(mkv, 'yes'), 'D0')
        cases.append(('D0l · MKV without a declaration ⇒ does NOT pass and says it was not checked',
                      (not x['ok']) and 'truncation not checked' in x['detail'], x['detail']))
        cut_mkv = os.path.join(d, 'cut.mkv')
        with open(mkv, 'rb') as f:
            blob = f.read()
        with open(cut_mkv, 'wb') as f:
            f.write(blob[:int(len(blob) * 0.55)])
        x = gate(check(cut_mkv, 'yes', duration=nfr / 30, fps=30), 'D0')
        cases.append(('D0m · ⛔ truncated MKV ⇒ D0 fails against the operator declaration',
                      not x['ok'], x['detail'][:150]))

        # ── D1/D2 · master profile ⇔ delivery profile ─────────────────────
        # ⛔ SYMMETRIC in both directions, otherwise `--profile` is an escape hatch.
        x = gate(check(mkv, 'yes', duration=nfr / 30, fps=30, profile='master'), 'D1')
        cases.append(('D1m · FFV1/RGB passes the master profile', x['ok'], x['detail']))
        x = gate(check(mkv, 'yes', duration=nfr / 30, fps=30, profile='delivery'), 'D1')
        cases.append(('D1n · ⛔ FFV1 fails the delivery profile', not x['ok'], x['detail']))
        x = gate(check(good, 'yes', profile='master'), 'D1')
        cases.append(('D1o · ⛔ h264/yuv420p fails the master profile', not x['ok'], x['detail']))
        x = gate(check(good, 'yes', profile='delivery'), 'D1')
        cases.append(('D1p · control: h264 passes the delivery profile', x['ok'], x['detail']))
        # D2 · in a master −1dBTP is not a rule, but "louder than the source" is
        loud = os.path.join(d, 'loud.mkv')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mkv, '-c:v', 'copy',
                        '-af', 'volume=12dB', '-c:a', 'flac', loud], check=True)
        x = gate(check(mkv, 'yes', duration=nfr / 30, fps=30, profile='master',
                       ref=mkv), 'D2')
        cases.append(('D2m · master at the source peak ⇒ passes, no warning',
                      x['ok'] and not x.get('warn'), x['detail']))
        x = gate(check(loud, 'yes', duration=nfr / 30, fps=30, profile='master',
                       ref=mkv), 'D2')
        cases.append(('D2n · ⛔ master louder than the source ⇒ fails',
                      not x['ok'] and 'above' in x['detail'], x['detail']))

        x = gate(check(still, 'no'), 'D3')
        cases.append(('D3f · without --ref the behaviour has not changed', not x['ok'], x['detail']))

        # ── D3 · SLOW motion in both files ────────────────────────────────
        # The measured bug: freezedetect flags by an absolute threshold, and in slow motion
        #    ours falls below the threshold while the source is just above it ⇒ a fake "gap".
        #    ⛔ The pair: matching motion must pass · weakened motion must fail.
        def slow(path, step, seed=7):
            fr, rng = [], np.random.default_rng(seed)
            for k in range(45):
                im = np.full((180, 320), 120, np.uint8)
                im[:, 60:140] = np.clip(140 + k * step, 0, 255)
                im = np.clip(im.astype(int) + rng.integers(-3, 4, im.shape),
                             0, 255).astype(np.uint8)
                fr.append(im)
            pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo',
                                   '-pix_fmt', 'gray', '-s', '320x180', '-framerate', '30',
                                   '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                                   '-crf', '20', path], stdin=subprocess.PIPE)
            pr.communicate(b''.join(f.tobytes() for f in fr))
            return path
        rslow = slow(os.path.join(d, 'rslow.mp4'), 0.9, 7)
        oslow = slow(os.path.join(d, 'oslow.mp4'), 0.9, 11)   # same motion, different noise
        oweak = slow(os.path.join(d, 'oweak.mp4'), 0.15, 11)  # same scene, motion ×0.17
        mv, why = ref_moves(rslow, 0.1, 1.4)
        cases.append(('D3h · precondition: the slow source is classified "moving"', mv is True, f'{mv} · {why}'))
        ok_m, why_m = motion_matches_ref(oslow, rslow, 0.1, 1.4)
        cases.append(('D3i · source-matched motion ⇒ not a gap', ok_m is True, why_m))
        ok_w, why_w = motion_matches_ref(oweak, rslow, 0.1, 1.4)
        cases.append(('D3j · ⛔ weakened motion against the same source ⇒ a gap', ok_w is False, why_w))
        ok_z, why_z = motion_matches_ref(still, rslow, 0.1, 1.4)
        cases.append(('D3k · ⛔ negative control: completely frozen ⇒ a gap', ok_z is False, why_z))
        _sm = structured_motion(still, 0.0, 0.01)
        cases.append(('D3g · section too short ⇒ None, not zero',
                      _sm is None, f'{_sm}'))

    finally:
        shutil.rmtree(d, ignore_errors=True)

    ok = True
    for name, passed, detail in cases:
        print(f"  {'✅' if passed else '❌'} {name}")
        if not passed:
            print(f'      ⟵ {detail}'); ok = False
    print(f"\n{'✅ selftest passed' if ok else '❌ selftest failed'} — {sum(1 for _, p, _ in cases if p)}/{len(cases)}")
    return ok


def parse_hold(s):
    try:
        a, b = (float(x) for x in s.split('-'))
        assert 0 <= a < b
        return a, b
    except Exception:
        raise argparse.ArgumentTypeError(f'--hold must be A-B in seconds: {s}')


def parse_hex(s):
    m = re.fullmatch(r'(#[0-9a-fA-F]{6})@([\d.]+),([\d.]+)@([\d.]+)', s)
    if not m:
        raise argparse.ArgumentTypeError(f"--hex must be '#rrggbb@x,y@t': {s}")
    return m.group(1).lower(), float(m.group(2)), float(m.group(3)), float(m.group(4))


def parse_size(s):
    m = re.fullmatch(r'(\d+)x(\d+)', s)
    if not m:
        raise argparse.ArgumentTypeError(f'--size must be WxH: {s}')
    return int(m.group(1)), int(m.group(2))


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    need_tools()
    p = argparse.ArgumentParser(description='The delivery gate on the final MP4')
    p.add_argument('video')
    p.add_argument('--audio', required=True, choices=['yes', 'no'], help='should the film be heard')
    p.add_argument('--duration', type=float)
    p.add_argument('--fps', type=float)
    p.add_argument('--size', type=parse_size)
    p.add_argument('--hold', action='append', type=parse_hold, default=[])
    p.add_argument('--ref', help='source to compare against — a freeze where the source is at rest too passes automatically as a "source-matched hold"')
    p.add_argument('--hex', action='append', type=parse_hex, default=[])
    p.add_argument('--freeze-min', type=float, default=FREEZE_MIN)
    p.add_argument('--checklist', help='markdown file for the results + the watch-list')
    p.add_argument('--profile', choices=['delivery', 'master'], default='delivery',
                   help='delivery = h264/yuv420p · master = lossless in RGB/4:4:4')
    a = p.parse_args()
    gates = check(a.video, a.audio, a.duration, a.fps, a.size, a.hold, a.hex,
                  a.freeze_min, ref=a.ref, profile=a.profile)
    sys.exit(0 if report(gates, a.video, a.checklist) else 1)
