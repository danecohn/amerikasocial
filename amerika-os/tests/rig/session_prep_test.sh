# amerika-session's preparation for KWin (Super key binding, Copilot key layout), with a stand-in for kwin_wayland.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cat > $T/fake-kwin <<'EOF'
#!/bin/sh
echo "FAKE-KWIN args: $*"
echo "XKB_CONFIG_EXTRA_PATH=$XKB_CONFIG_EXTRA_PATH"
echo "META-BINDING=$(kreadconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta)"
EOF
chmod +x $T/fake-kwin
# pretend the user had Plasma's own binding before
kwriteconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta "org.kde.plasmashell,/PlasmaShell,org.kde.PlasmaShell,activateLauncherMenu"
AMERIKA_KWIN=$T/fake-kwin AMERIKA_LIBEXEC=$ROOT/src/os/session sh $ROOT/src/os/session/amerika-session
echo "SAVED=$(cat $XDG_STATE_HOME/amerika-os/meta-shortcut.saved)"
cat $XDG_RUNTIME_DIR/amerika/xkb/symbols/inet 2>/dev/null | grep -c "FK23.*F23 \] };"
# end of session: restore
AMERIKA_BIN=/nonexistent sh -c '. /dev/null; true'
sh $ROOT/src/os/session/amerika-restore-meta
echo "AFTER-RESTORE-REPAIR=$(kreadconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta)"
