#!/bin/sh
# Webview shell with a test page. Run:  tests/rig/studio-rig.sh tests/rig/studio_webview_test.sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export LD_PRELOAD="${AMERIKA_LAYERSHELL_LIB:-}" GTK_A11Y=none
mkdir -p "$ROOT/dist/studio"
cd "$ROOT/tests/rig"
python3 studio_webview_test.py 2>&1 | grep -v "Gtk-WARNING\|^$" | tee "$ROOT/dist/studio/webview-rig.log"
grep -q "STUDIO WEBVIEW RIG OK" "$ROOT/dist/studio/webview-rig.log"
