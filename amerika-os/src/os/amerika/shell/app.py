"""The Amerika Shell application: ties the bar, dock, desktop, launcher, notifications and the AI broker together."""
import os
import sys
from concurrent.futures import Future
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import common, theme, windows as windows_mod
from ..ai.broker import Broker
from . import apps, layer
from .approval import Approval
from .bar import Bar
from .desktop import Desktop
from .dock import Dock
from .launcher import Launcher
from .notifyd import Notifications
from .power import PowerDialog

CONTROL_XML = '''<node><interface name="org.amerika.Control">
  <method name="Action"><arg type="s" name="name" direction="in"/></method>
</interface></node>'''


class Shell(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.amerika.Shell')
        self.settings = common.load_settings()
        self.windows = None
        self.notifications = None
        self.broker = None
        self.launcher = None
        self._approvals = set()
        self._provider = None
        self._started = False

    # ------------------------------------------------------------------ D-Bus objects
    def do_dbus_register(self, connection, object_path):
        self.windows = windows_mod.WindowBridge(connection)
        self.windows.export()
        info = Gio.DBusNodeInfo.new_for_xml(CONTROL_XML)
        connection.register_object('/Control', info.interfaces[0], self._on_control, None, None)
        return Gtk.Application.do_dbus_register(self, connection, object_path)

    def _on_control(self, conn, sender, path, iface, method, params, invocation):
        if method == 'Action':
            GLib.idle_add(self.action, params.unpack()[0])
        invocation.return_value(None)

    def action(self, name):
        ai = self.settings.get('bar_ai_apps', [])
        if name == 'launcher':
            self.toggle_launcher()
        elif name in ('ai1', 'ai2') and len(ai) >= int(name[-1]):
            self.activate_app(ai[int(name[-1]) - 1])
        elif name == 'copilot':
            self.copilot_key()
        elif name == 'debug-dock-menu' and os.environ.get('AMERIKA_DEBUG'):
            self.dock.debug_menu()
        elif name == 'debug-report' and os.environ.get('AMERIKA_DEBUG'):
            menu = getattr(self.dock, '_open_menu', None)
            print('DEBUG menu open=%s closed_after_ms=%s rebuilds=%s' % (bool(menu and menu.get_mapped() and menu.get_parent() is not None), getattr(self.dock, '_closed_after_ms', None), getattr(self.dock, '_rebuilds', 0)), flush=True)
            if menu and menu.get_visible() and os.environ.get('AMERIKA_SCREENSHOT_DIR'):
                save_widget(menu, Path(os.environ['AMERIKA_SCREENSHOT_DIR']) / 'dock-menu.png')
        elif name == 'lock':
            from .. import system
            system.lock_session()
        elif name == 'settings':
            self.open_settings()
        elif name == 'stop':
            self.broker.stop_all()
        return False

    # ------------------------------------------------------------------ lifecycle
    def do_activate(self):
        if self._started:
            return
        self._started = True
        display = Gdk.Display.get_default()
        icons = Gtk.IconTheme.get_for_display(display)
        dev_icons = os.environ.get('AMERIKA_ICONS')
        if dev_icons:  # development: our theme directory wins over any installed theme of the same name
            icons.set_search_path([dev_icons] + list(icons.get_search_path() or []))
        Gtk.Settings.get_default().set_property('gtk-icon-theme-name', 'AmerikaOS')
        self._apply_theme()
        if not layer.available():
            print('warning: layer-shell is not available; the shell cannot place its panels', file=sys.stderr, flush=True)
        self.windows.load()
        self.notifications = Notifications(self)
        self.notifications.start()
        self.broker = Broker(self)
        self.broker.start()
        common.CONFIG.mkdir(parents=True, exist_ok=True)
        self._monitor = Gio.File.new_for_path(str(common.CONFIG)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self._monitor.connect('changed', self._settings_changed)
        self.desktop = Desktop(self, self.settings)
        self.bar = Bar(self)
        self.dock = Dock(self)
        self.launcher = Launcher(self)
        for w in (self.desktop, self.bar, self.dock):
            w.present()
        self.hold()
        shots = os.environ.get('AMERIKA_SCREENSHOT_DIR')
        if shots:
            GLib.timeout_add_seconds(int(os.environ.get('AMERIKA_SCREENSHOT_DELAY', '4')), self._screenshots, Path(shots))

    def _settings_changed(self, _monitor, file, _other, event):
        if file.get_basename() != 'settings.json' or event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            return
        old = self.settings
        self.settings = common.load_settings()
        if (old.get('accent'), old.get('secondary')) != (self.settings.get('accent'), self.settings.get('secondary')):
            self._apply_theme()
        if old.get('wallpaper') != self.settings.get('wallpaper'):
            self.desktop.apply(self.settings)
        if old.get('dock_size') != self.settings.get('dock_size') or old.get('dock_pinned') != self.settings.get('dock_pinned'):
            self.dock.rebuild(force=True)
        if old.get('clock_24h') != self.settings.get('clock_24h'):
            self.bar._tick()

    def _apply_theme(self):
        accent, second = self.settings.get('accent', '#ff2e63'), self.settings.get('secondary', '#19e3ff')
        if self._provider is not None:
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self._provider)
        self._provider = theme.apply(accent, second)

    # ------------------------------------------------------------------ actions used by the UI and the AI tools
    def toggle_launcher(self):
        if self.launcher.get_visible():
            self.launcher.hide()
        else:
            self.launcher.present()

    def activate_app(self, desktop_id):
        wins = self.windows.windows_for(desktop_id)
        if wins:
            target = next((w for w in wins if not w['active']), wins[0])
            self.windows.command('activate', target['id'])
            return
        info = apps.lookup(desktop_id)
        if info:
            apps.launch(info)

    def copilot_key(self):
        """The Copilot key opens the AI app chosen in Settings, or a picker."""
        choice = self.settings.get('copilot_app', 'claude')
        ids = {'claude': 'com.anthropic.Claude', 'chatgpt': 'chatgpt'}
        if choice in ids:
            self.activate_app(ids[choice])
        else:
            self.launcher.present_ai()

    def hand_off_to_ai(self, desktop_id, text):
        """Put the question on the clipboard and bring the AI app forward (the apps have no prompt API)."""
        if text:
            self.clipboard_set(text)
            info = apps.lookup(desktop_id)
            name = info.get_display_name() if info else 'the app'
            self.notifications.notify('Amerika', 0, '', f'Your question is on the clipboard', f'Paste it into {name} with Ctrl+V.')
        self.activate_app(desktop_id)

    def open_settings(self):
        info = apps.lookup('amerika-settings')
        if info:
            apps.launch(info)

    def confirm_power(self):
        PowerDialog(self)

    def update_setting(self, key, value):
        self.settings[key] = value
        common.save_settings(self.settings)
        if key in ('accent', 'secondary'):
            self._apply_theme()
        elif key == 'wallpaper':
            self.desktop.apply(self.settings)
        elif key == 'dock_size':
            self.dock.rebuild(force=True)
        elif key == 'clock_24h':
            self.bar._tick()

    def clipboard_set(self, text):
        Gdk.Display.get_default().get_clipboard().set(text)

    def clipboard_get(self, callback):
        clip = Gdk.Display.get_default().get_clipboard()

        def done(source, result):
            try:
                callback(source.read_text_finish(result) or '')
            except GLib.Error:
                callback('')
        clip.read_text_async(None, done)

    # ------------------------------------------------------------------ AI approvals
    def ask_approval(self, client, tool, args, risk):
        dialog = Approval(self, client, tool, args, risk)
        self._approvals.add(dialog)
        dialog.future.add_done_callback(lambda _f: self._approvals.discard(dialog))
        return dialog.future

    def cancel_approvals(self):
        for dialog in list(self._approvals):
            dialog.finish('deny')

    # ------------------------------------------------------------------ test support
    def _screenshots(self, outdir):
        outdir.mkdir(parents=True, exist_ok=True)
        for name in ('bar', 'dock', 'desktop', 'launcher'):
            win = getattr(self, name, None)
            if win is None:
                continue
            if name == 'launcher':
                win.present()
        GLib.timeout_add(900, self._shoot_all, outdir)
        return False

    def _shoot_all(self, outdir):
        for name in ('desktop', 'bar', 'dock', 'launcher'):
            win = getattr(self, name)
            save_widget(win, outdir / f'{name}.png')
        for nid, toast in list(self.notifications._toasts.items()):
            save_widget(toast, outdir / f'toast-{nid}.png')
        for i, dlg in enumerate(self._approvals):
            save_widget(dlg, outdir / f'approval-{i}.png')
        if os.environ.get('AMERIKA_SCREENSHOT_QUIT') == '1':
            self.quit()
        return False


def save_widget(widget, path):
    """Render a realized widget to a PNG (used for visual checks without a compositor screenshot tool)."""
    w, h = widget.get_width(), widget.get_height()
    if w <= 0 or h <= 0:
        return False
    paintable = Gtk.WidgetPaintable.new(widget)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, w, h)
    node = snap.to_node()
    native = widget.get_native()
    renderer = native.get_renderer() if native else None
    if node is None or renderer is None:
        return False
    texture = renderer.render_texture(node, None)
    texture.save_to_png(str(path))
    return True


def main():
    # gtk4-layer-shell was preloaded for this process only; apps we launch must not inherit it
    os.environ.pop('LD_PRELOAD', None)
    return Shell().run(sys.argv)
