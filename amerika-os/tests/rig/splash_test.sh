# The startup screen appears, then leaves once the shell reports ready.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_SHARE=$ROOT/src/os/amerika AMERIKA_ICONS=$ROOT/src/os/icons AMERIKA_WALLPAPERS=$ROOT/src/os/wallpapers
export AMERIKA_SPLASH_SHOT=$ROOT/dist/splash-shot.png
rm -f $XDG_RUNTIME_DIR/amerika/shell-ready $AMERIKA_SPLASH_SHOT
$ROOT/src/os/bin/amerika-splash > $T/splash.log 2>&1 &
SP=$!
sleep 3
echo "splash running after 3s (shell not ready): $(kill -0 $SP 2>/dev/null && echo yes || echo no)"
mkdir -p $XDG_RUNTIME_DIR/amerika; echo ok > $XDG_RUNTIME_DIR/amerika/shell-ready
sleep 3
echo "splash running after ready file: $(kill -0 $SP 2>/dev/null && echo yes || echo no)"
rm -f $XDG_RUNTIME_DIR/amerika/shell-ready
kill $SP 2>/dev/null; true
