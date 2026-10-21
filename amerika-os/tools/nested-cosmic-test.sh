#!/bin/sh
# Runs the Amerika COSMIC layout nested inside the current Wayland session, on a PRIVATE D-Bus with throwaway
# XDG directories. It never touches the running desktop session or the real ~/.config/cosmic.
# Needs: dist/cosmicroot (extracted COSMIC debs), dist/testroot (extracted Amerika debs), libseat1 and dbus-run-session.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CR=$ROOT/dist/cosmicroot
AR=$ROOT/dist/testroot
T=$(mktemp -d)
echo "$T" > "$ROOT/dist/nested-test-dir"
export PATH="$CR/usr/bin:$AR/usr/bin:$ROOT/../tools/dbus-dl/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$ROOT/../tools/libseat/root/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
export XDG_DATA_DIRS="$CR/usr/share:$AR/usr/share:/usr/share"
export XDG_CONFIG_HOME="$T/config" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" XDG_STATE_HOME="$T/state"
export HOME="$T/home" AMERIKA_SESSION=1 AMERIKA_COSMIC_SRC="$AR/usr/share/amerika-os/cosmic"
export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC XDG_SESSION_TYPE=wayland
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME"
export T HOSTWL="$WAYLAND_DISPLAY" WAIT=${WAIT:-25} CR
exec dbus-run-session -- sh -c '
  sh "'$AR'/usr/bin/amerika-cosmic-seed"
  # the wallpaper lives under /usr/share when installed; point at the extracted tree for this test
  sed -i "s|\"/usr/share/backgrounds|\"'$AR'/usr/share/backgrounds|" "$XDG_CONFIG_HOME/cosmic/com.system76.CosmicBackground/v1/all"
  ls "$XDG_CONFIG_HOME/cosmic" | tr "\n" " "; echo
  # remove stale sockets left by an earlier run of this test (only when no COSMIC compositor is running)
  if ! pgrep -x cosmic-comp >/dev/null; then
    for s in $(ls "$XDG_RUNTIME_DIR" | grep "^wayland-[0-9]*\(\.lock\)\?$" | grep -v "^$HOSTWL\(\.lock\)\?$"); do rm -f "$XDG_RUNTIME_DIR/$s"; done
  fi
  cosmic-comp >"$T/comp.log" 2>&1 &
  CP=$!
  sleep 6
  sock=$(ls -t "$XDG_RUNTIME_DIR" | grep "^wayland-[0-9]*$" | grep -vx "$HOSTWL" | head -1)
  echo "nested socket: ${sock:-none}"
  [ -n "$sock" ] || { tail -5 "$T/comp.log"; kill $CP; exit 1; }
  export WAYLAND_DISPLAY=$sock
  cosmic-bg >"$T/bg.log" 2>&1 & BG=$!
  cosmic-settings-daemon >"$T/sd.log" 2>&1 & SD=$!
  cosmic-panel >"$T/panel.log" 2>&1 & PN=$!
  sleep $WAIT
  echo "== running processes (children of this test)"; ps -o pid,args --ppid $PN | cut -c1-110; ps -o pid,args -p $CP,$BG,$SD,$PN | cut -c1-100
  echo "== panel log"; grep -viE "debug|trace" "$T/panel.log" | head -20 | cut -c1-200
  echo "== comp log tail"; tail -4 "$T/comp.log" | cut -c1-200
  echo "== bg log"; head -5 "$T/bg.log" | cut -c1-200
  kill $PN $BG $SD $CP 2>/dev/null
'
