#!/bin/sh
# Headless KWin on a PRIVATE D-Bus with throwaway XDG dirs, for testing the Amerika shell.
# Usage: kwin-rig.sh <script-to-run-inside> [args]. The script runs with WAYLAND_DISPLAY set to the test KWin.
# It never touches the running session. Needs dbus-run-session (see work/tools/dbus-dl) and the layer-shell debs.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TOOLS=$ROOT/../tools
T=$(mktemp -d)
echo "$T" > "$ROOT/dist/rig-dir"
LS=$TOOLS/layershell/root/usr/lib/aarch64-linux-gnu
export PATH="$TOOLS/dbus-dl/root/usr/bin:$ROOT/src/os/bin:$PATH"
export GI_TYPELIB_PATH="$LS/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export LD_LIBRARY_PATH="$LS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export AMERIKA_LAYERSHELL_LIB="$LS/libgtk4-layer-shell.so.0"
export XDG_RUNTIME_DIR="$T/runtime"
mkdir -m 0700 "$XDG_RUNTIME_DIR"
export XDG_CONFIG_HOME="$T/config" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" XDG_STATE_HOME="$T/state" HOME="$T/home"
export PYTHONPATH="$ROOT/src/os${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$HOME"
export T RIG_WAIT=${RIG_WAIT:-6} RIG_SCRIPT="$1"; shift; export RIG_ARGS="$*"
exec dbus-run-session -- sh -c '
  kwin_wayland --virtual --socket rig-wl --width 1920 --height 1080 --no-lockscreen >"$T/kwin.log" 2>&1 &
  KW=$!
  sleep 4
  export WAYLAND_DISPLAY=rig-wl GDK_BACKEND=wayland QT_QPA_PLATFORM=wayland
  sh -c "$RIG_SCRIPT $RIG_ARGS" >"$T/script.log" 2>&1
  RESULT=$?
  kill $KW 2>/dev/null
  exit $RESULT
' 2>"$T/dbus.log"
