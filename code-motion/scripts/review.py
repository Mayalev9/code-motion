#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review.py — a review package for the encoded film. **Helps you see; it is not a judge.**

    python3 review.py OUT.mp4 [--direction direction/SCENE.md] [--prev OLD.mp4]
                     [--ref REF.mp4] [--keys 0.5,3.2,7] [--out DIR] [--label v2]

Writes to DIR (default: <name>-review/ next to the file):
  index.html      one page: phone-size player · key frames · contact sheet · motion curve · data
  keys/           full-resolution frames at the key points (shots from the direction doc / automatic)
  phone/          the same frames at 390px wide — roughly what a phone shows
  phone.mp4       the film at 390px wide, with sound
  sheet.png       contact sheet of the whole film (overview only — not evidence of pacing)
  motion.png      frame difference across the film + shot boundaries: where it moves, where it rests
  compare-prev.png / compare-ref.png   side by side at the same points
  data.json       file data · audio · measurement warnings (from the delivery gate)

and appends an empty review-round template to direction/SCENE.review.md (QUALITY.md §3) to fill in by eye.

⛔ The script does NOT decide that a film is "beautiful" or "studio level". There is no score. A warning = a place
   to look; no warning ≠ quality.
"""
import sys, os, re, json, shutil, subprocess, argparse, datetime, html

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('numpy/Pillow missing:  pip3 install numpy pillow')
import deliver_gate as dg

PHONE_W = 390


def run(a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'failed: {" ".join(a[:4])}…\n{r.stderr[:400]}')
    return r


def grab(path, t, out, width=None):
    vf = f'scale={width}:-2' if width else 'null'
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t):.3f}', '-i', path, '-frames:v', '1', '-vf', vf, out])


def font(size):
    # ⚠️ Pillow here may lack raqm ⇒ RTL text comes out reversed. In images: only numbers and Latin;
    #    all other captions live in index.html.
    for f in ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
              '/Library/Fonts/Arial Unicode.ttf', '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


def parse_direction(p):
    """The ```shots {json}``` block from the direction doc (DIRECTION.md)."""
    if not p or not os.path.exists(p):
        return None
    m = re.search(r'```shots\s*\n(.*?)\n```', open(p, encoding='utf-8').read(), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        sys.exit(f'the shots block in {p} is not valid JSON: {e}')


def motion_curve(path, fps):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', 'scale=96:-2,format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    W, H = dg.probe_size_cache[path]
    w, h = 96, int(round(H * 96 / W / 2)) * 2
    a = np.frombuffer(raw, np.uint8)
    n = len(a) // (w * h)
    a = a[:n * w * h].reshape(n, h, w).astype(np.int16)
    return np.r_[0, np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))]


def plot_motion(curve, fps, dur, shots, out, keys):
    W, H, pad = 1400, 300, 40
    im = Image.new('RGB', (W, H), (250, 250, 248))
    d = ImageDraw.Draw(im)
    mx = max(1.0, float(np.percentile(curve, 99)) * 1.1)
    X = lambda t: pad + (W - 2 * pad) * t / max(dur, 1e-6)
    Y = lambda v: H - pad - (H - 2 * pad) * min(v, mx) / mx
    for i, s in enumerate(shots or []):
        d.rectangle([X(s['t0']), pad, X(s['t1']), H - pad], outline=(210, 210, 205))
        d.text((X(s['t0']) + 4, pad + 4), f'#{i + 1}', fill=(120, 120, 120), font=font(13))
    for k in keys:
        d.line([X(k), pad, X(k), H - pad], fill=(200, 230, 150), width=2)
    pts = [(X(i / fps), Y(v)) for i, v in enumerate(curve)]
    if len(pts) > 1:
        d.line(pts, fill=(30, 30, 36), width=2)
    for s in range(0, int(dur) + 1):
        d.text((X(s) - 4, H - pad + 8), str(s), fill=(90, 90, 90), font=font(12))
    d.text((pad, 10), 'frame diff  |  green = key frames  |  boxes = shots (#)  |  x = seconds', fill=(60, 60, 60), font=font(14))
    im.save(out)


def side_by_side(a_paths, b_paths, labels, out, width=300):
    rows = []
    for pa, pb in zip(a_paths, b_paths):
        A, B = Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')
        A = A.resize((width, int(A.height * width / A.width)))
        B = B.resize((width, int(B.height * width / B.width)))
        h = max(A.height, B.height)
        r = Image.new('RGB', (2 * width + 12, h), (30, 30, 30))
        r.paste(A, (0, 0)); r.paste(B, (width + 12, 0))
        rows.append(r)
    if not rows:
        return
    cols = min(4, len(rows))
    rw, rh = rows[0].width, max(r.height for r in rows)
    lines = (len(rows) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (rw + 16), lines * (rh + 16) + 40), (30, 30, 30))
    ImageDraw.Draw(sheet).text((10, 10), f'LEFT {labels[0]}   |   RIGHT {labels[1]}   (same moments)',
                               fill=(230, 230, 230), font=font(18))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % cols) * (rw + 16), 40 + (i // cols) * (rh + 16)))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser(description='Review package for the encoded film (not a judge)')
    ap.add_argument('video')
    ap.add_argument('--direction', help='direction/SCENE.md with a ```shots``` block')
    ap.add_argument('--prev', help='previous version to compare against')
    ap.add_argument('--ref', help='reference to compare against (replication/inspiration)')
    ap.add_argument('--keys', help='key points in seconds, comma-separated')
    ap.add_argument('--out')
    ap.add_argument('--label', default='')
    a = ap.parse_args()
    dg.need_tools()
    v = os.path.abspath(a.video)
    if not os.path.isfile(v):
        sys.exit(f'no such file: {v}')
    out = os.path.abspath(a.out or os.path.splitext(v)[0] + '-review')
    for sub in ('keys', 'phone'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    info = dg.probe(v)
    has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])
    gates = dg.check(v, 'yes' if has_audio else 'no')          # also fills probe_size_cache
    vs = next(s for s in info['streams'] if s['codec_type'] == 'video')
    fps = dg.rate(vs['r_frame_rate']) or 30.0
    dur = float(vs.get('duration') or info['format']['duration'])

    direction = parse_direction(a.direction)
    shots = (direction or {}).get('shots', [])
    # key points: declared > open/peak/end from the direction doc + middle of every shot > automatic
    if a.keys:
        keys = [float(x) for x in a.keys.split(',')]
    elif shots:
        keys = []
        for s in shots:
            keys.append((s['t0'] + s['t1']) / 2)
        for k in ('open', 'peak', 'end'):
            if isinstance((direction.get('keyframes') or {}).get(k), (int, float)):
                keys.append(direction['keyframes'][k])
    else:
        keys = [dur * f for f in (0.02, 0.2, 0.4, 0.6, 0.8)] + [max(0, dur - 0.05)]
    keys = sorted({round(min(max(0.0, k), max(0, dur - 1 / fps)), 3) for k in keys})

    kp, pp = [], []
    for i, t in enumerate(keys):
        f = os.path.join(out, 'keys', f'{i:02d}_{t:06.2f}.png'); grab(v, t, f); kp.append(f)
        g = os.path.join(out, 'phone', f'{i:02d}_{t:06.2f}.png'); grab(v, t, g, PHONE_W); pp.append(g)

    # contact sheet: up to ~48 cells for the whole film
    sfps = min(fps, max(0.5, 48 / max(dur, 0.1)))
    run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-vf',
         f'fps={sfps:.4f},scale=180:-2,tile=8x6:margin=4:padding=4', '-frames:v', '1',
         os.path.join(out, 'sheet.png')])
    run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-vf', f'scale={PHONE_W}:-2', '-c:v', 'libx264',
         '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'] +
        (['-c:a', 'aac', '-b:a', '128k'] if has_audio else ['-an']) + [os.path.join(out, 'phone.mp4')])

    curve = motion_curve(v, fps)
    plot_motion(curve, fps, dur, shots, os.path.join(out, 'motion.png'), keys)
    holds = []
    thr = max(0.15, float(np.percentile(curve, 20)))
    run_s = None
    for i, x in enumerate(list(curve) + [1e9]):
        if x <= thr and run_s is None:
            run_s = i
        elif x > thr and run_s is not None:
            if (i - run_s) / fps >= 0.4:
                holds.append((round(run_s / fps, 2), round(i / fps, 2)))
            run_s = None

    for flag, path, name in ((a.prev, a.prev, 'prev'), (a.ref, a.ref, 'ref')):
        if not path:
            continue
        bp = []
        for i, t in enumerate(keys):
            f = os.path.join(out, 'keys', f'{name}_{i:02d}.png'); grab(os.path.abspath(path), t, f); bp.append(f)
        side_by_side(bp, kp, (os.path.basename(path), os.path.basename(v)), os.path.join(out, f'compare-{name}.png'))

    data = {
        'video': v, 'label': a.label, 'duration': dur, 'fps': fps, 'size': dg.probe_size_cache[v],
        'audio': has_audio, 'keys': keys,
        'measured': [{k: g[k] for k in ('id', 'name', 'ok', 'detail')} | {'warn': bool(g.get('warn'))}
                     for g in gates],
        'still_spans': holds,
        'note': 'measurements point where to look; they are not a quality verdict',
    }
    json.dump(data, open(os.path.join(out, 'data.json'), 'w'), ensure_ascii=False, indent=1)

    # one page
    e = html.escape
    rel = lambda p: os.path.relpath(p, out)
    meas = ''.join(f"<li class='{'bad' if not g['ok'] else 'warn' if g.get('warn') else ''}'>"
                   f"<b>{e(g['id'])} {e(g['name'])}</b> — {e(g['detail'])}</li>" for g in gates)
    shots_html = ''.join(f"<tr><td>#{i + 1}</td><td>{s['t0']:.2f}–{s['t1']:.2f}</td>" + ''.join(
        f"<td>{e(str(s.get(k, '')))}</td>" for k in ('role', 'focus', 'change', 'why', 'sound')) + '</tr>'
        for i, s in enumerate(shots))
    keys_html = ''.join(f"<figure><img src='{rel(p)}'><figcaption>{t:.2f}s</figcaption></figure>"
                        for p, t in zip(pp, keys))
    cmp_html = ''.join(f"<h2>Comparison — {'previous version' if n == 'prev' else 'reference'} (left) vs. current (right)</h2><img class='wide' src='compare-{n}.png'>"
                       for n, f in (('prev', a.prev), ('ref', a.ref)) if f)
    page = f"""<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8">
<title>Review · {e(os.path.basename(v))}</title>
<style>
:root{{--bg:#f4f4f1;--fg:#16161a;--mut:#6b6b70;--line:#dcdcd6;--bad:#c0392b;--warn:#b7791f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141416;--fg:#ececec;--mut:#9a9aa0;--line:#2c2c30}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif;margin:0;padding:24px 16px;max-width:1200px;margin-inline:auto}}
h1{{font-size:20px}} h2{{font-size:16px;margin-top:32px;border-top:1px solid var(--line);padding-top:16px}}
.lead{{color:var(--mut)}} .phone{{width:{PHONE_W}px;max-width:100%;border-radius:18px;border:1px solid var(--line)}}
.keys{{display:flex;flex-wrap:wrap;gap:12px}} figure{{margin:0}} figure img{{width:{PHONE_W // 2}px;display:block;border:1px solid var(--line)}}
figcaption{{color:var(--mut);font-size:12px;text-align:center}}
img.wide{{max-width:100%;border:1px solid var(--line)}} li.bad{{color:var(--bad)}} li.warn{{color:var(--warn)}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border:1px solid var(--line);padding:4px 6px;vertical-align:top}}
</style></head><body>
<h1>Review · {e(os.path.basename(v))} {e(a.label)}</h1>
<p class="lead">This package helps you see. It does <b>not</b> decide that the film is good. Judging: QUALITY.md, watching the encoded film with sound.</p>
<h2>Watch at phone size (with sound)</h2>
<video class="phone" src="phone.mp4" controls playsinline></video>
<p class="lead">{dur:.2f}s · {fps:g}fps · {dg.probe_size_cache[v][0]}×{dg.probe_size_cache[v][1]} · {'has audio' if has_audio else 'silent'}</p>
<h2>Key frames — at phone width</h2><div class="keys">{keys_html}</div>
<h2>Motion vs. rest</h2><img class="wide" src="motion.png">
<p class="lead">Frame difference across the film (x axis in seconds). Green lines = key frames; numbered boxes = the shots from the table.</p>
<p class="lead">Holds ≥0.4s: {e(', '.join(f'{x}–{y}' for x, y in holds) or 'none')} — intended? (Q9)</p>
{('<h2>Shot plan</h2><table><tr><th>#</th><th>time</th><th>role</th><th>focus</th><th>changes</th><th>why</th><th>sound</th></tr>' + shots_html + '</table>') if shots else ''}
{cmp_html}
<h2>Contact sheet</h2><img class="wide" src="sheet.png"><p class="lead">Overview only: it does not show pacing, short freezes or sync.</p>
<h2>Measurements (places to look)</h2><ul>{meas}</ul>
</body></html>"""
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(page)

    # review-round template to fill in by eye
    if a.direction:
        rv = re.sub(r'\.md$', '', a.direction) + '.review.md'
        prev_log = open(rv, encoding='utf-8').read() if os.path.exists(rv) else ''
        n = 1 + prev_log.count('\n## Round ')
    # do not add a new template while the previous one is still empty (running ≠ a review round)
    if a.direction and '|  |  |  |  |' in prev_log.rsplit('\n## Round ', 1)[-1]:
        print(f'  the last round template in {rv} is still empty — no new one added. Fill it in first.')
    elif a.direction:
        with open(rv, 'a', encoding='utf-8') as f:
            f.write(f"""
## Round {n} · {a.label or os.path.basename(v)} · {datetime.date.today():%Y-%m-%d}
Package: {out}/index.html
Watched: [ ] full MP4 · [ ] at phone size · [ ] with sound · [ ] without sound
(whatever was not done — write that it was not done, and why)

| weakness (concrete, with the second) | Q# | cause | change made |
|---|---|---|---|
|  |  |  |  |

Comparison with the previous version:
""")
        print(f'added round template {n} to {rv}')
    print(f'✓ {out}/index.html   ({len(keys)} key frames · motion curve · contact sheet · phone.mp4)')
    print('  ⛔ This is a package for watching, not a verdict. Judge by QUALITY.md — by eye, on the encoded film.')


if __name__ == '__main__':
    main()
