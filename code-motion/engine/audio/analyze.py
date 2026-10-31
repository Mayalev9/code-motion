#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyses a track into per-frame data an animation can ride on.
Usage:  python3 audio/analyze.py track.wav [fps]
Output: track.json  — bass/mid/high/level/onset per frame + a list of beats.
"""
import numpy as np, wave, json, sys, os

path = sys.argv[1] if len(sys.argv) > 1 else 'track.wav'
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

with wave.open(path) as w:
    sr = w.getframerate()
    nch = w.getnchannels()
    raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
if nch > 1:
    raw = raw.reshape(-1, nch).mean(axis=1)

dur = len(raw) / sr
frames = int(round(dur * FPS))
win = 2048
hann = np.hanning(win)
freqs = np.fft.rfftfreq(win, 1 / sr)

# the three bands — the limits were chosen so the kick falls in bass and the hi-hat in high
BANDS = {'bass': (30, 160), 'mid': (160, 2000), 'high': (2000, 12000)}
masks = {k: (freqs >= lo) & (freqs < hi) for k, (lo, hi) in BANDS.items()}

series = {k: [] for k in BANDS}
level, flux = [], []
prev = None

for i in range(frames):
    c = int(i / FPS * sr)
    a = max(0, c - win // 2)
    seg = raw[a:a + win]
    if len(seg) < win:
        seg = np.pad(seg, (0, win - len(seg)))
    spec = np.abs(np.fft.rfft(seg * hann))
    for k, m in masks.items():
        series[k].append(float(spec[m].mean()))
    level.append(float(np.sqrt(np.mean(seg ** 2))))
    # spectral flux: a sudden rise in energy = an attack
    flux.append(0.0 if prev is None else float(np.sum(np.maximum(0, spec - prev))))
    prev = spec

def norm(x):
    x = np.array(x)
    lo, hi = np.percentile(x, 2), np.percentile(x, 98)
    return np.clip((x - lo) / max(1e-9, hi - lo), 0, 1)

out = {k: norm(v).round(4).tolist() for k, v in series.items()}
out['level'] = norm(level).round(4).tolist()
f = norm(flux)
out['onset'] = f.round(4).tolist()

# beats: local peaks in the flux above a threshold, with a minimum spacing
thr = float(np.percentile(f, 82))
beats, last = [], -99
for i in range(1, len(f) - 1):
    if f[i] > thr and f[i] >= f[i - 1] and f[i] > f[i + 1] and i - last > FPS * 0.22:
        beats.append(i); last = i
out['beats'] = beats
out['fps'] = FPS
out['duration'] = dur

dst = os.path.splitext(path)[0] + '.json'
json.dump(out, open(dst, 'w'))
print(f'✓ {dst}  {frames} frames · {len(beats)} beats · {dur:.2f}s')
