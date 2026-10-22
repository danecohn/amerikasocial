"""The Amerika Shell application: ties the bar, dock, desktop, launcher, notifications and the AI broker together."""
import os
import json
import signal
import sys
import time
from concurrent.futures import Future
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import common, deskconf, theme, windows as windows_mod
from ..ai.broker import Broker
from . import apps, barlayout, home, layer
from .approval import Approval
from .agent_service import AgentService  # agent-ui
from .bar import Bar
from .caster import Caster
from .desktop import Desktop
from .dock import Dock
from .launcher import Launcher
from .notifyd import Notifications
from .power import PowerDialog

DESKTOP_XML = '<node><interface name="org.amerika.Desktop"><method name="Config"><arg type="s" direction="out"/></method></interface></node>'

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
        self.dock = None
        self.caster = None
        self.home = None
        self._home_key = None
        self._home_release = []
        self._home_started = 0.0
        self._approvals = set()
        self._provider = None
        self._started = False

    # ------------------------------------------------------------------ D-Bus objects
    def do_dbus_register(self, connection, object_path):
        self.windows = windows_mod.WindowBridge(connection)
        self.windows.export()
        desktop_info = Gio.DBusNodeInfo.new_for_xml(DESKTOP_XML)
        connection.register_object('/Desktop', desktop_info.interfaces[0], self._on_desktop, None, None)
        info = Gio.DBusNodeInfo.new_for_xml(CONTROL_XML)
        connection.register_object('/Control', info.interfaces[0], self._on_control, None, None)
        return Gtk.Application.do_dbus_register(self, connection, object_path)

    def _on_desktop(self, conn, sender, path, iface, method, params, invocation):
        invocation.return_value(GLib.Variant('(s)', (json.dumps(deskconf.bridge_config(self.settings, release=self._home_release)),)))

    def _on_control(self, conn, sender, path, iface, method, params, invocation):
        if method == 'Action':
            GLib.idle_add(self.action, params.unpack()[0])
        invocation.return_value(None)

    def action(self, name):
        if getattr(self, 'parity', None) and self.parity.action(name):
            return False
        ai = self.settings.get('bar_ai_apps', [])
        if name == 'launcher':
            self.toggle_launcher()
        elif name in ('ai1', 'ai2') and len(ai) >= int(name[-1]):
            self.activate_app(ai[int(name[-1]) - 1])
        elif name == 'copilot':
            self.copilot_key()
        elif name == 'home':
            self.go_home()
        elif name == 'home-start':
            self.start_home()
        elif name == 'caster':
            self.caster.toggle()
        elif name == 'caster:close':
            self.caster.close()
        elif name.startswith('caster:') and name.split(':', 1)[1] in ('next', 'prev'):
            self.caster.press('Right' if name.endswith('next') else 'Left')
        elif name.startswith('relaunch:') and name.split(':', 1)[1] in home.APPS:
            self.relaunch_ai(name.split(':', 1)[1])
        elif name.startswith('debug-') and name not in ('debug-dock-menu', 'debug-report') and os.environ.get('AMERIKA_DEBUG'):
            self._debug(name)
        elif name == 'agent':  # agent-ui: Windows+A
            self.open_agent_window()
        elif name == 'debug-dock-menu' and os.environ.get('AMERIKA_DEBUG') and self.dock:
            self.dock.debug_menu()
        elif name == 'debug-report' and os.environ.get('AMERIKA_DEBUG') and self.dock:
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
        self.agent = AgentService(self)  # agent-ui: activity, status, Stop-switch coupling, Agent window
        common.CONFIG.mkdir(parents=True, exist_ok=True)
        self._monitor = Gio.File.new_for_path(str(common.CONFIG)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self._monitor.connect('changed', self._settings_changed)
        self.desktop = Desktop(self, self.settings)
        from .parity import DesktopServices
        self.parity = DesktopServices(self)
        self.bar = Bar(self)
        self.dock = Dock(self) if self.settings.get('dock_enabled', True) else None
        self.launcher = Launcher(self)
        self.caster = Caster(self)
        self.home = home.HomeSupervisor(self._home_has_window, self._home_launch, time.monotonic, on_give_up=self._home_gave_up)
        self._home_key = home.home_key(self.settings)
        GLib.timeout_add_seconds(2, self._home_tick)
        self.agent.start()  # agent-ui: after the bar exists so the chip receives the first update
        for w in (self.desktop, self.bar, self.dock):
            if w is not None:
                w.present()
        self.hold()
        GLib.timeout_add(900, self._mark_ready)
        shots = os.environ.get('AMERIKA_SCREENSHOT_DIR')
        if shots:
            GLib.timeout_add_seconds(int(os.environ.get('AMERIKA_SCREENSHOT_DELAY', '4')), self._screenshots, Path(shots))

    def _mark_ready(self):
        """Tell the startup screen that the bar and dock are on screen."""
        try:
            common.RUNTIME.mkdir(parents=True, exist_ok=True)
            (common.RUNTIME / 'shell-ready').write_text(str(os.getpid()))
        except OSError:
            pass
        return False

    def do_shutdown(self):
        if self.home is not None:
            self.home.stop()
        if hasattr(self, 'bar'):
            self.bar.tray.close()
        if getattr(self, 'parity', None):
            self.parity.close()
        if getattr(self, 'agent', None):
            self.agent.stop_for_exit()
        if self.broker:
            self.broker.close()
        Gtk.Application.do_shutdown(self)

    def _settings_changed(self, _monitor, file, _other, event):
        if file.get_basename() != 'settings.json' or event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            return
        from .. import notifprefs
        self.notifications.dnd = notifprefs.load()['dnd']
        old = self.settings
        self.settings = common.load_settings()
        if (old.get('accent'), old.get('secondary')) != (self.settings.get('accent'), self.settings.get('secondary')):
            self._apply_theme()
        if old.get('wallpaper') != self.settings.get('wallpaper'):
            self.desktop.apply(self.settings)
        if self.dock and (old.get('dock_size') != self.settings.get('dock_size') or old.get('dock_pinned') != self.settings.get('dock_pinned')):
            self.dock.rebuild(force=True)
        if old.get('desktop') != self.settings.get('desktop'):
            self.windows.load()
        if old.get('clock_24h') != self.settings.get('clock_24h'):
            self.bar._tick()
        self.reconcile()

    def _apply_theme(self):
        accent, second = self.settings.get('accent', '#ff2e63'), self.settings.get('secondary', '#19e3ff')
        if self._provider is not None:
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self._provider)
        self._ui_style = self.settings.get('ui_style', 'retro')
        self._provider = theme.apply(accent, second, self._ui_style)

    # ------------------------------------------------------------------ actions used by the UI and the AI tools
    def toggle_launcher(self):
        if self.launcher.get_visible():
            self.launcher.hide()
        else:
            self.launcher.present()

    def activate_app(self, desktop_id):
        key = home.key_for_desktop_id(desktop_id)
        if key:
            self.note_used(key)
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
        if choice == 'caster':
            self.caster.toggle()
        elif choice == 'agent':  # agent-ui
            self.open_agent_window()
        elif choice in ids:
            self.activate_app(ids[choice])
        else:
            self.launcher.present_ai()

    def open_agent_window(self, start=False):
        """agent-ui: open (or raise) the Amerika Agent window."""
        self.agent.open_window(start=start)

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
            if self.dock:
                self.dock.rebuild(force=True)
        elif key == 'clock_24h':
            self.bar._tick()
        self.reconcile()

    def update_settings(self, changes):
        """Change several settings with one write, then apply them."""
        self.settings.update(changes)
        common.save_settings(self.settings)
        self.reconcile()

    # ------------------------------------------------------------------ settings -> live shell
    def reconcile(self):
        """Make the running shell match the settings: dock present or not, bar layout, home app and its window rules."""
        if self.settings.get('ui_style', 'retro') != getattr(self, '_ui_style', self.settings.get('ui_style', 'retro')):
            self._apply_theme()
        want_dock = bool(self.settings.get('dock_enabled', True))
        if self.dock is not None and want_dock and self.dock.position != self.settings.get('dock_position', 'bottom'):
            dock, self.dock = self.dock, None  # moved to another screen edge: rebuild the layer-shell window
            dock.destroy()
        if want_dock and self.dock is None:
            self.dock = Dock(self)
            self.dock.present()
        elif not want_dock and self.dock is not None:
            dock, self.dock = self.dock, None
            dock.destroy()
        if getattr(self, 'bar', None):
            self.bar.rebuild()
        key = home.home_key(self.settings)
        if key != self._home_key:
            self._home_changed(self._home_key, key)

    def _home_changed(self, old, new):
        """home_mode moved: stop supervising the old app, give its window back its frame, load the rules for the new one."""
        self.home.stop()
        self._home_key = new
        self._home_release = home.classes(self.settings, old) if old else []
        self.windows.load()
        if new:
            self.start_home()

    # ------------------------------------------------------------------ home app
    def _home_info(self):
        key = home.home_key(self.settings)
        return apps.lookup(home.APPS[key]['id']) if key else None

    def _home_windows(self):
        return home.home_windows(self.windows.app_windows(), self.settings)

    def _home_has_window(self):
        return bool(self._home_windows())

    def _home_launch(self):
        info = self._home_info()
        if info is None:
            print('home app is not installed:', home.home_key(self.settings), flush=True)
            return False
        return apps.launch(info)

    def _home_gave_up(self):
        key = home.home_key(self.settings)
        name = home.APPS[key]['name'] if key else 'The home app'
        self.notifications.notify('Amerika', 0, '', f'{name} did not start', 'Home mode stopped retrying. Press Win+H to try again, or switch to Classic in Settings.')

    def start_home(self):
        """Launch the home app (once the window bridge has reported) and keep it running."""
        if home.home_key(self.settings) is None:
            return
        self._home_started = time.monotonic()
        self._home_pending = True

    def _home_tick(self):
        if self.home is None:
            return False
        if getattr(self, '_home_pending', False):
            reported = bool(self.windows.state.get('screens')) or time.monotonic() - self._home_started > 15
            if reported:
                self._home_pending = False
                if home.home_key(self.settings):
                    self.home.start()
        elif home.home_key(self.settings) is None and self.home.active:
            self.home.stop()
        else:
            self.home.tick()
        return True

    def go_home(self):
        """Win+H and the Home entries: bring the home app to the front (launching it when it is not running)."""
        key = home.home_key(self.settings)
        if not key:
            return
        wins = self._home_windows()
        if wins:
            target = next((w for w in wins if not w.get('minimized')), wins[0])
            self.note_used(key)
            self.windows.command('activate', target['id'])
        else:
            self.note_used(key)
            if getattr(self, '_home_pending', False):
                return                      # the pending start launches it
            if self.home.state == 'gave-up' or not self.home.active:
                self.home.start()
            else:
                self._home_launch()

    def choose_home(self, key):
        """The Caster's choice: that app becomes the front home view (the home app itself when home mode is on)."""
        changes = {'caster_last': key}
        if home.home_key(self.settings) and home.home_key(self.settings) != key:
            changes['home_mode'] = key
        self.note_used(key, save=False)
        changes['app_last_used'] = self.settings['app_last_used']
        self.update_settings(changes)
        if home.home_key(self.settings) == key:
            self.go_home()
        else:
            self.activate_app(home.APPS[key]['id'])

    def note_used(self, key, save=True):
        used = dict(self.settings.get('app_last_used') or {})
        used[key] = int(time.time())
        self.settings['app_last_used'] = used
        if save:
            common.save_settings(self.settings)

    def note_recent(self, desktop_id):
        recent = [r for r in (self.settings.get('recent_apps') or []) if r != desktop_id]
        self.settings['recent_apps'] = ([desktop_id] + recent)[:8]
        common.save_settings(self.settings)

    def relaunch_ai(self, key):
        """Restart one AI app so a new text size applies. Only the exact PIDs of that app's windows are signalled."""
        pids = sorted({int(w['pid']) for w in home.home_windows(self.windows.app_windows(), self.settings, key) + self.windows.windows_for(home.APPS[key]['id'])
                       if w.get('pid') and int(w['pid']) > 1 and int(w['pid']) != os.getpid()})
        paused = home.home_key(self.settings) == key
        if paused:
            self.home.pause(25)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        started = time.monotonic()

        def relaunch():
            if self.windows.windows_for(home.APPS[key]['id']) and time.monotonic() - started < 8:
                return True
            info = apps.lookup(home.APPS[key]['id'])
            if info:
                apps.launch(info)
            if paused:
                self.home.start(launch_now=False)
            return False
        GLib.timeout_add(500, relaunch)

    def _debug(self, name):
        """Rig-only hooks (AMERIKA_DEBUG): state dumps and widget screenshots."""
        if name == 'debug-home':
            print('DEBUG home mode=%s state=%s launches=%s failures=%s dock=%s bar_rebuilds=%s' % (
                home.mode(self.settings), self.home.state, self.home.launches, self.home.failures, self.dock is not None,
                getattr(self.bar, '_rebuilds', 0)), flush=True)
        elif name.startswith('debug-caster-key:'):
            print('DEBUG caster key=%s handled=%s focused=%s visible=%s' % (name.split(':', 1)[1], self.caster.press(name.split(':', 1)[1]),
                  self.caster.state.focused, self.caster.get_visible()), flush=True)
        elif name.startswith('debug-shot:') and os.environ.get('AMERIKA_SCREENSHOT_DIR'):
            widget = getattr(self, name.split(':', 1)[1], None)
            if widget is not None:
                save_widget(widget, Path(os.environ['AMERIKA_SCREENSHOT_DIR']) / (name.split(':', 1)[1] + '.png'))
        elif name == 'debug-windows':
            keep = ('cls', 'caption', 'x', 'y', 'w', 'h', 'noBorder', 'maximized', 'minimized', 'fullscreen', 'home', 'z', 'active', 'pid', 'dock')
            print('DEBUG windows ' + json.dumps({'windows': [{k: w.get(k) for k in keep} for w in self.windows.windows],
                                                  'screens': self.windows.state.get('screens')}), flush=True)
        elif name == 'debug-bar':
            print('DEBUG bar zones=%s height=%s rebuilds=%s date=%r clock=%r date_vis=%s' % (json.dumps(barlayout.zones(self.settings.get('bar_layout'))),
                  self.bar.get_height(), self.bar._rebuilds, self.bar.date.get_text(), self.bar.clock.get_text(), self.bar.date.get_visible()), flush=True)
        elif name.startswith('debug-screen') and os.environ.get('AMERIKA_SCREENSHOT_DIR'):
            from . import screenshot
            out = Path(os.environ['AMERIKA_SCREENSHOT_DIR']) / ((name.partition(':')[2] or 'screen-%d' % int(time.time() * 1000)) + '.png')
            screenshot.run_async(lambda: self.parity.screenshots.capture.workspace()[0],
                                 lambda surface, error: (surface.write_to_png(str(out)) if surface else None,
                                                          print('DEBUG screen saved=%s error=%s' % (out, error), flush=True)))
        elif name == 'debug-caster-state':
            print('DEBUG caster visible=%s focused=%s cards=%s' % (self.caster.get_visible(), self.caster.state.focused,
                  {k: self.caster.info(k)['running'] for k in home.APPS}), flush=True)

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
            win = getattr(self, name, None)
            if win is None:
                continue
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
