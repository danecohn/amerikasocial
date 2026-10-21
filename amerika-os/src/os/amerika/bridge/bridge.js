// Amerika window bridge (KWin script). Pushes the window list to the shell whenever it changes.
// Loaded by amerika-shell through org.kde.KWin /Scripting. Commands are sent as one-shot scripts (see windows.py).
var SERVICE = "org.amerika.Shell", PATH = "/Windows", IFACE = "org.amerika.Windows";
var pending = false;
var mru = [];                 // window ids, most recently activated first (the Alt+Tab order)
var CFG = { locked: false, corners: {}, touch_edges: {}, snap_gaps: 0 };   // pushed by the shell (org.amerika.Desktop.Config)

function id(w) { return String(w.internalId); }

function maxArea(w) { return workspace.clientArea(KWin.MaximizeArea, w); }

function describe(w) {
    var g = w.frameGeometry, a = maxArea(w);
    var full = Math.abs(g.width - a.width) < 3 && Math.abs(g.height - a.height) < 3;
    return {
        id: id(w), caption: w.caption, cls: w.resourceClass, desktopFile: w.desktopFileName,
        pid: w.pid, x: Math.round(g.x), y: Math.round(g.y), w: Math.round(g.width), h: Math.round(g.height),
        active: workspace.activeWindow === w, minimized: !!w.minimized, fullscreen: !!w.fullScreen,
        normal: !!w.normalWindow, dock: !!w.dock, skip: !!(w.skipTaskbar || w.skipPager),
        desktops: (w.desktops || []).map(function (d) { return d.x11DesktopNumber; }),
        allDesktops: !!w.onAllDesktops, above: !!w.keepAbove, maximized: full && !w.fullScreen,
        closeable: !!w.closeable, screen: w.output ? w.output.name : ""
    };
}

function report() {
    pending = false;
    var list = workspace.windowList().filter(function (w) { return w.normalWindow || w.dock; }).map(describe);
    var stack = workspace.stackingOrder.map(id);
    list.forEach(function (d) { d.z = stack.indexOf(d.id); });
    var screens = workspace.screens.map(function (s) {
        var a = workspace.clientArea(KWin.PlacementArea, s, workspace.currentDesktop);
        return { name: s.name, x: s.geometry.x, y: s.geometry.y, w: s.geometry.width, h: s.geometry.height,
                 work: { x: a.x, y: a.y, w: a.width, h: a.height } };
    });
    var desktops = workspace.desktops.map(function (d) { return { n: d.x11DesktopNumber, name: d.name, id: d.id }; });
    var cur = workspace.cursorPos;
    callDBus(SERVICE, PATH, IFACE, "Report", JSON.stringify({
        windows: list, screens: screens, desktops: desktops, current: workspace.currentDesktop.x11DesktopNumber,
        mru: mru.slice(0, 64), activeScreen: workspace.activeScreen ? workspace.activeScreen.name : "",
        cursor: { x: Math.round(cur.x), y: Math.round(cur.y) }
    }));
}

function schedule() { if (!pending) { pending = true; report(); } else { report(); } }

function touch(w) {
    var i = id(w), at = mru.indexOf(i);
    if (at >= 0) mru.splice(at, 1);
    mru.unshift(i);
}

function watch(w) {
    ["captionChanged", "minimizedChanged", "fullScreenChanged", "desktopsChanged", "frameGeometryChanged", "keepAboveChanged"].forEach(function (s) {
        if (w[s] && w[s].connect) w[s].connect(schedule);
    });
}

workspace.windowAdded.connect(function (w) { watch(w); if (w.normalWindow) mru.push(id(w)); schedule(); });
workspace.windowRemoved.connect(function (w) { var at = mru.indexOf(id(w)); if (at >= 0) mru.splice(at, 1); schedule(); });
workspace.windowActivated.connect(function (w) { if (w && w.normalWindow) touch(w); schedule(); });
workspace.currentDesktopChanged.connect(schedule);
if (workspace.desktopsChanged && workspace.desktopsChanged.connect) workspace.desktopsChanged.connect(schedule);
workspace.windowList().forEach(watch);
workspace.stackingOrder.forEach(function (w) { if (w.normalWindow) mru.unshift(id(w)); });
report();

// ---- global shortcuts (registered through KWin, so they work everywhere in the session)
function control(name) { callDBus(SERVICE, "/Control", "org.amerika.Control", "Action", name); }
// Everything below is ignored while the shell's lock screen is up (CFG.locked is pushed by the shell, which reloads this script).
function guard(fn) { return function () { if (!CFG.locked) fn(); }; }
function key(title, text, seq, fn) { registerShortcut(title, text, seq, guard(fn)); }
function act(title, text, seq, name) { key(title, text, seq, function () { control(name); }); }
function active() { var w = workspace.activeWindow; return (w && w.normalWindow) ? w : null; }

act("Amerika: Launcher (Windows key)", "Tap the Windows key to open the launcher", "Meta", "launcher");
act("Amerika: Launcher", "Open the launcher", "Meta+Space", "launcher");
act("Amerika: First AI app", "Open or focus the first AI app", "Meta+1", "ai1");
act("Amerika: Second AI app", "Open or focus the second AI app", "Meta+2", "ai2");
act("Amerika: Copilot key", "Open the AI app chosen for the Copilot key", "Meta+Shift+F23", "copilot");
act("Amerika: Settings", "Open Amerika Settings", "Meta+,", "settings");
act("Amerika: Agent", "Open Amerika Agent", "Meta+A", "agent");
act("Amerika: Lock screen", "Lock the screen", "Meta+L", "lock");
act("Amerika: Stop AI actions", "Pause or resume everything the AI apps are doing", "Ctrl+Alt+Escape", "stop");
key("Amerika: Close window", "Close the active window", "Meta+Q", function () { var w = active(); if (w) w.closeWindow(); });

// ---- snapping / tiling zones (Meta+arrows are the classic half/maximize keys; Meta+Alt+... the extra zones)
function zoneGeometry(zone, a) {
    var x = a.x, y = a.y, W = a.width, H = a.height, hw = W / 2, hh = H / 2, t = W / 3;
    var z = {
        "left": [x, y, hw, H], "right": [x + hw, y, hw, H], "top": [x, y, W, hh], "bottom": [x, y + hh, W, hh],
        "top-left": [x, y, hw, hh], "top-right": [x + hw, y, hw, hh], "bottom-left": [x, y + hh, hw, hh],
        "bottom-right": [x + hw, y + hh, hw, hh], "third-left": [x, y, t, H], "third-center": [x + t, y, t, H],
        "third-right": [x + 2 * t, y, t, H], "center": [x + W * 0.15, y + H * 0.1, W * 0.7, H * 0.8], "full": [x, y, W, H]
    }[zone];
    if (!z) return null;
    var gap = CFG.snap_gaps || 0;
    return { x: Math.round(z[0] + gap), y: Math.round(z[1] + gap), width: Math.round(z[2] - 2 * gap), height: Math.round(z[3] - 2 * gap) };
}
function snap(zone) {
    var w = active(); if (!w || !w.resizeable) return;
    var g = zoneGeometry(zone, maxArea(w)); if (!g) return;
    if (zone === "full") { w.setMaximize(true, true); return; }
    w.setMaximize(false, false); w.frameGeometry = g;
}
function sameGeometry(w, zone) {
    var g = zoneGeometry(zone, maxArea(w)), f = w.frameGeometry;
    return g && Math.abs(f.x - g.x) < 4 && Math.abs(f.y - g.y) < 4 && Math.abs(f.width - g.width) < 4 && Math.abs(f.height - g.height) < 4;
}
function toScreen(step) {
    var w = active(); if (!w || workspace.screens.length < 2) return;
    var screens = workspace.screens, at = 0;
    screens.forEach(function (s, i) { if (w.output && s.name === w.output.name) at = i; });
    var next = screens[(at + step + screens.length) % screens.length];
    workspace.sendClientToScreen(w, next);
}
key("Amerika: Tile left", "Snap the window to the left half", "Meta+Left", function () {
    var w = active(); if (!w) return;
    if (sameGeometry(w, "left")) { snap("third-left"); } else { snap("left"); }
});
key("Amerika: Tile right", "Snap the window to the right half", "Meta+Right", function () {
    var w = active(); if (!w) return;
    if (sameGeometry(w, "right")) { snap("third-right"); } else { snap("right"); }
});
key("Amerika: Maximize", "Maximize the window", "Meta+Up", function () { snap("full"); });
key("Amerika: Restore", "Restore the window (a second press minimizes it)", "Meta+Down", function () {
    var w = active(); if (!w) return;
    var g = maxArea(w), f = w.frameGeometry;
    if (Math.abs(f.width - g.width) < 3 && Math.abs(f.height - g.height) < 3 || w.fullScreen) { w.fullScreen = false; w.setMaximize(false, false); }
    else if (sameGeometry(w, "left") || sameGeometry(w, "right")) { w.setMaximize(false, false); snap("center"); }
    else { w.minimized = true; }
});
[["Meta+Alt+U", "top-left"], ["Meta+Alt+I", "top-right"], ["Meta+Alt+J", "bottom-left"], ["Meta+Alt+K", "bottom-right"],
 ["Meta+Alt+D", "third-left"], ["Meta+Alt+F", "third-center"], ["Meta+Alt+G", "third-right"], ["Meta+Alt+C", "center"],
 ["Meta+Alt+Up", "top"], ["Meta+Alt+Down", "bottom"]].forEach(function (z) {
    key("Amerika: Snap " + z[1], "Snap the window to the " + z[1] + " zone", z[0], function () { snap(z[1]); });
});
key("Amerika: Window to next screen", "Move the window to the next screen", "Meta+Shift+Right", function () { toScreen(1); });
key("Amerika: Window to previous screen", "Move the window to the previous screen", "Meta+Shift+Left", function () { toScreen(-1); });
key("Amerika: Always on top", "Keep the window above others", "Meta+Shift+T", function () { var w = active(); if (w) w.keepAbove = !w.keepAbove; });
key("Amerika: Window on all desktops", "Show the window on every desktop", "Meta+Shift+A", function () { var w = active(); if (w) w.onAllDesktops = !w.onAllDesktops; });
key("Amerika: Minimize window", "Minimize the active window", "Meta+M", function () { var w = active(); if (w) w.minimized = true; });

// ---- show desktop: minimize everything on this desktop, or bring it back
var hidden = [];
key("Amerika: Show desktop", "Minimize all windows, or restore them", "Meta+D", function () {
    var here = workspace.windowList().filter(function (w) { return w.normalWindow && !w.minimized && !w.skipTaskbar; });
    if (here.length) { hidden = here.map(id); here.forEach(function (w) { w.minimized = true; }); return; }
    workspace.windowList().forEach(function (w) { if (hidden.indexOf(id(w)) >= 0) w.minimized = false; });
    hidden = [];
});

// ---- virtual desktops: Ctrl+Alt+1..9 (Meta+1/2 stay the AI shortcuts), Meta+Ctrl+arrows, move window with Shift
function desktopAt(n) { return workspace.desktops[n - 1]; }
function relativeDesktop(step) {
    var list = workspace.desktops, at = list.indexOf(workspace.currentDesktop);
    for (var i = 0; i < list.length; i++) if (list[i] === workspace.currentDesktop) at = i;
    var n = at + step;
    if (n < 0 || n >= list.length) n = (n + list.length) % list.length;
    return list[n];
}
for (var n = 1; n <= 9; n++) {
    (function (n) {
        key("Amerika: Desktop " + n, "Switch to virtual desktop " + n, "Ctrl+Alt+" + n, function () { var d = desktopAt(n); if (d) workspace.currentDesktop = d; });
        key("Amerika: Move window to desktop " + n, "Send the window to virtual desktop " + n, "Ctrl+Alt+Shift+" + n, function () {
            var w = active(), d = desktopAt(n); if (w && d) w.desktops = [d];
        });
    })(n);
}
key("Amerika: Previous desktop", "Switch to the previous virtual desktop", "Meta+Ctrl+Left", function () { workspace.currentDesktop = relativeDesktop(-1); });
key("Amerika: Next desktop", "Switch to the next virtual desktop", "Meta+Ctrl+Right", function () { workspace.currentDesktop = relativeDesktop(1); });
key("Amerika: Window to previous desktop", "Move the window to the previous desktop and follow it", "Meta+Ctrl+Shift+Left", function () {
    var w = active(), d = relativeDesktop(-1); if (w && d) { w.desktops = [d]; workspace.currentDesktop = d; workspace.activeWindow = w; }
});
key("Amerika: Window to next desktop", "Move the window to the next desktop and follow it", "Meta+Ctrl+Shift+Right", function () {
    var w = active(), d = relativeDesktop(1); if (w && d) { w.desktops = [d]; workspace.currentDesktop = d; workspace.activeWindow = w; }
});
act("Amerika: Overview", "Show every window on every desktop", "Meta+Tab", "overview");
act("Amerika: Overview (Ctrl+Meta+Up)", "Show every window on every desktop", "Meta+Ctrl+Up", "overview");

// ---- window switcher: the shell draws it; these keys only tell it to start or step (it watches the Alt key itself)
act("Amerika: Switch windows", "Alt+Tab window switcher", "Alt+Tab", "switcher:next");
act("Amerika: Switch windows (reverse)", "Reverse window switcher", "Alt+Shift+Tab", "switcher:prev");
act("Amerika: Switch windows (reverse, Backtab)", "Reverse window switcher", "Alt+Shift+Backtab", "switcher:prev");
act("Amerika: Switch windows of this app", "Cycle through the windows of the current app", "Alt+`", "switcher:app-next");

// ---- clipboard history, screenshots, recording
act("Amerika: Clipboard history", "Open the clipboard history", "Meta+V", "clipboard");
act("Amerika: Screenshot", "Capture a region, window or screen", "Print", "screenshot:region");
act("Amerika: Screenshot (region)", "Capture a region of the screen", "Meta+Shift+S", "screenshot:region");
act("Amerika: Screenshot (window)", "Capture a window", "Shift+Print", "screenshot:window");
act("Amerika: Screenshot (screen)", "Capture the whole screen", "Ctrl+Print", "screenshot:screen");
act("Amerika: Screen recording", "Start or stop a screen recording", "Meta+Shift+R", "record:toggle");
act("Amerika: Calendar", "Open the calendar and clock", "Meta+C", "calendar");

// ---- hardware keys (the shell does the work and shows an on-screen display)
act("Amerika: Volume up", "Raise the volume", "Volume Up", "osd:volume-up");
act("Amerika: Volume down", "Lower the volume", "Volume Down", "osd:volume-down");
act("Amerika: Volume mute", "Mute or unmute", "Volume Mute", "osd:volume-mute");
act("Amerika: Microphone mute", "Mute or unmute the microphone", "Mic Mute", "osd:mic-mute");
act("Amerika: Brightness up", "Raise the screen brightness", "Monitor Brightness Up", "osd:brightness-up");
act("Amerika: Brightness down", "Lower the screen brightness", "Monitor Brightness Down", "osd:brightness-down");
act("Amerika: Keyboard backlight up", "Raise the keyboard backlight", "Keyboard Brightness Up", "osd:kbd-up");
act("Amerika: Keyboard backlight down", "Lower the keyboard backlight", "Keyboard Brightness Down", "osd:kbd-down");
act("Amerika: Play/pause", "Play or pause the current media", "Toggle Media Play/Pause", "media:play-pause");
act("Amerika: Play", "Play the current media", "Media Play", "media:play-pause");
act("Amerika: Next track", "Next track", "Media Next", "media:next");
act("Amerika: Previous track", "Previous track", "Media Previous", "media:previous");
act("Amerika: Stop media", "Stop the current media", "Media Stop", "media:stop");

// ---- hot corners and touch screen edges: configured in Settings, pushed by the shell
var EDGES = { topleft: "ElectricTopLeft", topright: "ElectricTopRight", bottomleft: "ElectricBottomLeft", bottomright: "ElectricBottomRight",
              top: "ElectricTop", bottom: "ElectricBottom", left: "ElectricLeft", right: "ElectricRight" };
function applyConfig(cfg) {
    CFG = cfg;
    Object.keys(cfg.corners || {}).forEach(function (name) {
        if (!EDGES[name] || KWin[EDGES[name]] === undefined) return;
        registerScreenEdge(KWin[EDGES[name]], function () { if (!CFG.locked) control("corner:" + name); });
    });
    Object.keys(cfg.touch_edges || {}).forEach(function (name) {
        if (!EDGES[name] || KWin[EDGES[name]] === undefined || typeof registerTouchScreenEdge !== "function") return;
        registerTouchScreenEdge(KWin[EDGES[name]], function () { if (!CFG.locked) control("touch:" + name); });
    });
}
callDBus(SERVICE, "/Desktop", "org.amerika.Desktop", "Config", function (json) {
    try { applyConfig(JSON.parse(json)); } catch (e) { print("amerika: bad desktop config: " + e); }
});
