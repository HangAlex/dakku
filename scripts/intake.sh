#!/bin/bash
# intake.sh <id> <bytes>: the picture ChatGPT drew for <id>, just downloaded (found in ~/Downloads by its size),
# goes to art/incoming/<id>.png (an earlier try is kept as <id>-vN.png) and through the gate.
set -e
cd "$(dirname "$0")/.."
id=$1; size=$2
f=$(find ~/Downloads -maxdepth 1 -type f -size "${size}c" | head -1)
[ -n "$f" ] || { echo "no file of $size bytes in ~/Downloads"; exit 1; }
if [ -e "art/incoming/$id.png" ]; then n=1; while [ -e "art/incoming/$id-v$n.png" ]; do n=$((n+1)); done; mv "art/incoming/$id.png" "art/incoming/$id-v$n.png"; fi
mv "$f" "art/incoming/$id.png"
python3 scripts/duckgate.py "$id=art/incoming/$id.png" 2>&1 | grep -E '^\s*(!!|wing|verdict|look:)'
