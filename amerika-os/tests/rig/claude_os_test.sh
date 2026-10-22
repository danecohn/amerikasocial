#!/bin/sh
# Run inside tests/rig/claude_os_rig.sh:  tests/rig/claude_os_rig.sh "sh tests/rig/claude_os_test.sh"
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
exec python3 "$ROOT/tests/rig/claude_os_test.py"
