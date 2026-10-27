#!/usr/bin/env bash
# Generate platform icons from the Linux SVG so every OS shows the same Gossip icon.
#
# Usage: scripts/generate_icons.sh <ico|icns> <output-file>
#   ico   Windows icon (PNG-compressed entries, 16-256 px)
#   icns  macOS icon (PNG-compressed entries, 16-1024 px), written directly so the build does
#         not depend on `iconutil`, which crashes on some hosted macOS runners
# Needs rsvg-convert (or inkscape) and python.
set -euo pipefail

SVG="$(dirname "$0")/../data/icons/hicolor/scalable/apps/com.github.sincorchetes.gossip_gcp.svg"
FORMAT="${1:?usage: $0 <ico|icns> <output-file>}"
OUT="${2:?usage: $0 <ico|icns> <output-file>}"

render() { # <size> <png>
  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w "$1" -h "$1" "$SVG" -o "$2"
  else
    inkscape -w "$1" -h "$1" -o "$2" "$SVG" >/dev/null 2>&1
  fi
}

case "$FORMAT" in
  ico) sizes=(16 24 32 48 64 128 256) ;;
  icns) sizes=(16 32 64 128 256 512 1024) ;;
  *)
    echo "Unknown format: $FORMAT (expected ico or icns)" >&2
    exit 2
    ;;
esac

PY="$(command -v python3 || command -v python)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$(dirname "$OUT")"

for s in "${sizes[@]}"; do render "$s" "$WORK/$s.png"; done

"$PY" - "$FORMAT" "$OUT" "$WORK" "${sizes[@]}" <<'PYEOF'
import struct
import sys

fmt, out, work, *sizes = sys.argv[1:]
blobs = {int(s): open(f"{work}/{s}.png", "rb").read() for s in sizes}

if fmt == "ico":
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs.items():
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    payload = struct.pack("<HHH", 0, 1, len(blobs)) + entries + data
else:
    # ICNS element types holding PNG data, including the @2x aliases used on Retina displays
    types = [
        ("icp4", 16), ("icp5", 32), ("ic11", 32), ("ic12", 64), ("ic07", 128),
        ("ic13", 256), ("ic08", 256), ("ic14", 512), ("ic09", 512), ("ic10", 1024),
    ]
    body = b"".join(
        kind.encode() + struct.pack(">I", 8 + len(blobs[size])) + blobs[size]
        for kind, size in types
    )
    payload = b"icns" + struct.pack(">I", 8 + len(body)) + body

with open(out, "wb") as fh:
    fh.write(payload)
PYEOF
echo "Generated $OUT"
