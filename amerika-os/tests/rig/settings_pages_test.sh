#!/bin/sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export GTK_A11Y=none
python3 "$ROOT/tests/rig/settings_pages_test.py"
