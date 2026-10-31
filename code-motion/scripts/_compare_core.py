#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared core for `sbs.py` and `perframe.py` — probe · crop · preflight ·
stream decoding with an exit-code check · measurement signature.

Why one core: two tools that check "are these two files comparable at all"
   in two different ways are two standards. Here it is checked once.

⛔ The default FAILS on a mismatch. Override only with an explicit flag
   (`--allow-mismatch`). A difference in RESOLUTION ONLY, when the aspect ratio is the same, is allowed —
   that is a proxy — but it is RECORDED in the signature.
"""
import sys, os, json, subprocess

ALGO_VERSION = '1.0'          # algorithm version — part of the signature
DUR_TOL = 0.05                # seconds
FPS_TOL = 0.01
AR_TOL = 0.005
SCALE_FLAGS = 'flags=lanczos'

# ── colour management ────────────────────────────────────────────────────
# Reference and render are often both completely untagged (`color_space=unknown`).
#    With no tag, every stage in the chain guesses — and you measure through the guess
#    without declaring it. Measured: the same untagged file decoded as bt601 vs bt709 differs by
#    mean 2.38 · p99 14 · max 18 — the same order as a typical replication error.
# ⇒ The comparison DECLARES the assumption and applies it to both sides explicitly.
#    It is an assumption, not knowledge: an untagged source cannot tell you on its own.
COLOR_MATRIX = 'bt709'      # HD standard; what a modern player assumes for 1080p/2160p
COLOR_IN_RANGE = 'tv'       # limited range (16–235) — the h264 default
COLOR_OUT = 'pc'            # full RGB 0–255 for measuring


MATRICES = ('bt709', 'bt601')


def color_filter(matrix=None):
    """The declared colour conversion. Applied IDENTICALLY to both sides.

    `matrix=None` ⇒ `COLOR_MATRIX` (the default for every comparison tool).
    An explicit matrix exists for a source KNOWN to be encoded differently, e.g. an
       untagged reference measured as bt601. It is DECLARED in the call, not left to
       ffmpeg's default guess — which is exactly what proved inconsistent between environments.
    ⛔ Only values from `MATRICES`; anything else is an error, not a silent fall back to bt709.
    """
    m = COLOR_MATRIX if matrix is None else matrix
    if m not in MATRICES:
        raise ValueError(f'unknown matrix: {m!r} (allowed: {MATRICES})')
    return (f'scale=in_color_matrix={m}:in_range={COLOR_IN_RANGE}'
            f':out_range={COLOR_OUT}')  # the scale filter — part of the signature


def sh(a, check=True, binary=False):
    # `text=True` on raw-video output raises UnicodeDecodeError.
    r = subprocess.run(a, capture_output=True, text=not binary)
    if check and r.returncode != 0:
        err = r.stderr if not binary else r.stderr.decode('utf-8', 'replace')
        sys.exit(f'failed: {" ".join(a[:6])}…\n{err[:600]}')
    return r


def probe(p):
    if not os.path.isfile(p):
        sys.exit(f'no such file: {p}')
    j = json.loads(sh(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                       '-of', 'json', p]).stdout)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
    if v is None:
        sys.exit(f'no video stream: {p}')
    n, d = v['r_frame_rate'].split('/')
    fps = float(n) / float(d) if float(d) else 0.0
    w, h = int(v['width']), int(v['height'])
    sar = v.get('sample_aspect_ratio', '1:1')
    try:
        sn, sd = (float(x) for x in sar.split(':'))
        sar = sn / sd if sd else 1.0
    except Exception:
        sar = 1.0
    if not sar or sar <= 0:
        sar = 1.0
    nb = v.get('nb_frames')
    return {'path': p, 'fps': fps, 'w': w, 'h': h, 'sar': sar, 'dar': (w * sar) / h,
            # The STREAM duration, not the format duration: the format includes an audio tail
            #    (e.g. 18.0907 vs 18.0333) and produces a false warning on the frame count.
            'dur': float(v.get('duration') or j['format']['duration']),
            'nb': int(nb) if nb and str(nb).isdigit() else None,
            'pix_fmt': v.get('pix_fmt', '?'),
            'color_space': v.get('color_space') or 'undeclared',
            'color_primaries': v.get('color_primaries') or 'undeclared',
            'color_transfer': v.get('color_transfer') or 'undeclared',
            'audio': [s for s in j['streams'] if s['codec_type'] == 'audio']}


def crop_dims(crop, src_w, src_h):
    """W:H:X:Y ⇒ (w,h) after a bounds check."""
    try:
        cw, ch, cx, cy = (int(x) for x in crop.split(':'))
    except Exception:
        sys.exit(f'--crop must be W:H:X:Y: {crop}')
    if cw <= 0 or ch <= 0 or cx < 0 or cy < 0 or cx + cw > src_w or cy + ch > src_h:
        sys.exit(f'crop {crop} exceeds {src_w}×{src_h}')
    return cw, ch


def frames_of(P):
    """The expected frame count: `nb_frames` first, stream duration only as a fallback."""
    if P['nb']:
        return P['nb']
    return int(round(P['fps'] * P['dur'])) if P['dur'] and P['fps'] else 0


def preflight(R, O, rdim, odim, rf=0.0, of=0.0, req_dur=None, dur=None,
              check_counts=True, win=None):
    """`win` = (start_ref, start_ours, n) — when set, the WINDOW is checked, not
    the file lengths. Without it: a 100-frame source vs a 50-frame replica, when you ask
    for only the first 10 — the tool returned exit 2 even though the window exists in full on both sides."""
    """Every difference between the sides is reported. Returns a list of (status, name, detail).
    'FAIL' = the files are not comparable. 'WARN' = comparable, but recorded in the signature."""
    out = []
    add = lambda st, n, d: out.append((st, n, d))
    ra, oa = R['dur'] - rf, O['dur'] - of
    if win is not None:
        sr, so, nw = win
        av_r, av_o = frames_of(R) - sr, frames_of(O) - so
        # Available and missing are reported separately (an older message said "missing 10"
        #    when ten were the AVAILABLE ones).
        lack = []
        if av_r < nw: lack.append(f'source missing {nw - av_r}')
        if av_o < nw: lack.append(f'ours missing {nw - av_o}')
        add('FAIL' if lack else 'OK', 'frame window',
            f'requested {nw} · available: source {av_r} (f{sr}..{sr + av_r - 1}) · '
            f'ours {av_o} (f{so}..{so + av_o - 1})' +
            ('  ⟵ ' + ' · '.join(lack) + '; the missing part gets MISSING frames' if lack else ''))
    elif req_dur is not None:
        lack = []
        if ra < req_dur - DUR_TOL: lack.append(f'source {ra:.3f}')
        if oa < req_dur - DUR_TOL: lack.append(f'ours {oa:.3f}')
        add('FAIL' if lack else 'OK', 'requested window',
            f'requested {req_dur:.3f}s · available: source {ra:.3f} · ours {oa:.3f}' +
            (' ⟵ missing in ' + ', '.join(lack) + '; the missing part gets MISSING frames' if lack else ''))
    else:
        dd = abs(ra - oa)
        add('FAIL' if dd > DUR_TOL else 'OK', 'length (from start point)',
            f'source {ra:.3f}s · ours {oa:.3f}s · difference {dd:.3f}' +
            ((f' ⟵ comparison window {dur:.3f}s; ' if dur else ' ⟵ ') +
             'the shorter side gets MISSING frames' if dd > DUR_TOL else ''))
    # A different fps is a FAILURE, not a warning. 30fps vs 24fps with the same frame count
    #    gives MAE 0.00 and looks perfect — while the motion in time is completely different.
    fd = abs(R['fps'] - O['fps'])
    add('FAIL' if fd > FPS_TOL else 'OK', 'frame rate',
        f"source {R['fps']:.4f} · ours {O['fps']:.4f}" +
        (' ⟵ **not comparable**: the same frame index means a different time' if fd > FPS_TOL else ''))
    # ⚠️ When a WINDOW is set (`--ref-from`/`--duration`), comparing the total
    #    frame count is meaningless — a 3s section of an 18s source is a valid case.
    if check_counts and win is None:
        nr, no = frames_of(R), frames_of(O)
        add('FAIL' if (nr and no and nr != no) else 'OK', 'frame count',
            f'source {nr} · ours {no}' + (' ⟵ one side is longer' if nr != no else ''))
    # A different resolution at the SAME aspect ratio = proxy: allowed, but recorded.
    rar, oar = rdim[0] * R['sar'] / rdim[1], odim[0] * O['sar'] / odim[1]
    ard = abs(rar - oar)
    add('FAIL' if ard > AR_TOL else 'OK', 'aspect ratio',
        f'source {rar:.4f} · ours {oar:.4f}' +
        (' ⟵ **mismatch**: stretching into one box would invent a match' if ard > AR_TOL else ''))
    add('WARN' if rdim != odim else 'OK', 'size (after crop)',
        f'source {rdim[0]}×{rdim[1]} · ours {odim[0]}×{odim[1]}' +
        (' ⟵ proxy: same aspect ratio, only the resolution differs; recorded in the signature' if rdim != odim else ''))
    ha, hb = bool(R['audio']), bool(O['audio'])
    if ha and hb:
        add('OK', 'audio', 'on both sides')
    elif ha or hb:
        add('WARN', 'audio', ('only in the source' if ha else 'only in ours'))
    else:
        add('WARN', 'audio', 'on neither side')
    return out


def preflight_failed(checks):
    return [c for c in checks if c[0] == 'FAIL']


def print_preflight(checks):
    for st, name, detail in checks:
        print(f'  [{st:4s}] {name}: {detail}')


# ─────────────────────── stream decoding with an rc check ──────────────

def frame_chain(start_frame=0, crop=None, scale=None, extra=None, color=True,
                matrix=None):
    """The ONLY filter chain for extracting frames — for comparison, hires and blink.

    Why one: when there were two separate extraction paths, one of them used a variable
       left over from another loop (`g['i']` instead of `i`) — and every hires image came out as THE SAME
       frame, with different file names and times. Duplicated logic is what allowed that
       to exist, so extraction lives here, in one place.
    ⛔ No `-ss`: alignment by FRAME INDEX only.

    ⚠️ DECLARED colour management: the chain always ends with `color_filter()`, so both
       sides go through the same declared conversion and not the default guess.
       `color=False` keeps the old path — only for measuring the effect itself.
    """
    vf = []
    if crop: vf.append(f'crop={crop}')
    if start_frame:
        vf.append(f'trim=start_frame={int(start_frame)}')
        vf.append('setpts=PTS-STARTPTS')
    if scale: vf.append(scale)
    if extra: vf.append(extra)
    if color: vf.append(color_filter(matrix))
    return ','.join(vf) or 'null'


def extract_frame(path, frame_idx, out_png, crop=None, scale=None):
    """Outputs EXACTLY frame `frame_idx` to a PNG file, through the same chain.
    Returns the path, or `None` if extraction failed.
    ⚠️ Does NOT crash the process: a failure to extract a single evidence image is reported by
    the caller; the hard failure is already caught in the main decoder."""
    r = sh(['ffmpeg', '-v', 'error', '-xerror', '-y', '-i', path,
            '-vf', frame_chain(frame_idx, crop, scale), '-frames:v', '1', out_png],
           check=False)
    return out_png if (r.returncode == 0 and os.path.isfile(out_png)) else None


class Decoder:
    """Reads frames SEQUENTIALLY from a frame window. No `-ss`, no skipping.
    `ffmpeg -ss` at a rounded time lands on a frame boundary and sometimes returns the next one.
    ⛔ At the end, ffmpeg's EXIT CODE is checked: a decode that failed midway is not "a short film"."""

    def __init__(self, path, w, h, crop=None, vf_extra=None, start_frame=0, count=None,
                 scale=None, matrix=None):
        sc = scale if scale is not None else f'scale={w}:{h}:{SCALE_FLAGS}'
        vf = frame_chain(start_frame, crop, sc, vf_extra, matrix=matrix)
        # `-xerror` is mandatory. Without it ffmpeg decodes "as much as it can" from a broken file
        #    and returns rc=0 — i.e. a partial stream is measured as if it were complete. Tested on
        #    a file cut in half: without `-xerror` rc=0, with it rc=183.
        self.cmd = ['ffmpeg', '-v', 'error', '-xerror', '-i', path, '-vf', vf]
        if count:
            self.cmd += ['-frames:v', str(int(count))]
        self.cmd += ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.n = w * h * 3
        self.p = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.count = 0
        self.tail = b''

    def read(self):
        b = self.p.stdout.read(self.n)
        if len(b) < self.n:
            self.tail = b
            return None
        self.count += 1
        return b

    def close(self):
        """Returns (rc, stderr). ⚠️ Call it AFTER the stream is drained."""
        try:
            err = self.p.stderr.read() or b''
        except Exception:
            err = b''
        try:
            self.p.stdout.close()
        except Exception:
            pass
        rc = self.p.wait()
        return rc, err.decode('utf-8', 'replace')


def read_frames(path, w, h, count=None, start_frame=0, crop=None, scale=None,
                vf_extra=None, dtype=None, matrix=None):
    """Reads frames as numpy arrays, WITH an exit-code check.

    Why this lives in the core and not in each reader: `Decoder.read()` returns bytes,
       and `close()` returns `(rc, stderr)` that must be CHECKED. Every tool that implemented
       the loop itself forgot the check — and without it a file cut midway is read as "a short film"
       and the `-xerror` in `Decoder` is wasted.
    ⛔ Raises on rc≠0. "Fewer frames" is not a result, it is a failure.
    """
    import numpy as _np
    d = Decoder(path, w, h, crop=crop, vf_extra=vf_extra,
                start_frame=start_frame, count=count, scale=scale, matrix=matrix)
    out = []
    while True:
        b = d.read()
        if b is None:
            break
        a = _np.frombuffer(b, _np.uint8).reshape(h, w, 3)
        out.append(a.astype(dtype) if dtype is not None else a)
    rc, err = d.close()
    if rc != 0:
        raise RuntimeError(f'decode failed ({path}, rc={rc}): {err.strip()[:300]}')
    if d.tail:
        raise RuntimeError(f'decode cut off mid-frame ({path}): '
                           f'{len(d.tail)} extra bytes out of {w * h * 3}')
    if count is not None and len(out) != count:
        raise RuntimeError(f'read {len(out)} frames out of the {count} requested ({path}) '
                           f'— that is a shortfall, not "a short film"')
    return out


def signature(tool, R, O, rdim, odim, wh, union, ranges_txt, crops, n_read, n_expect,
              extra=None, pipeline=None, align=None):
    """Full measurement signature. ⛔ Never compare two numbers with different signatures.
    ⚠️ `pipeline` is conceptually MANDATORY: the two tools have different scale pipelines, so never
    copy a signature from one to the other. `sbs.py` adds Pillow-LANCZOS and padding; `perframe.py`
    does not. Without this description two signatures would look identical while the numbers are not comparable."""
    sig = {
        'tool': tool,
        'algorithm-version': ALGO_VERSION,
        'source-size': f"{R['w']}×{R['h']}",
        'replica-size': f"{O['w']}×{O['h']}",
        'fps-source': f"{R['fps']:.4f}",
        'fps-replica': f"{O['fps']:.4f}",
        'crop-source': crops[0] or 'none',
        'crop-replica': crops[1] or 'none',
        'size-after-crop': f'{rdim[0]}×{rdim[1]} / {odim[0]}×{odim[1]}',
        'measure-resolution': f'{wh[0]}×{wh[1]}',
        'scale-pipeline': pipeline or f'ffmpeg scale ({SCALE_FLAGS}) only',
        'alignment': align or 'frame index (no -ss)',
        'SAR-source/replica': f"{R['sar']:.4f} / {O['sar']:.4f}",
        # Don't just write "sRGB" — report what is DECLARED in the file, and what the conversion actually is.
        'pix_fmt-source': R['pix_fmt'],
        'pix_fmt-replica': O['pix_fmt'],
        'declared-colour-source': f"{R['color_space']}/{R['color_primaries']}/{R['color_transfer']}",
        'declared-colour-replica': f"{O['color_space']}/{O['color_primaries']}/{O['color_transfer']}",
        'colour-conversion': f'ffmpeg → rgb24 8-bit · declared: {COLOR_MATRIX}/{COLOR_IN_RANGE} → {COLOR_OUT}',
        'channel-merge': union,
        'ranges': ranges_txt,
        'frames-read': n_read,
        'frames-expected': n_expect,
    }
    if extra:
        sig.update(extra)
    return sig


def print_signature(sig):
    print('measurement signature:')
    for k, v in sig.items():
        print(f'  · {k}: {v}')
    print('  ⛔ never compare two numbers with different signatures.')
