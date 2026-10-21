# Launch an Electron app inside the rig with different environments to find what makes it exit.
# Usage: tools/kwin-rig.sh "sh tests/rig/launch_test.sh <command>"
APP=${RIG_ARGS:-claude-desktop}
LS=$AMERIKA_LAYERSHELL_LIB
try() {  # name, env assignments...
  name=$1; shift
  ( env "$@" $APP >$T/launch-$name.log 2>&1 & echo $! > $T/launch-$name.pid )
  sleep 9
  pid=$(cat $T/launch-$name.pid)
  if kill -0 $pid 2>/dev/null; then echo "$name: ALIVE after 9s"; kill $pid 2>/dev/null; else echo "$name: EXITED early"; fi
  sleep 2
}
unset LD_PRELOAD
try baseline X=1
try preload LD_PRELOAD=$LS
try desktop XDG_CURRENT_DESKTOP=Amerika XDG_SESSION_DESKTOP=Amerika
try gdkbackend GDK_BACKEND=wayland,x11 QT_QPA_PLATFORM=wayland MOZ_ENABLE_WAYLAND=1
