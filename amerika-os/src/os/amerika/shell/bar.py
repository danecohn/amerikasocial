"""The top bar: launcher, the AI apps, active window, clock, AI activity and quick controls."""
import threading
import time

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

from .. import system
from . import apps, layer
from .tray import Tray


def _label(text, css=None, xalign=0.0):
    label = Gtk.Label(label=text, xalign=xalign)
    if css:
        for c in css.split():
            label.add_css_class(c)
    return label


class Bar(Gtk.Window):
    def __init__(self, shell):
        super().__init__(application=shell, title='Amerika Bar')
        self.shell = shell
        self.add_css_class('am-bar')
        layer.setup(self, 'top', anchors=('top', 'left', 'right'), exclusive='auto', keyboard='on_demand', namespace='amerika-bar')
        self.set_default_size(1280, 36)

        box = Gtk.CenterBox()
        box.add_css_class('am-bar-box')
        self.set_child(box)

        # ---- start: launcher, AI apps, active app
        start = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        launcher = Gtk.Button()
        launcher.add_css_class('am-bar-btn')
        inner = Gtk.Box(spacing=7)
        inner.append(apps.icon_image('amerika-home', 18))
        inner.append(_label('AMERIKA', None))
        launcher.set_child(inner)
        launcher.connect('clicked', lambda *_: shell.toggle_launcher())
        start.append(launcher)
        for desktop_id in shell.settings.get('bar_ai_apps', []):
            info = apps.lookup(desktop_id)
            if not info:
                continue
            button = Gtk.Button()
            button.add_css_class('am-bar-btn')
            button.add_css_class('ai')
            row = Gtk.Box(spacing=7)
            row.append(apps.icon_image(info, 18))
            row.append(_label(info.get_display_name().upper()))
            button.set_child(row)
            button.set_tooltip_text(f'Open {info.get_display_name()}')
            button.connect('clicked', lambda _b, i=desktop_id: shell.activate_app(i))
            start.append(button)
        self.appname = _label('', 'am-appname')
        self.appname.set_margin_start(10)
        self.appname.set_ellipsize(3)
        self.appname.set_max_width_chars(48)
        start.append(self.appname)
        box.set_start_widget(start)

        # ---- center: clock
        self.clock = _label('', 'am-clock', 0.5)
        box.set_center_widget(self.clock)

        # ---- end: AI chip, stop, controls, notifications
        end = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.chip = _label('AI · IDLE', 'am-ai-chip idle')
        self.stop = Gtk.Button(label='STOP')
        self.stop.add_css_class('am-ai-stop')
        self.stop.set_visible(False)
        self.stop.connect('clicked', lambda *_: shell.broker.stop_all())
        end.append(self.chip)
        end.append(self.stop)

        self.tray = Tray()
        end.append(self.tray)
        self.tray.start()

        self.status = Gtk.MenuButton()
        self.status.add_css_class('am-bar-icon')
        self.status.set_always_show_arrow(False)
        sbox = Gtk.Box(spacing=8)
        self.net_icon = Gtk.Image.new_from_icon_name('amerika-wifi-symbolic')
        self.vol_icon = Gtk.Image.new_from_icon_name('amerika-volume-symbolic')
        self.bat_icon = Gtk.Image.new_from_icon_name('amerika-battery-symbolic')
        self.bat_label = _label('', 'am-mono')
        for w in (self.net_icon, self.vol_icon, self.bat_icon, self.bat_label):
            sbox.append(w)
        self.status.set_child(sbox)
        self.status.set_popover(self._controls_popover())
        end.append(self.status)

        self.bell = Gtk.MenuButton()
        self.bell.add_css_class('am-bar-icon')
        self.bell.set_icon_name('amerika-bell-symbolic')
        self.bell.set_popover(shell.notifications.center_popover())
        end.append(self.bell)
        box.set_end_widget(end)

        shell.windows.connect('changed', lambda *_: self._windows_changed())
        shell.broker.connect('activity', self._on_activity)
        GLib.timeout_add_seconds(1, self._tick)
        GLib.timeout_add_seconds(6, self._poll)
        self._tick()
        self._poll()

    # ------------------------------------------------------------------ controls popover
    def _controls_popover(self):
        pop = Gtk.Popover()
        pop.add_css_class('am-panel')
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(col, f'set_margin_{m}')(14)
        col.set_size_request(320, -1)
        col.append(_label('QUICK CONTROLS', 'am-label'))

        def slider(title, icon, getter, setter):
            row = Gtk.Box(spacing=10)
            row.append(Gtk.Image.new_from_icon_name(icon))
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_hexpand(True)
            scale.set_draw_value(False)
            state = getter() or {'percent': 50}
            scale.set_value(state['percent'])
            scale.connect('value-changed', lambda s: setter(int(s.get_value())) if not getattr(s, '_busy', False) else None)
            row.append(scale)
            col.append(row)
            return scale

        self.vol_scale = slider('Volume', 'amerika-volume-symbolic', system.volume, system.set_volume)
        self.bri_scale = slider('Brightness', 'amerika-brightness-symbolic', system.brightness, system.set_brightness)

        wifi = Gtk.Box(spacing=10)
        wifi.append(Gtk.Image.new_from_icon_name('amerika-wifi-symbolic'))
        wifi.append(_label('Wi-Fi', None))
        sw = Gtk.Switch(hexpand=True, halign=Gtk.Align.END)
        sw.set_active(system.wifi_enabled())
        sw.connect('state-set', lambda _s, on: (system.set_wifi(on), False)[1])
        wifi.append(sw)
        col.append(wifi)

        dnd = Gtk.Box(spacing=10)
        dnd.append(Gtk.Image.new_from_icon_name('amerika-moon-symbolic'))
        dnd.append(_label('Do not disturb', None))
        dsw = Gtk.Switch(hexpand=True, halign=Gtk.Align.END)
        dsw.set_active(self.shell.notifications.dnd)
        dsw.connect('state-set', lambda _s, on: (self.shell.notifications.set_dnd(on), False)[1])
        dnd.append(dsw)
        col.append(dnd)

        col.append(Gtk.Separator())
        actions = Gtk.Box(spacing=8, homogeneous=True)
        for icon, title, fn in (('amerika-settings-symbolic', 'Settings', lambda: self.shell.open_settings()),
                                ('amerika-lock-symbolic', 'Lock', system.lock_session),
                                ('amerika-logout-symbolic', 'Log out', system.logout),
                                ('amerika-power-symbolic', 'Power', lambda: self.shell.confirm_power())):
            b = Gtk.Button()
            b.add_css_class('am-secondary')
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            v.append(Gtk.Image.new_from_icon_name(icon))
            v.append(_label(title.upper(), 'am-label', 0.5))
            b.set_child(v)
            b.connect('clicked', lambda _b, f=fn: (pop.popdown(), f()))
            actions.append(b)
        col.append(actions)
        pop.set_child(col)
        return pop

    # ------------------------------------------------------------------ updates
    def _tick(self):
        fmt = '%a %d %b   %H:%M' if self.shell.settings.get('clock_24h') else '%a %d %b   %I:%M %p'
        self.clock.set_text(time.strftime(fmt).upper())
        return True

    def _poll(self):
        def work():
            data = {'net': system.network(), 'vol': system.volume(), 'bat': system.battery()}
            GLib.idle_add(self._apply_status, data)
        threading.Thread(target=work, daemon=True).start()
        return True

    def _apply_status(self, data):
        net = data['net'] or {}
        self.net_icon.set_opacity(1.0 if net.get('state') == 'connected' else 0.4)
        self.net_icon.set_tooltip_text(net.get('connection') or 'Not connected')
        vol = data['vol']
        self.vol_icon.set_opacity(0.4 if (not vol or vol['muted']) else 1.0)
        if vol:
            self.vol_icon.set_tooltip_text(f"Volume {vol['percent']}%{' (muted)' if vol['muted'] else ''}")
        bat = data['bat']
        if bat and bat.get('present', True):
            self.bat_label.set_text(f"{bat['percent']}%{'⚡' if bat['state'] == 'charging' else ''}")
            self.bat_icon.set_visible(True)
        else:
            self.bat_label.set_text('')
            self.bat_icon.set_visible(False)
        return False

    def _windows_changed(self):
        active = [w for w in self.shell.windows.app_windows() if w.get('active')]
        self.appname.set_text((active[0].get('caption') or active[0].get('cls') or '').upper() if active else '')

    def _on_activity(self, _broker, client, text, active):
        self.chip.set_text(f'{client.upper()} · {text.upper()}' if active else 'AI · IDLE')
        if active:
            self.chip.remove_css_class('idle')
        else:
            self.chip.add_css_class('idle')
        self.stop.set_visible(active)
