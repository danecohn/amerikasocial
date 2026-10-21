#!/bin/sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export LD_PRELOAD="${AMERIKA_LAYERSHELL_LIB:-}" GTK_A11Y=none
export AMERIKA_SHARE="$ROOT/src/os/amerika" AMERIKA_ICONS="$ROOT/src/os/icons" AMERIKA_WALLPAPERS="$ROOT/src/os/wallpapers"
cd "$ROOT"
# Use a test-only module path to exercise the real native host with this rig.
mkdir -p "$T/modules/amerika/shell"
printf '__path__ = [%s, %s]\n' "\"$T/modules/amerika\"" "\"$ROOT/src/os/amerika\"" > "$T/modules/amerika/__init__.py"
printf '__path__ = [%s, %s]\n' "\"$T/modules/amerika/shell\"" "\"$ROOT/src/os/amerika/shell\"" > "$T/modules/amerika/shell/__init__.py"
printf 'import runpy; runpy.run_path(%s, run_name="__main__")\n' "\"$ROOT/tests/rig/desktop_services_test.py\"" > "$T/modules/amerika/shell/main.py"
export PYTHONPATH="$T/modules:$ROOT/src/os"
"$AMERIKA_SHELL_HOST"
