# Super key, Copilot key and app launching, end to end inside the rig, using the build tree.
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_BIN=$ROOT/src/os/bin PATH=$ROOT/src/os/bin:$PATH
export AMERIKA_SHARE=$ROOT/src/os/amerika AMERIKA_ICONS=$ROOT/src/os/icons AMERIKA_WALLPAPERS=$ROOT/src/os/wallpapers AMERIKA_SCHEMES=$ROOT/src/os/color-schemes
dump() {
cat > $T/dump.js <<'JS'
var out=[];workspace.windowList().forEach(function(w){var g=w.frameGeometry;out.push(w.resourceClass+"|"+w.caption+"|"+Math.round(g.width)+"x"+Math.round(g.height));});
print("WINDOWS: "+out.join(" ;; "));
JS
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript $T/dump.js dumpwin$1 >/dev/null; qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.start >/dev/null; sleep 1
grep "WINDOWS" $T/kwin.log | tail -1 | cut -c1-500
}
action() { gdbus call --session --dest org.amerika.Shell --object-path /Control --method org.amerika.Control.Action "$1" >/dev/null 2>&1; }
sh $ROOT/src/os/session/session-start > $T/session.log 2>&1 &
SS=$!
sleep 9
echo "META after start: $(kreadconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta)"
echo "== Action ai1 (Claude)"; action ai1; sleep 14
echo "claude processes: $(pgrep -fc 'claude-desktop' )"
dump a
echo "== Action copilot (default: claude, already running -> focus)"; action copilot; sleep 3; echo "claude processes: $(pgrep -fc 'claude-desktop')"
echo "== copilot_app=ask -> picker"
python3 - <<'PY'
from amerika import common
s=common.load_settings(); s['copilot_app']='ask'; common.save_settings(s)
PY
sleep 2; action copilot; sleep 3; dump b
echo "== Action launcher (toggle closes the picker)"; action launcher; sleep 2; dump c
kill $SS; sleep 3
echo "META after exit: [$(kreadconfig6 --file kwinrc --group ModifierOnlyShortcuts --key Meta)]"
pkill -x claude-desktop 2>/dev/null; true
