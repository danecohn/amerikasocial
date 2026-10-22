#!/bin/sh
# Private KWin rig for the Claude-first shell tests: own Wayland socket (rig-claude-os) and rig-dir file so it never collides with
# other rigs. Fake claude-desktop / chatgpt apps (tests/rig/claude_os_fake/bin) come first on PATH and their .desktop entries are
# installed into the throwaway XDG_DATA_HOME. Usage: claude_os_rig.sh "<command>"   (the command runs with WAYLAND_DISPLAY set)
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TOOLS=$ROOT/../tools
T=$(mktemp -d)
mkdir -p "$ROOT/dist/claude-os"
echo "$T" > "$ROOT/dist/claude-os/rig-dir"
LS=$TOOLS/layershell/root/usr/lib/aarch64-linux-gnu
export PATH="$ROOT/tests/rig/claude_os_fake/bin:$TOOLS/dbus-dl/root/usr/bin:$ROOT/src/os/bin:$PATH"
export GI_TYPELIB_PATH="$LS/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export LD_LIBRARY_PATH="$LS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export AMERIKA_LAYERSHELL_LIB="$LS/libgtk4-layer-shell.so.0"
export XDG_RUNTIME_DIR="$T/runtime"
mkdir -m 0700 "$XDG_RUNTIME_DIR"
export XDG_CONFIG_HOME="$T/config" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" XDG_STATE_HOME="$T/state" HOME="$T/home"
export PYTHONPATH="$ROOT/src/os${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME/applications" "$XDG_STATE_HOME" "$HOME"
cp "$ROOT"/src/os/applications/*.desktop "$XDG_DATA_HOME/applications/" 2>/dev/null
# fake AI apps: same ids and Exec lines as the real entries (the real apps are never started in the rig)
cat > "$XDG_DATA_HOME/applications/com.anthropic.Claude.desktop" <<EOD
[Desktop Entry]
Name=Claude
Exec=claude-desktop %U
Icon=amerika-ai
Type=Application
StartupWMClass=com.anthropic.Claude
Categories=Utility;Development;
Actions=NewChat;
[Desktop Action NewChat]
Name=New Chat
Exec=claude-desktop "claude://claude.ai/new"
EOD
cat > "$XDG_DATA_HOME/applications/chatgpt.desktop" <<EOD
[Desktop Entry]
Name=ChatGPT
Exec=chatgpt %U
Icon=amerika-ai
Type=Application
Categories=Utility;Development;
EOD
export XDG_DATA_DIRS="$XDG_DATA_HOME:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
# the shell is authorised for KWin's screenshot interface by its desktop file (matched on the interpreter path)
if [ -z "${AMERIKA_SHELL_HOST:-}" ]; then
  for c in /usr/libexec/amerika/amerika-shell-host "$ROOT/dist/amerika-shell-host"; do [ -x "$c" ] && AMERIKA_SHELL_HOST=$c && break; done
fi
export AMERIKA_SHELL_HOST="${AMERIKA_SHELL_HOST:-}"
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
export CLAUDE_OS_RIG_WAIT=${CLAUDE_OS_RIG_WAIT:-4}
exec dbus-run-session -- sh -c '
  kwin_wayland --virtual --socket rig-claude-os --width 1920 --height 1080 --no-lockscreen >"$T/kwin.log" 2>&1 &
  KW=$!
  sleep "$CLAUDE_OS_RIG_WAIT"
  export WAYLAND_DISPLAY=rig-claude-os GDK_BACKEND=wayland QT_QPA_PLATFORM=wayland
  sh -c "$RIG_SCRIPT $RIG_ARGS" >"$T/script.log" 2>&1
  RESULT=$?
  cat "$T/script.log"
  kill $KW 2>/dev/null
  exit $RESULT
' 2>"$T/dbus.log"
