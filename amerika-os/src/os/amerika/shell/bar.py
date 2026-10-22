"""The top bar: launcher, the AI apps, active window, clock, AI activity and quick controls."""
import threading
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .. import system
from . import apps, barlayout, layer
from .agent_chip import AgentChip  # agent-ui
from .tray import Tray


def _label(text, css=None, xalign=0.0):
    label = Gtk.Label(label=text, xalign=xalign)
    if css:
        for c in css.split():
            label.add_css_class(c)
    return label


class Bar(Gtk.Window):
    """The top bar. Every widget is created once; `rebuild()` only re-arranges them from settings['bar_layout'] (see barlayout.py),
    and does nothing while the signature is unchanged or a popover is open."""

    def __init__(self, shell):
        super().__init__(application=shell, title='Amerika Bar')
        self.shell = shell
        self.add_css_class('am-bar')
        layer.setup(self, 'top', anchors=('top', 'left', 'right'), exclusive='auto', keyboard='on_demand', namespace='amerika-bar')
        self.set_default_size(1280, barlayout.height(shell.settings))

        box = Gtk.CenterBox()
        box.add_css_class('am-bar-box')
        self.set_child(box)
        self.zone_boxes = {'left': Gtk.Box(spacing=8, valign=Gtk.Align.CENTER), 'center': Gtk.Box(spacing=8, valign=Gtk.Align.CENTER),
                           'right': Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)}
        box.set_start_widget(self.zone_boxes['left'])
        box.set_center_widget(self.zone_boxes['center'])
        box.set_end_widget(self.zone_boxes['right'])
        self._style = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._style, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self._signature = None
        self._wrappers = []
        self._rebuilds = 0

        shell_ = shell
        self.parts = {}
        # ---- launcher and home buttons
        launcher = Gtk.Button()
        launcher.add_css_class('am-bar-btn')
        inner = Gtk.Box(spacing=7)
        inner.append(apps.icon_image('amerika-home', 18))
        inner.append(_label('Amerika' if shell.settings.get('ui_style') == 'tesla' else 'AMERIKA', None))
        launcher.set_child(inner)
        launcher.connect('clicked', lambda *_: shell_.toggle_launcher())
        self.parts['launcher'] = launcher
        home_btn = Gtk.Button()
        home_btn.add_css_class('am-bar-btn')
        home_btn.add_css_class('home')
        home_btn.set_child(_label('HOME', None))
        home_btn.set_tooltip_text('Bring the home app to the front (Win+H)')
        home_btn.connect('clicked', lambda *_: shell_.go_home())
        self.parts['home'] = home_btn
        self.parts['ai_apps'] = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)

        self.appname = _label('', 'am-appname')
        self.appname.set_margin_start(10)
        self.appname.set_ellipsize(3)
        self.appname.set_max_width_chars(48)
        self.parts['title'] = self.appname
        from .workspaces import Pager
        self.parts['pager'] = Pager(shell)

        # ---- clock and date (labels persist; the buttons around them are rebuilt)
        self.clock = _label('', 'am-clock', 0.5)
        self.date = _label('', 'am-clock', 0.5)

        # ---- recording and Stop are safety controls: always in the right zone, whatever the layout
        self.record_chip = Gtk.Button(label='● RECORDING')
        self.record_chip.add_css_class('am-ai-stop')
        self.record_chip.set_visible(False)
        self.record_chip.connect('clicked', lambda *_: shell_.action('record:toggle'))
        self.stop = Gtk.Button(label='STOP')
        self.stop.add_css_class('am-ai-stop')
        self.stop.set_visible(False)
        self.stop.connect('clicked', lambda *_: shell_.broker.stop_all())

        self.agent_chip = AgentChip(shell)  # agent-ui: live Amerika Agent state (hidden until the agent is installed)
        self.parts['agent_chip'] = self.agent_chip
        self.chip = _label('AI · IDLE', 'am-ai-chip idle')
        self.parts['ai_chip'] = self.chip

        self.tray = Tray()
        self.parts['tray'] = self.tray
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
        self.parts['status'] = self.status

        self.bell = Gtk.MenuButton()
        self.bell.add_css_class('am-bar-icon')
        self.bell.set_icon_name('amerika-bell-symbolic')
        self.bell.set_popover(shell.notifications.center_popover())
        self.parts['bell'] = self.bell

        self.rebuild(force=True)
        shell.windows.connect('changed', lambda *_: self._windows_changed())
        shell.broker.connect('activity', self._on_activity)
        GLib.timeout_add_seconds(1, self._tick)
        GLib.timeout_add_seconds(6, self._poll)
        self._tick()
        self._poll()

    # ------------------------------------------------------------------ layout
    def _popover_open(self):
        for pop in (self.status.get_popover(), self.bell.get_popover()):
            if pop is not None and pop.get_visible():
                return True
        item = self.tray.get_first_child()
        while item is not None:
            pop = getattr(item, 'pop', None)
            if pop is not None and pop.get_visible():
                return True
            item = item.get_next_sibling()
        return False

    @staticmethod
    def _detach(widget):
        parent = widget.get_parent()
        if parent is None:
            return
        if isinstance(parent, Gtk.Button):
            parent.set_child(None)
        elif isinstance(parent, Gtk.Box):
            parent.remove(widget)

    def _apply_style(self):
        h = barlayout.height(self.shell.settings)
        o = barlayout.opacity(self.shell.settings)
        self._style.load_from_string(
            '.am-bar-box { min-height: %dpx; background-image: linear-gradient(to bottom, alpha(#262535, %.2f), alpha(#12111b, %.2f));'
            ' box-shadow: 0 1px 14px alpha(@am_accent, %.2f), inset 0 1px 0 alpha(white, .10); }' % (h, o, o, 0.35 * o))
        self.set_default_size(1280, h)

    def _ai_buttons(self):
        box = self.parts['ai_apps']
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        for desktop_id in self.shell.settings.get('bar_ai_apps', []):
            info = apps.lookup(desktop_id)
            if not info:
                continue
            button = Gtk.Button()
            button.add_css_class('am-bar-btn')
            button.add_css_class('ai')
            row = Gtk.Box(spacing=7)
            row.append(apps.icon_image(info, 18))
            row.append(_label(info.get_display_name() if shell.settings.get('ui_style') == 'tesla' else info.get_display_name().upper()))
            button.set_child(row)
            button.set_tooltip_text(f'Open {info.get_display_name()}')
            button.connect('clicked', lambda _b, i=desktop_id: self.shell.activate_app(i))
            box.append(button)

    def _time_button(self, ids):
        button = Gtk.Button()
        button.add_css_class('am-bar-btn')
        button.connect('clicked', lambda *_: self.shell.action('calendar'))
        labels = {'clock': self.clock, 'date': self.date}
        for wid in ids:
            self._detach(labels[wid])
        if len(ids) == 1:
            button.set_child(labels[ids[0]])
        else:
            row = Gtk.Box(spacing=14)
            for wid in ids:
                row.append(labels[wid])
            button.set_child(row)
        self._wrappers.append(button)
        return button

    def rebuild(self, force=False):
        """Re-arrange the bar from settings. No-op when nothing it shows has changed; deferred while a popover is open."""
        signature = barlayout.signature(self.shell.settings)
        if not force and signature == self._signature:
            return False
        if not force and self._popover_open():
            if not getattr(self, '_retry', False):
                self._retry = True

                def again():
                    self._retry = False
                    self.rebuild()
                    return False
                GLib.timeout_add_seconds(1, again)
            return False
        self._signature = signature
        self._rebuilds += 1
        self._apply_style()
        self._ai_buttons()
        for old in self._wrappers:
            old.set_child(None)
        self._wrappers = []
        zones = barlayout.zones(self.shell.settings.get('bar_layout'))
        for zone, box in self.zone_boxes.items():
            child = box.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                box.remove(child)
                child = nxt
        right = self.zone_boxes['right']
        right.append(self.record_chip)
        right.append(self.stop)
        for zone, ids in zones.items():
            box = self.zone_boxes[zone]
            for run in barlayout.runs(ids):
                if run[0] in ('clock', 'date'):
                    box.append(self._time_button(run))
                else:
                    part = self.parts[run[0]]
                    self._detach(part)
                    box.append(part)
        self.date.set_visible(barlayout.clock_format(self.shell.settings)['date'] != 'none')
        self._tick()
        return True

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
        conf = barlayout.clock_format(self.shell.settings)
        now = time.localtime()
        up = self.shell.settings.get('ui_style') != 'tesla'
        self.clock.set_text(barlayout.format_time(conf, now, up))
        self.date.set_text(barlayout.format_date(conf, now, up))
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
        name = (active[0].get('caption') or active[0].get('cls') or '') if active else ''
        self.appname.set_text(name if self.shell.settings.get('ui_style') == 'tesla' else name.upper())

    def _on_activity(self, _broker, client, text, active):
        if active and client == 'Amerika Agent':  # agent-ui: its own chip shows what it is doing; keep only the Stop switch
            self.stop.set_visible(True)
            return
        self.chip.set_text(f'{client.upper()} · {text.upper()}' if active else 'AI · IDLE')
        if active:
            self.chip.remove_css_class('idle')
        else:
            self.chip.add_css_class('idle')
        self.stop.set_visible(active)
