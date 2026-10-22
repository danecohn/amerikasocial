#!/bin/sh
# AmerikaBox in the real webview shell. Run:  tests/rig/studio-rig.sh src/os/box/test/rig/box_rig.sh
set -eu
ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
export LD_PRELOAD="${AMERIKA_LAYERSHELL_LIB:-}" GTK_A11Y=none
mkdir -p "$ROOT/dist/studio"
cd "$ROOT/src/os/box/test/rig"
python3 box_rig.py 2>&1 | grep -v "Gtk-WARNING\|^$" | tee "$ROOT/dist/studio/box-rig.log"
grep -q "BOX RIG OK" "$ROOT/dist/studio/box-rig.log"
