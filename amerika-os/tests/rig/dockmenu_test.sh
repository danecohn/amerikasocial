# Right-click menu on the dock must stay open while other windows keep reporting changes.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_SHARE=$ROOT/src/os/amerika AMERIKA_ICONS=$ROOT/src/os/icons AMERIKA_WALLPAPERS=$ROOT/src/os/wallpapers
export AMERIKA_DEBUG=1
action() { gdbus call --session --dest org.amerika.Shell --object-path /Control --method org.amerika.Control.Action "$1" >/dev/null 2>&1; }
$ROOT/src/os/bin/amerika-shell > $T/shell.log 2>&1 &
SP=$!
sleep 6
python3 $ROOT/tests/rig/churn_window.py > $T/churn.log 2>&1 &
CW=$!
sleep 3
action debug-dock-menu; sleep 4; action debug-report; sleep 1
echo "with a churning window: $(grep DEBUG $T/shell.log | tail -1)"
kill $CW $SP 2>/dev/null
