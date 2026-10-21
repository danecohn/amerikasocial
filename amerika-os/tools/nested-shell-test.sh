#!/bin/sh
# Runs the Amerika shell in a headless KWin on a PRIVATE D-Bus with throwaway config.
# It never touches the running desktop session. Needs dbus-run-session (dbus-daemon package).
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TR=$ROOT/dist/testroot
DBUSBIN=${DBUS_BIN:-$ROOT/../tools/dbus-dl/root/usr/bin}
T=$(mktemp -d)
echo "$T" > "$ROOT/dist/nested-test-dir"
export PATH="$DBUSBIN:$PATH"
export XDG_DATA_DIRS="$TR/usr/share:/usr/share"
export XDG_CONFIG_HOME="$T/config" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" XDG_STATE_HOME="$T/state"
export XDG_CONFIG_DIRS="$TR/etc/xdg:/etc/xdg"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
export QT_LOGGING_RULES="*.debug=true;qt.*=false;kf.kio*=false;kf.wallet*=false;org.kde.kded*=false;qt.qml*=false"
export SCRIPT_LIST T SHELL_ID=${SHELL_ID:-org.amerika.shell} WAIT=${WAIT:-16}
exec dbus-run-session -- sh -c '
  kwin_wayland --virtual --socket amtest --width 1920 --height 1080 --no-lockscreen >"$T/kwin.log" 2>&1 &
  KW=$!
  sleep 4
  export WAYLAND_DISPLAY=amtest QT_QPA_PLATFORM=wayland PLASMA_DEFAULT_SHELL=$SHELL_ID AMERIKA_SESSION=1
  plasmashell --no-respawn >"$T/plasmashell.log" 2>&1 &
  PS=$!
  sleep $WAIT
  echo "== config files"; ls "$T/config"
  echo "== bus names"; qdbus6 org.freedesktop.DBus / org.freedesktop.DBus.ListNames 2>&1 | grep -E "plasmashell|KWin" | head
  echo "== script test"
  for js in ${SCRIPTS:-"panels().length"}; do :; done
  echo "$SCRIPT_LIST" | while IFS= read -r js; do [ -n "$js" ] && { echo "> $js"; qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$js" 2>&1; }; done
  [ -n "${SHOT:-}" ] && qdbus6 org.kde.KWin /org/kde/KWin/ScreenShot2 org.kde.KWin.ScreenShot2.version 2>&1 | head -2
  echo "== plasmashell log"; grep -viE "propertyCache|portal|deprecated" "$T/plasmashell.log" | head -40
  kill $PS $KW 2>/dev/null
'
