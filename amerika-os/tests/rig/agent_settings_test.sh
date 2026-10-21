#!/bin/sh
# Settings > Amerika Agent against the fake CLI. Run:  tests/rig/agent-rig.sh tests/rig/agent_settings_test.sh
# (kwin-rig.sh reports the script's exit status; the full log is also kept in dist/agent-ui/settings-rig.log)
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export LD_PRELOAD="${AMERIKA_LAYERSHELL_LIB:-}" GTK_A11Y=none
mkdir -p "$ROOT/dist/agent-ui"
cd "$ROOT/tests/rig"
python3 agent_settings_test.py 2>&1 | grep -v "Gtk-WARNING\|^$" | tee "$ROOT/dist/agent-ui/settings-rig.log"
grep -q "SETTINGS RIG OK" "$ROOT/dist/agent-ui/settings-rig.log"
