#!/bin/sh
# Private KWin rig for the desktop-parity tests: own Wayland socket (rig-desktop) and rig-dir file, so it never collides with
# other rigs (tools/kwin-rig.sh uses rig-wl). Usage: desktop_rig.sh "<command>"; the command runs with WAYLAND_DISPLAY set.
# Extra env: DESKTOP_RIG_WAIT (seconds to let KWin start, default 4), DESKTOP_RIG_PIPEWIRE=1 (start a private pipewire).
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TOOLS=$ROOT/../tools
T=$(mktemp -d)
mkdir -p "$ROOT/dist"
echo "$T" > "$ROOT/dist/rig-dir-desktop"
LS=$TOOLS/layershell/root/usr/lib/aarch64-linux-gnu
export PATH="$TOOLS/dbus-dl/root/usr/bin:$ROOT/src/os/bin:$ROOT/../tools/wlclip/root/usr/bin:$PATH"
[ -d /tmp/claude-1000/wlc/root/usr/bin ] && export PATH="/tmp/claude-1000/wlc/root/usr/bin:$PATH"
export GI_TYPELIB_PATH="$LS/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export LD_LIBRARY_PATH="$LS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export AMERIKA_LAYERSHELL_LIB="$LS/libgtk4-layer-shell.so.0"
export XDG_RUNTIME_DIR="$T/runtime"
mkdir -m 0700 "$XDG_RUNTIME_DIR"
export XDG_CONFIG_HOME="$T/config" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" XDG_STATE_HOME="$T/state" HOME="$T/home"
export PYTHONPATH="$ROOT/src/os${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME/applications" "$XDG_STATE_HOME" "$HOME"
# The shell is authorised for KWin's screenshot interface by its desktop file (matched on the interpreter path).
PY=${AMERIKA_SHELL_HOST:-$(readlink -f "$(command -v python3)")}
cat > "$XDG_DATA_HOME/applications/org.amerika.Shell.desktop" <<EOD
[Desktop Entry]
Type=Application
Name=Amerika Shell (rig)
Exec=$PY %U
NoDisplay=true
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
EOD
export T RIG_SCRIPT="$1"; shift; export RIG_ARGS="$*"
export DESKTOP_RIG_WAIT=${DESKTOP_RIG_WAIT:-4}
exec dbus-run-session -- sh -c '
  kwin_wayland --virtual --socket rig-desktop --width 1920 --height 1080 --no-lockscreen >"$T/kwin.log" 2>&1 &
  KW=$!
  sleep "$DESKTOP_RIG_WAIT"
  export WAYLAND_DISPLAY=rig-desktop GDK_BACKEND=wayland QT_QPA_PLATFORM=wayland
  if [ "${DESKTOP_RIG_PIPEWIRE:-0}" = 1 ] && command -v pipewire >/dev/null; then pipewire >"$T/pipewire.log" 2>&1 & PW=$!; sleep 1; fi
  sh -c "$RIG_SCRIPT $RIG_ARGS" >"$T/script.log" 2>&1
  RESULT=$?
  kill $KW 2>/dev/null
  [ -n "${PW:-}" ] && kill $PW 2>/dev/null
  exit $RESULT
' 2>"$T/dbus.log"
