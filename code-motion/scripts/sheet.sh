#!/usr/bin/env bash
# Contact sheet from a video — the step you must not skip before showing anything.
# Usage: sheet.sh video.mp4 [fps] [cols] [rows] [out.png]
set -e
V="$1"; FPS="${2:-1}"; C="${3:-6}"; R="${4:-4}"; OUT="${5:-sheet.png}"
[ -z "$V" ] && { echo "Usage: sheet.sh video.mp4 [fps] [cols] [rows] [out.png]"; exit 1; }
DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")"
PAGES="$(awk -v d="$DURATION" -v fps="$FPS" -v slots="$((C * R))" 'BEGIN { n = int(d * fps); if (n < d * fps) n++; p = int((n + slots - 1) / slots); print (p > 0 ? p : 1) }')"
VF="fps=$FPS,scale=210:-2,tile=${C}x${R}:margin=3:padding=3"
if [ "$PAGES" -gt 1 ]; then
  STEM="${OUT%.*}"; EXT="${OUT##*.}"
  PATTERN="${STEM}-%03d.${EXT}"
  ffmpeg -y -v error -i "$V" -vf "$VF" "$PATTERN"
  echo "✓ $PATTERN   (${DURATION}s · ${FPS}fps · ${C}×${R} · several sheets)"
else
  ffmpeg -y -v error -i "$V" -vf "$VF" -frames:v 1 "$OUT"
  echo "✓ $OUT   (${DURATION}s · ${FPS}fps · ${C}×${R})"
fi
