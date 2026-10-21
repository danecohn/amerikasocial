# The shell's keyboard shortcuts are registered with KWin under the expected key codes, and amerika-session prepares the layout.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_SHARE=$ROOT/src/os/amerika AMERIKA_ICONS=$ROOT/src/os/icons AMERIKA_WALLPAPERS=$ROOT/src/os/wallpapers
$ROOT/src/os/bin/amerika-shell > $T/shell.log 2>&1 &
SP=$!
sleep 12
info=$(qdbus6 --literal org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.allShortcutInfos 2>&1)
check() { # name, expected key code
  code=$(printf '%s' "$info" | grep -oE '"Amerika[^"]*", "[^"]*", "kwin"[^]]*\], \[Argument: ai \{[0-9, ]*\}\]' | grep -F "\"$1\"," | sed -n 's/.*Default Context", \[Argument: ai {\([0-9, ]*\)}\].*/\1/p' | head -1)
  [ "$code" = "$2" ] && echo "PASS $1 -> $2" || echo "FAIL $1 -> '$code' (expected $2)"
}
check "Amerika: Launcher (Windows key)" 16777250        # Qt::Key_Meta: tap the Windows key
check "Amerika: Launcher" 268435488                     # Meta+Space
check "Amerika: Copilot key" 318767174                  # Meta+Shift+F23
check "Amerika: Settings" 268435500                     # Meta+,
check "Amerika: Stop AI actions" 218103808              # Ctrl+Alt+Esc
kill $SP 2>/dev/null
# amerika-session: layout override handed to KWin, and no kwinrc side effects
cat > $T/fake-kwin <<'EOF'
#!/bin/sh
echo "XKB_CONFIG_EXTRA_PATH=$XKB_CONFIG_EXTRA_PATH"
echo "KWINRC-META=[$(kreadconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta)]"
EOF
chmod +x $T/fake-kwin
AMERIKA_KWIN=$T/fake-kwin AMERIKA_LIBEXEC=$ROOT/src/os/session sh $ROOT/src/os/session/amerika-session
grep -c "FK23.*F23 \] };" $XDG_RUNTIME_DIR/amerika/xkb/symbols/inet | sed 's/^/override lines with F23: /'
