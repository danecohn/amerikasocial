#!/bin/sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_SHARE="$ROOT/src/os/amerika" AMERIKA_ICONS="$ROOT/src/os/icons" AMERIKA_WALLPAPERS="$ROOT/src/os/wallpapers" GTK_A11Y=none
"$ROOT/src/os/bin/amerika-shell" >"$T/shell.log" 2>&1 &
SHELL_PID=$!
trap 'kill "$SHELL_PID" 2>/dev/null || true' EXIT
sleep 3
python3 "$ROOT/tests/rig/agent_gateway.py"
