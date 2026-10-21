// Amerika window bridge (KWin script). Pushes the window list to the shell whenever it changes.
// Loaded by amerika-shell through org.kde.KWin /Scripting. Commands are sent as one-shot scripts (see windows.py).
var SERVICE = "org.amerika.Shell", PATH = "/Windows", IFACE = "org.amerika.Windows";
var pending = false;

function describe(w) {
    var g = w.frameGeometry;
    return {
        id: String(w.internalId), caption: w.caption, cls: w.resourceClass, desktopFile: w.desktopFileName,
        pid: w.pid, x: Math.round(g.x), y: Math.round(g.y), w: Math.round(g.width), h: Math.round(g.height),
        active: workspace.activeWindow === w, minimized: !!w.minimized, fullscreen: !!w.fullScreen,
        normal: !!w.normalWindow, dock: !!w.dock, skip: !!(w.skipTaskbar || w.skipPager),
        desktops: (w.desktops || []).map(function (d) { return d.x11DesktopNumber; })
    };
}

function report() {
    pending = false;
    var list = workspace.windowList().filter(function (w) { return w.normalWindow || w.dock; }).map(describe);
    var screens = workspace.screens.map(function (s) {
        var a = workspace.clientArea(KWin.PlacementArea, s, workspace.currentDesktop);
        return { name: s.name, x: s.geometry.x, y: s.geometry.y, w: s.geometry.width, h: s.geometry.height,
                 work: { x: a.x, y: a.y, w: a.width, h: a.height } };
    });
    var desktops = workspace.desktops.map(function (d) { return { n: d.x11DesktopNumber, name: d.name }; });
    callDBus(SERVICE, PATH, IFACE, "Report", JSON.stringify({
        windows: list, screens: screens, desktops: desktops, current: workspace.currentDesktop.x11DesktopNumber
    }));
}

function schedule() { if (!pending) { pending = true; report(); } else { report(); } }

function watch(w) {
    ["captionChanged", "minimizedChanged", "fullScreenChanged", "desktopsChanged", "frameGeometryChanged"].forEach(function (s) {
        if (w[s] && w[s].connect) w[s].connect(schedule);
    });
}

workspace.windowAdded.connect(function (w) { watch(w); schedule(); });
workspace.windowRemoved.connect(schedule);
workspace.windowActivated.connect(schedule);
workspace.currentDesktopChanged.connect(schedule);
workspace.windowList().forEach(watch);
report();

// ---- global shortcuts (registered through KWin, so they work everywhere in the session)
function control(name) { callDBus(SERVICE, "/Control", "org.amerika.Control", "Action", name); }
registerShortcut("Amerika: Launcher (Windows key)", "Tap the Windows key to open the launcher", "Meta", function () { control("launcher"); });
registerShortcut("Amerika: Launcher", "Open the launcher", "Meta+Space", function () { control("launcher"); });
registerShortcut("Amerika: First AI app", "Open or focus the first AI app", "Meta+1", function () { control("ai1"); });
registerShortcut("Amerika: Second AI app", "Open or focus the second AI app", "Meta+2", function () { control("ai2"); });
registerShortcut("Amerika: Copilot key", "Open the AI app chosen for the Copilot key", "Meta+Shift+F23", function () { control("copilot"); });
registerShortcut("Amerika: Settings", "Open Amerika Settings", "Meta+,", function () { control("settings"); });
registerShortcut("Amerika: Lock screen", "Lock the screen", "Meta+L", function () { control("lock"); });
registerShortcut("Amerika: Stop AI actions", "Pause or resume everything the AI apps are doing", "Ctrl+Alt+Escape", function () { control("stop"); });
registerShortcut("Amerika: Close window", "Close the active window", "Meta+Q", function () { if (workspace.activeWindow && workspace.activeWindow.normalWindow) workspace.activeWindow.closeWindow(); });
function tile(side) {
    var w = workspace.activeWindow; if (!w || !w.normalWindow) return;
    var a = workspace.clientArea(KWin.MaximizeArea, w); var g = { x: a.x, y: a.y, width: a.width, height: a.height };
    if (side === "left") g.width = a.width / 2; else { g.x = a.x + a.width / 2; g.width = a.width / 2; }
    w.setMaximize(false, false); w.frameGeometry = g;
}
registerShortcut("Amerika: Tile left", "Snap the window to the left half", "Meta+Left", function () { tile("left"); });
registerShortcut("Amerika: Tile right", "Snap the window to the right half", "Meta+Right", function () { tile("right"); });
registerShortcut("Amerika: Maximize", "Maximize the window", "Meta+Up", function () { var w = workspace.activeWindow; if (w && w.normalWindow) w.setMaximize(true, true); });
registerShortcut("Amerika: Restore", "Restore the window", "Meta+Down", function () { var w = workspace.activeWindow; if (w && w.normalWindow) w.setMaximize(false, false); });
