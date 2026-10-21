"""Virtual desktops and window management: desktop manager (KWin D-Bus), pager, window menu, snap zones, KWin options.

Windows are controlled through the bridge's one-shot scripts (windows.py); desktops through KWin's own
org.kde.KWin.VirtualDesktopManager, so names and counts are saved by KWin itself (kwinrc [Desktops]) and survive restarts.
"""
import json
import subprocess

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from . import dutil

KWIN = 'org.kde.KWin'
VDM_PATH, VDM_IFACE = '/VirtualDesktopManager', 'org.kde.KWin.VirtualDesktopManager'
MAX_DESKTOPS = 20
FOCUS_VALUES = {'click': 'ClickToFocus', 'follow': 'FocusFollowsMouse', 'follow-strict': 'FocusStrictlyUnderMouse'}
ZONES = ('left', 'right', 'top', 'bottom', 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'third-left',
         'third-center', 'third-right', 'center', 'full')


# ---------------------------------------------------------------------------------------------------------- snap math
def zone_geometry(zone, area, gap=0):
    """Rectangle (x, y, w, h) of a snap zone inside `area` = (x, y, w, h). Mirrors bridge.js zoneGeometry."""
    x, y, w, h = area
    hw, hh, t = w / 2, h / 2, w / 3
    table = {
        'left': (x, y, hw, h), 'right': (x + hw, y, hw, h), 'top': (x, y, w, hh), 'bottom': (x, y + hh, w, hh),
        'top-left': (x, y, hw, hh), 'top-right': (x + hw, y, hw, hh), 'bottom-left': (x, y + hh, hw, hh),
        'bottom-right': (x + hw, y + hh, hw, hh), 'third-left': (x, y, t, h), 'third-center': (x + t, y, t, h),
        'third-right': (x + 2 * t, y, t, h), 'center': (x + w * 0.15, y + h * 0.1, w * 0.7, h * 0.8), 'full': (x, y, w, h),
    }
    if zone not in table:
        raise ValueError('unknown snap zone')
    gx, gy, gw, gh = table[zone]
    return round(gx + gap), round(gy + gap), round(gw - 2 * gap), round(gh - 2 * gap)


def desktops_of(state):
    """Normalised desktop list from a bridge report: [{'n', 'name', 'id', 'windows', 'current'}]."""
    cur = state.get('current', 1)
    out = []
    for d in state.get('desktops', []):
        count = sum(1 for w in state.get('windows', [])
                    if w.get('normal') and not w.get('skip') and (w.get('allDesktops') or d['n'] in w.get('desktops', [])))
        out.append({'n': d['n'], 'name': d.get('name') or f"Desktop {d['n']}", 'id': d.get('id', ''), 'windows': count,
                    'current': d['n'] == cur})
    return out


# ---------------------------------------------------------------------------------------------------------- KWin options
class KWinOptions:
    """Writes kwinrc through kwriteconfig6 and asks KWin to reload; `runner` is injectable for tests."""

    def __init__(self, bus=None, runner=None):
        self.bus = bus
        self.runner = runner or self._run

    @staticmethod
    def _run(argv):
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=4).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 127

    def write(self, group, key, value, kind=None):
        argv = ['kwriteconfig6', '--file', 'kwinrc', '--group', group, '--key', key]
        if kind:
            argv += ['--type', kind]
        return self.runner(argv + [str(value).lower() if isinstance(value, bool) else str(value)])

    def reconfigure(self):
        try:
            bus = self.bus or Gio.bus_get_sync(Gio.BusType.SESSION)
            bus.call_sync(KWIN, '/KWin', 'org.kde.KWin', 'reconfigure', None, None, Gio.DBusCallFlags.NONE, 2000, None)
            return True
        except GLib.Error:
            return False

    def set_focus_policy(self, policy):
        if policy not in FOCUS_VALUES:
            raise ValueError('focus policy must be click, follow or follow-strict')
        self.write('Windows', 'FocusPolicy', FOCUS_VALUES[policy])
        self.write('Windows', 'AutoRaise', 'false', 'bool')
        return self.reconfigure()

    def set_quick_tile(self, on):
        """KWin's own drag-to-edge snapping with its translucent preview overlay (left/right edge: half, top edge: maximize)."""
        self.write('Windows', 'ElectricBorderTiling', bool(on), 'bool')
        self.write('Windows', 'ElectricBorderMaximize', bool(on), 'bool')
        return self.reconfigure()

    def set_animation(self, on):
        """Slide animation when switching desktops (also what gives the touchpad desktop-swipe its motion)."""
        self.write('Plugins', 'slideEnabled', bool(on), 'bool')
        try:
            bus = self.bus or Gio.bus_get_sync(Gio.BusType.SESSION)
            bus.call_sync(KWIN, '/Effects', 'org.kde.kwin.Effects', 'loadEffect' if on else 'unloadEffect',
                          GLib.Variant('(s)', ('slide',)), None, Gio.DBusCallFlags.NONE, 2000, None)
            return True
        except GLib.Error:
            return False


# ---------------------------------------------------------------------------------------------------------- desktops
class DesktopManager(GObject.Object):
    """Thin client for KWin's VirtualDesktopManager."""

    def __init__(self, bus=None):
        super().__init__()
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION)

    def _call(self, method, params=None):
        return self.bus.call_sync(KWIN, VDM_PATH, VDM_IFACE, method, params, None, Gio.DBusCallFlags.NONE, 2500, None)

    def _prop(self, name):
        reply = self.bus.call_sync(KWIN, VDM_PATH, 'org.freedesktop.DBus.Properties', 'Get',
                                   GLib.Variant('(ss)', (VDM_IFACE, name)), None, Gio.DBusCallFlags.NONE, 2500, None)
        return reply.unpack()[0]

    def desktops(self):
        """[(number, id, name)] in order."""
        try:
            return [(n, i, name) for n, i, name in self._prop('desktops')]
        except GLib.Error:
            return []

    def current_id(self):
        try:
            return self._prop('current')
        except GLib.Error:
            return ''

    def switch_to_id(self, desktop_id):
        self.bus.call_sync(KWIN, VDM_PATH, 'org.freedesktop.DBus.Properties', 'Set',
                           GLib.Variant('(ssv)', (VDM_IFACE, 'current', GLib.Variant('s', desktop_id))), None,
                           Gio.DBusCallFlags.NONE, 2500, None)

    def switch_to(self, number):
        for n, ident, _name in self.desktops():
            if n == int(number):
                self.switch_to_id(ident)
                return True
        return False

    def create(self, name=None):
        items = self.desktops()
        if len(items) >= MAX_DESKTOPS:
            raise ValueError(f'at most {MAX_DESKTOPS} desktops')
        self._call('createDesktop', GLib.Variant('(us)', (len(items), (name or '').strip() or f'Desktop {len(items) + 1}')))

    def remove(self, desktop_id):
        if len(self.desktops()) <= 1:
            raise ValueError('the last desktop cannot be removed')
        self._call('removeDesktop', GLib.Variant('(s)', (desktop_id,)))

    def rename(self, desktop_id, name):
        name = (name or '').strip()
        if not name or len(name) > 40:
            raise ValueError('desktop names must be 1 to 40 characters')
        self._call('setDesktopName', GLib.Variant('(ss)', (desktop_id, name)))

    def set_count(self, count):
        count = int(count)
        if not 1 <= count <= MAX_DESKTOPS:
            raise ValueError(f'desktop count must be between 1 and {MAX_DESKTOPS}')
        while len(self.desktops()) < count:
            self.create()
        while len(self.desktops()) > count:
            self.remove(self.desktops()[-1][1])
        return self.desktops()

    def set_wrap(self, on):
        self.bus.call_sync(KWIN, VDM_PATH, 'org.freedesktop.DBus.Properties', 'Set',
                           GLib.Variant('(ssv)', (VDM_IFACE, 'navigationWrappingAround', GLib.Variant('b', bool(on)))), None,
                           Gio.DBusCallFlags.NONE, 2500, None)


# ---------------------------------------------------------------------------------------------------------- window ops
def window_command(bridge, action, win_id, **kw):
    """Window operations beyond windows.py's own list, as one-shot KWin scripts with only validated values interpolated."""
    simple = {
        'keep_above': 'W.keepAbove = %s;' % ('true' if kw.get('on', True) else 'false'),
        'all_desktops': 'W.onAllDesktops = %s;' % ('true' if kw.get('on', True) else 'false'),
        'unmaximize': 'W.setMaximize(false, false);',
    }
    if action == 'snap':
        zone = kw.get('zone')
        if zone not in ZONES:
            raise ValueError('unknown snap zone')
        if zone == 'full':
            return bridge.command('maximize', win_id)
        body = ('var a = workspace.clientArea(KWin.MaximizeArea, W); var Z = %s; W.setMaximize(false, false);'
                'var x = a.x, y = a.y, w = a.width, h = a.height, hw = w / 2, hh = h / 2, t = w / 3;'
                'var T = {"left": [x, y, hw, h], "right": [x + hw, y, hw, h], "top": [x, y, w, hh], "bottom": [x, y + hh, w, hh],'
                '"top-left": [x, y, hw, hh], "top-right": [x + hw, y, hw, hh], "bottom-left": [x, y + hh, hw, hh],'
                '"bottom-right": [x + hw, y + hh, hw, hh], "third-left": [x, y, t, h], "third-center": [x + t, y, t, h],'
                '"third-right": [x + 2 * t, y, t, h], "center": [x + w * 0.15, y + h * 0.1, w * 0.7, h * 0.8]}[Z];'
                'W.frameGeometry = {x: T[0], y: T[1], width: T[2], height: T[3]};' % json.dumps(zone))
    elif action in simple:
        body = simple[action]
    else:
        return bridge.command(action, win_id, **kw)
    head = bridge._find(win_id)
    bridge._run_script(head + body + '}')


def show_desktop(bridge):
    bridge._run_script('var any = workspace.windowList().filter(function (w) { return w.normalWindow && !w.minimized && !w.skipTaskbar; });'
                       'any.forEach(function (w) { w.minimized = true; });')


def unminimize_all(bridge):
    bridge._run_script('workspace.windowList().forEach(function (w) { if (w.normalWindow) w.minimized = false; });')


def new_desktop_with(manager, bridge, win_id):
    """Create a desktop and send the window there (the drop target 'New desktop' in the overview)."""
    manager.create()
    items = manager.desktops()
    window_command(bridge, 'to_desktop', win_id, desktop=items[-1][0])
    manager.switch_to(items[-1][0])


# ---------------------------------------------------------------------------------------------------------- window menu
def window_menu(shell, win, parent, after=None):
    """Popover with the window operations (shared by the overview, the switcher and the bar). Returns the popover."""
    bridge, manager = shell.windows, shell.parity.desktops
    pop = Gtk.Popover()
    pop.add_css_class('am-panel')
    pop.set_parent(parent)
    pop.connect('closed', lambda p: GLib.idle_add(p.unparent))
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    for m in ('top', 'bottom', 'start', 'end'):
        getattr(col, f'set_margin_{m}')(8)

    def item(text, fn, enabled=True):
        b = Gtk.Button(label=text, halign=Gtk.Align.FILL)
        b.add_css_class('am-tray-menu-item')
        b.get_child().set_xalign(0)
        b.set_sensitive(enabled)
        b.connect('clicked', lambda *_: (pop.popdown(), fn(), after() if after else None))
        col.append(b)

    wid = win['id']
    item('Restore' if win.get('maximized') else 'Maximize',
         lambda: window_command(bridge, 'unmaximize' if win.get('maximized') else 'maximize', wid))
    item('Minimize', lambda: window_command(bridge, 'minimize', wid))
    item('Always on top' if not win.get('above') else 'Stop keeping on top',
         lambda: window_command(bridge, 'keep_above', wid, on=not win.get('above')))
    item('Show on all desktops' if not win.get('allDesktops') else 'Only on this desktop',
         lambda: window_command(bridge, 'all_desktops', wid, on=not win.get('allDesktops')))
    col.append(Gtk.Separator())
    for zone, text in (('left', 'Snap left'), ('right', 'Snap right'), ('top-left', 'Snap top left'), ('top-right', 'Snap top right'),
                       ('bottom-left', 'Snap bottom left'), ('bottom-right', 'Snap bottom right')):
        item(text, lambda z=zone: window_command(bridge, 'snap', wid, zone=z))
    col.append(Gtk.Separator())
    for d in desktops_of(bridge.state):
        item(f"Move to {d['name']}", lambda n=d['n']: window_command(bridge, 'to_desktop', wid, desktop=n))
    item('Move to a new desktop', lambda: new_desktop_with(manager, bridge, wid))
    col.append(Gtk.Separator())
    item('Close', lambda: window_command(bridge, 'close', wid), enabled=win.get('closeable', True))
    pop.set_child(col)
    pop.popup()
    return pop


# ---------------------------------------------------------------------------------------------------------- pager widget
class Pager(Gtk.Box):
    """Bar widget: one pill per virtual desktop with its window count; click to switch, scroll to step, right click to manage,
    drop a window on a pill to send it there."""

    def __init__(self, shell):
        super().__init__(spacing=3, valign=Gtk.Align.CENTER)
        self.shell = shell
        self.add_css_class('am-pager')
        self._sig = shell.windows.connect('changed', lambda *_: self.refresh())
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.DISCRETE)
        scroll.connect('scroll', self._scroll)
        self.add_controller(scroll)
        self._last = None
        self.refresh()

    def refresh(self):
        items = desktops_of(self.shell.windows.state)
        sig = json.dumps(items, sort_keys=True)
        if sig == self._last:
            return
        self._last = sig
        dutil.clear(self)
        self.set_visible(len(items) > 0)
        for d in items:
            b = Gtk.Button()
            b.add_css_class('am-pager-pill')
            if d['current']:
                b.add_css_class('current')
            if d['windows']:
                b.add_css_class('busy')
            b.set_child(dutil.label(str(d['n']), 'am-mono', 0.5))
            b.set_tooltip_text(f"{d['name']}  ·  {d['windows']} window{'s' if d['windows'] != 1 else ''}")
            b.connect('clicked', lambda _b, n=d['n']: self.shell.parity.desktops.switch_to(n))
            right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
            right.connect('pressed', lambda g, _n, _x, _y, d=d, b=b: self._menu(d, b))
            b.add_controller(right)
            drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
            drop.connect('drop', lambda _t, value, _x, _y, n=d['n']: self._dropped(value, n))
            b.add_controller(drop)
            self.append(b)
        add = Gtk.Button(label='+')
        add.add_css_class('am-pager-pill')
        add.set_tooltip_text('Add a desktop')
        add.connect('clicked', lambda *_: self._safe(self.shell.parity.desktops.create))
        self.append(add)

    def _safe(self, fn, *args):
        try:
            fn(*args)
        except (ValueError, GLib.Error) as error:
            self.shell.notifications.notify('Amerika', 0, '', 'Desktops', str(getattr(error, 'message', error)))

    def _dropped(self, value, number):
        if not str(value).startswith('window:'):
            return False
        window_command(self.shell.windows, 'to_desktop', value[7:], desktop=number)
        return True

    def _scroll(self, _c, _dx, dy):
        items = desktops_of(self.shell.windows.state)
        cur = next((i for i, d in enumerate(items) if d['current']), 0)
        step = 1 if dy > 0 else -1
        target = items[(cur + step) % len(items)]['n'] if items else None
        if target:
            self.shell.parity.desktops.switch_to(target)
        return True

    def _menu(self, d, parent):
        pop = Gtk.Popover()
        pop.add_css_class('am-panel')
        pop.set_parent(parent)
        pop.connect('closed', lambda p: GLib.idle_add(p.unparent))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(col, f'set_margin_{m}')(10)
        entry = Gtk.Entry(text=d['name'], width_chars=18)
        entry.connect('activate', lambda e: (pop.popdown(), self._safe(self.shell.parity.desktops.rename, d['id'], e.get_text())))
        col.append(dutil.label('RENAME DESKTOP', 'am-label'))
        col.append(entry)
        for text, fn in (('Add a desktop', lambda: self._safe(self.shell.parity.desktops.create)),
                         ('Remove this desktop', lambda: self._safe(self.shell.parity.desktops.remove, d['id']))):
            b = Gtk.Button(label=text)
            b.add_css_class('am-tray-menu-item')
            b.get_child().set_xalign(0)
            b.connect('clicked', lambda _b, f=fn: (pop.popdown(), f()))
            col.append(b)
        pop.set_child(col)
        pop.popup()
