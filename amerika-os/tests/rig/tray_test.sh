#!/bin/sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_SHARE="$ROOT/src/os/amerika" AMERIKA_ICONS="$ROOT/src/os/icons" AMERIKA_WALLPAPERS="$ROOT/src/os/wallpapers"
export LD_PRELOAD="$AMERIKA_LAYERSHELL_LIB"
export GTK_A11Y=none
python3 "$ROOT/tests/rig/tray_test.py"
