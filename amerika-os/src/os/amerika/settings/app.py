"""Amerika Settings: appearance, display, sound, network, power and, above all, the AI assistants."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import __version__, common, system, theme
from ..ai import connect
from ..shell import apps
from ..shell.app import save_widget
from ..shell.desktop import WALLPAPERS, wallpaper_path

PRESETS = {'Crimson': '#ff2e63', 'Cyan': '#19e3ff', 'Magenta': '#ff3df0', 'Amber': '#ffb02e', 'Phosphor': '#39ff88', 'Violet': '#9b6bff'}
MODES = [('ask', 'Ask every time', 'Claude and ChatGPT ask before changing anything. Read-only tools still work.'),
         ('safe', 'Balanced (recommended)', 'Everyday changes run on their own (open apps, windows, volume). Anything that could lose or expose data asks first.'),
         ('trusted', 'Trusted', 'Also lets them run sensitive tools such as shell commands and file writes without asking. Power-off, restart and delete always ask.')]


def label(text, css=None, xalign=0.0, wrap=False):
    lab = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    for c in (css or '').split():
        lab.add_css_class(c)
    return lab


def card(*children, spacing=10):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    box.add_css_class('am-card')
    for c in children:
        box.append(c)
    return box


def page_box():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    for m in ('top', 'bottom', 'start', 'end'):
        getattr(box, f'set_margin_{m}')(26)
    return box


def scrolled(child):
    s = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    s.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    s.set_child(child)
    return s


class SettingsApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.amerika.Settings')
        self.settings = common.load_settings()
        self.win = None
        self.pages = {}

    def do_activate(self):
        if self.win:
            self.win.present()
            return
        dev_icons = os.environ.get('AMERIKA_ICONS')
        icons = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if dev_icons:
            icons.set_search_path([dev_icons] + list(icons.get_search_path() or []))
        Gtk.Settings.get_default().set_property('gtk-icon-theme-name', 'AmerikaOS')
        theme.apply(self.settings['accent'], self.settings['secondary'])
        self.win = Gtk.ApplicationWindow(application=self, title='Amerika Settings')
        self.win.add_css_class('am-settings')
        self.win.set_default_size(1040, 720)
        root = Gtk.Box()
        self.win.set_child(root)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        side.add_css_class('am-sidebar')
        side.set_size_request(230, -1)
        brand = Gtk.Box(spacing=10)
        brand.append(apps.icon_image('amerika-settings', 34))
        brand.append(label('SETTINGS', 'am-heading'))
        brand.set_margin_bottom(14)
        side.append(brand)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        self.nav = {}
        order = [('ai', 'AI & Assistants', 'amerika-ai', self._page_ai), ('appearance', 'Appearance', 'amerika-home', self._page_appearance),
                 ('display', 'Display', 'amerika-display', self._page_display), ('sound', 'Sound', 'amerika-sound', self._page_sound),
                 ('network', 'Network', 'amerika-network', self._page_network), ('power', 'Power', 'amerika-power', self._page_power),
                 ('login', 'Login screen', 'amerika-home', self._page_login),
                 ('about', 'About', 'amerika-settings', self._page_about)]
        for key, title, icon, builder in order:
            btn = Gtk.ToggleButton()
            btn.add_css_class('am-side-item')
            row = Gtk.Box(spacing=10)
            row.append(apps.icon_image(icon, 24))
            row.append(label(title))
            btn.set_child(row)
            btn.connect('toggled', lambda b, k=key: self._nav(k) if b.get_active() else None)
            side.append(btn)
            self.nav[key] = btn
            self.pages[key] = builder
            self.stack.add_named(scrolled(builder()), key)
        root.append(side)
        root.append(self.stack)
        self.nav['ai'].set_active(True)
        self.win.present()
        shots = os.environ.get('AMERIKA_SETTINGS_SHOTS')
        if shots:
            GLib.timeout_add(1500, self._shoot, Path(shots), list(self.pages))

    def _nav(self, key):
        for k, b in self.nav.items():
            if k != key and b.get_active():
                b.set_active(False)
        self.stack.set_visible_child_name(key)

    def _shoot(self, outdir, keys):
        outdir.mkdir(parents=True, exist_ok=True)
        if not keys:
            self.quit()
            return False
        key = keys.pop(0)
        self.nav[key].set_active(True)
        GLib.timeout_add(500, lambda: (save_widget(self.win, outdir / f'settings-{key}.png'), GLib.timeout_add(300, self._shoot, outdir, keys), False)[2])
        return False

    def save(self):
        common.save_settings(self.settings)

    # ================================================================ AI page
    def _page_ai(self):
        box = page_box()
        box.append(label('AI & ASSISTANTS', 'am-heading'))
        box.append(label('Claude and ChatGPT can operate this computer through the Amerika system tools. You decide how much they may do, '
                         'you see everything they do in the top bar, and you can stop them at any time with Ctrl+Alt+Esc.', 'am-sub', wrap=True))

        # --- connections
        cards = Gtk.Box(spacing=14, homogeneous=True)
        self.conn_buttons = {}
        for client, name, desktop_id, conn, disc in (('claude', 'Claude', 'com.anthropic.Claude', connect.connect_claude, connect.disconnect_claude),
                                                     ('chatgpt', 'ChatGPT', 'chatgpt', connect.connect_chatgpt, connect.disconnect_chatgpt)):
            info = apps.lookup(desktop_id)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            head = Gtk.Box(spacing=10)
            head.append(apps.icon_image(info if info else 'amerika-ai', 44))
            head.append(label(name.upper(), 'am-heading'))
            col.append(head)
            status = label('', 'am-sub', wrap=True)
            button = Gtk.Button()
            button.add_css_class('am-primary')
            enabled = Gtk.Switch(halign=Gtk.Align.START)
            enabled.set_active(self.settings['ai']['clients'].get(client, {}).get('enabled', True))
            enabled.connect('state-set', lambda _s, on, c=client: (self._client_set(c, 'enabled', on), False)[1])
            col.append(status)
            col.append(button)
            erow = Gtk.Box(spacing=8)
            erow.append(enabled)
            erow.append(label('Allow this app to use the tools', 'am-sub'))
            col.append(erow)
            if not info:
                status.set_text(f'{name} is not installed on this computer.')
            self.conn_buttons[client] = (button, status, conn, disc)
            button.connect('clicked', lambda _b, c=client: self._toggle_connection(c))
            cards.append(card(col))
        box.append(cards)
        self._refresh_connections()

        # --- Copilot key
        key_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        key_card.append(label('COPILOT KEY', 'am-label'))
        key_card.append(label('The Copilot key on your keyboard (Win+Shift+F23) opens:', 'am-sub', wrap=True))
        choices = [('claude', 'Claude'), ('chatgpt', 'ChatGPT'), ('ask', 'Ask me each time')]
        drop = Gtk.DropDown.new_from_strings([c[1] for c in choices])
        current = self.settings.get('copilot_app', 'claude')
        drop.set_selected(next((i for i, c in enumerate(choices) if c[0] == current), 0))
        drop.connect('notify::selected', lambda d, _p: self._set('copilot_app', choices[d.get_selected()][0]))
        key_card.append(drop)
        box.append(card(key_card))

        # --- permission mode
        mode_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_card.append(label('PERMISSIONS', 'am-label'))
        group = None
        self.mode_buttons = {}
        for key, title, text in MODES:
            row = Gtk.Box(spacing=12)
            radio = Gtk.CheckButton()
            if group:
                radio.set_group(group)
            group = group or radio
            radio.set_active(self.settings['ai']['mode'] == key)
            radio.connect('toggled', lambda r, k=key: self._set_mode(k) if r.get_active() else None)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            col.append(label(title, 'am-appname'))
            col.append(label(text, 'am-sub', wrap=True))
            row.append(radio)
            row.append(col)
            mode_card.append(row)
            self.mode_buttons[key] = radio
        box.append(card(mode_card))

        # --- activity + audit
        audit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        head = Gtk.Box(spacing=10)
        head.append(label('ACTIVITY LOG', 'am-label', wrap=False))
        head.get_first_child().set_hexpand(True)
        refresh = Gtk.Button(label='Refresh')
        refresh.add_css_class('am-secondary')
        refresh.connect('clicked', lambda *_: self._fill_audit())
        head.append(refresh)
        audit_card.append(head)
        self.audit_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        audit_card.append(self.audit_list)
        box.append(card(audit_card))
        self._fill_audit()
        return box

    def _refresh_connections(self):
        state = connect.status()
        for client, (button, status, conn, disc) in self.conn_buttons.items():
            on = state.get(client)
            button.set_label('Disconnect' if on else 'Connect to Amerika OS')
            if on:
                button.remove_css_class('am-primary')
                button.add_css_class('am-secondary')
                status.set_text('Connected. Restart the app once so it picks up the Amerika system tools.')
            else:
                button.remove_css_class('am-secondary')
                button.add_css_class('am-primary')
                if 'not installed' not in status.get_text():
                    status.set_text('Not connected. Connecting adds the Amerika system tools to this app\'s settings; you can remove them again here.')

    def _toggle_connection(self, client):
        button, status, conn, disc = self.conn_buttons[client]
        try:
            (disc if connect.status().get(client) else conn)()
        except (OSError, ValueError) as error:
            status.set_text(f'Could not change the connection: {error}')
            return
        self._refresh_connections()

    def _client_set(self, client, key, value):
        self.settings['ai']['clients'].setdefault(client, {})[key] = value
        self.save()

    def _set_mode(self, mode):
        self.settings['ai']['mode'] = mode
        self.save()

    def _fill_audit(self):
        child = self.audit_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.audit_list.remove(child)
            child = nxt
        events = list(reversed(common.read_audit(60)))
        if not events:
            self.audit_list.append(label('Nothing yet. When Claude or ChatGPT use the system tools, each action appears here.', 'am-sub', wrap=True))
        for e in events[:40]:
            ok = e.get('ok', True) if e.get('event') == 'call' else None
            what = e.get('tool') or e.get('event')
            tag = {'call': 'OK' if ok else 'FAILED', 'denied': 'DENIED', 'paused': 'PAUSED', 'resumed': 'RESUMED'}.get(e.get('event'), e.get('event', ''))
            row = Gtk.Box(spacing=10)
            row.append(label(e.get('t', '')[11:19], 'am-mono am-sub'))
            row.append(label((e.get('client') or '').upper(), 'am-label'))
            row.append(label(what, 'am-appname'))
            row.append(label(tag, 'am-label'))
            self.audit_list.append(row)

    # ================================================================ Appearance
    def _page_appearance(self):
        box = page_box()
        box.append(label('APPEARANCE', 'am-heading'))
        accent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        accent.append(label('ACCENT COLOUR', 'am-label'))
        row = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, row_spacing=8, column_spacing=8)
        for name, colour in PRESETS.items():
            b = Gtk.Button(label=name)
            b.add_css_class('am-secondary')
            b.connect('clicked', lambda _b, c=colour: self._set('accent', c))
            row.append(b)
        accent.append(row)
        box.append(card(accent))

        wall = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        wall.append(label('WALLPAPER', 'am-label'))
        row = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, row_spacing=12, column_spacing=12)
        for name in WALLPAPERS:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            path = wallpaper_path(name)
            pic = Gtk.Picture()
            pic.set_size_request(200, 113)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            if path:
                pic.set_filename(str(path))
            btn = Gtk.Button()
            btn.set_child(pic)
            btn.add_css_class('am-app')
            btn.connect('clicked', lambda _b, n=name: self._set('wallpaper', n))
            col.append(btn)
            col.append(label(name.upper(), 'am-label', 0.5))
            row.append(col)
        wall.append(row)
        box.append(card(wall))

        dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        dock.append(label('DOCK & CLOCK', 'am-label'))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 32, 96, 4)
        scale.set_value(self.settings['dock_size'])
        scale.set_draw_value(True)
        scale.connect('value-changed', lambda s: self._set('dock_size', int(s.get_value())))
        dock.append(label('Dock icon size', 'am-sub'))
        dock.append(scale)
        sw = Gtk.Box(spacing=10)
        s24 = Gtk.Switch()
        s24.set_active(self.settings['clock_24h'])
        s24.connect('state-set', lambda _s, on: (self._set('clock_24h', on), False)[1])
        sw.append(s24)
        sw.append(label('24-hour clock'))
        dock.append(sw)
        box.append(card(dock))
        return box

    def _set(self, key, value):
        self.settings[key] = value
        self.save()

    # ================================================================ Display
    def _page_display(self):
        box = page_box()
        box.append(label('DISPLAY', 'am-heading'))
        bright = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bright.append(label('BRIGHTNESS', 'am-label'))
        b = system.brightness()
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        scale.set_draw_value(True)
        scale.set_value(b['percent'] if b else 50)
        scale.set_sensitive(bool(b))
        scale.connect('value-changed', lambda s: system.set_brightness(int(s.get_value())))
        bright.append(scale)
        box.append(card(bright))
        self.display_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.display_card.append(label('SCREENS', 'am-label'))
        self.display_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.display_card.append(self.display_rows)
        box.append(card(self.display_card))

        def load():
            data = system.displays()
            GLib.idle_add(self._fill_displays, data)
        threading.Thread(target=load, daemon=True).start()
        return box

    def _fill_displays(self, data):
        if not data:
            self.display_rows.append(label('Display details are available when the Amerika session is running.', 'am-sub', wrap=True))
            return False
        for d in data:
            row = Gtk.Box(spacing=12)
            row.append(label(f"{d['name']}   {d['width']}×{d['height']}", 'am-appname'))
            row.get_first_child().set_hexpand(True)
            drop = Gtk.DropDown.new_from_strings(['100%', '125%', '150%', '175%', '200%'])
            drop.set_selected(max(0, min(4, round((d['scale'] - 1) / 0.25))))
            drop.connect('notify::selected', lambda dd, _p, n=d['name']: threading.Thread(
                target=system.set_display_scale, args=(n, 1 + 0.25 * dd.get_selected()), daemon=True).start())
            row.append(label('Scale', 'am-sub'))
            row.append(drop)
            self.display_rows.append(row)
        return False

    # ================================================================ Sound
    def _page_sound(self):
        box = page_box()
        box.append(label('SOUND', 'am-heading'))
        vol = system.volume() or {'percent': 50, 'muted': False}
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        col.append(label('OUTPUT VOLUME', 'am-label'))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(True)
        scale.set_value(min(100, vol['percent']))
        scale.connect('value-changed', lambda s: system.set_volume(int(s.get_value())))
        col.append(scale)
        row = Gtk.Box(spacing=10)
        mute = Gtk.Switch()
        mute.set_active(vol['muted'])
        mute.connect('state-set', lambda _s, on: (system.set_mute(on), False)[1])
        row.append(mute)
        row.append(label('Muted'))
        col.append(row)
        box.append(card(col))
        return box

    # ================================================================ Network
    def _page_network(self):
        box = page_box()
        box.append(label('NETWORK', 'am-heading'))
        net = system.network() or {}
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        col.append(label('CONNECTION', 'am-label'))
        col.append(label(net.get('connection') or 'Not connected', 'am-appname'))
        row = Gtk.Box(spacing=10)
        sw = Gtk.Switch()
        sw.set_active(system.wifi_enabled())
        sw.connect('state-set', lambda _s, on: (system.set_wifi(on), False)[1])
        row.append(sw)
        row.append(label('Wi-Fi'))
        col.append(row)
        box.append(card(col))
        return box

    # ================================================================ Power
    def _page_power(self):
        box = page_box()
        box.append(label('POWER', 'am-heading'))
        bat = system.battery()
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        col.append(label('BATTERY', 'am-label'))
        col.append(label(f"{bat['percent']}%  ·  {bat['state']}" if bat else 'No battery found', 'am-appname'))
        col.append(label('POWER PROFILE', 'am-label'))
        profiles = ['power-saver', 'balanced', 'performance']
        drop = Gtk.DropDown.new_from_strings(['Power saver', 'Balanced', 'Performance'])
        cur = system.power_profile()
        if cur in profiles:
            drop.set_selected(profiles.index(cur))
        drop.connect('notify::selected', lambda d, _p: system.set_power_profile(profiles[d.get_selected()]))
        col.append(drop)
        box.append(card(col))
        return box

    # ================================================================ Login screen
    LOGIN_HELPER = os.environ.get('AMERIKA_LOGIN_HELPER', '/usr/libexec/amerika/amerika-login-helper')

    def _login_status(self):
        try:
            out = subprocess.run([self.LOGIN_HELPER, 'status'], capture_output=True, text=True, timeout=10)
            return json.loads(out.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None

    def _page_login(self):
        box = page_box()
        box.append(label('LOGIN SCREEN', 'am-heading'))
        box.append(label('Amerika OS has its own retro-futurist login screen. It uses the SDDM login manager instead of GDM, '
                         'takes effect the next time you start or restart the computer, and can be switched back here at any time.', 'am-sub', wrap=True))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        col.append(label('STATUS', 'am-label'))
        self.login_status = label('', 'am-appname', wrap=True)
        col.append(self.login_status)
        row = Gtk.Box(spacing=10)
        self.login_enable = Gtk.Button()
        self.login_enable.add_css_class('am-primary')
        self.login_enable.connect('clicked', lambda *_: self._login_change())
        row.append(self.login_enable)
        preview = Gtk.Button(label='Preview (30 seconds)')
        preview.add_css_class('am-secondary')
        preview.connect('clicked', lambda *_: subprocess.Popen(['timeout', '30', 'sddm-greeter-qt6', '--test-mode', '--theme',
                                                                '/usr/share/sddm/themes/amerika'], stdout=subprocess.DEVNULL,
                                                               stderr=subprocess.DEVNULL, start_new_session=True))
        row.append(preview)
        col.append(row)
        self.login_note = label('', 'am-sub', wrap=True)
        col.append(self.login_note)
        box.append(card(col))
        box.append(card(label('IF THE LOGIN SCREEN EVER DOES NOT APPEAR', 'am-label'),
                        label('Amerika OS switches back to the previous login screen by itself if SDDM cannot start. If you ever see a blank '
                              'screen anyway: press Ctrl+Alt+F3, log in on the text console, and run  sudo /usr/libexec/amerika/amerika-login-helper '
                              'disable  then  sudo reboot.', 'am-sub', wrap=True)))
        self._refresh_login()
        return box

    def _refresh_login(self):
        st = self._login_status()
        if not st:
            self.login_status.set_text('The login screen helper is not installed.')
            self.login_enable.set_sensitive(False)
            return
        name = os.path.basename(st.get('default') or '') or 'unknown'
        if st.get('amerika_active'):
            self.login_status.set_text('The Amerika login screen is on (SDDM).')
            self.login_enable.set_label('Go back to the previous login screen')
            self.login_enable.remove_css_class('am-primary')
            self.login_enable.add_css_class('am-secondary')
        else:
            self.login_status.set_text(f'You are using the {name} login screen.')
            self.login_enable.set_label('Use the Amerika login screen')
            self.login_enable.remove_css_class('am-secondary')
            self.login_enable.add_css_class('am-primary')
        self.login_enable.set_sensitive(bool(st.get('theme_installed') and st.get('sddm_installed')))
        self._login_active = bool(st.get('amerika_active'))

    def _login_change(self):
        action = 'disable' if getattr(self, '_login_active', False) else 'enable'
        self.login_note.set_text('Asking for your password…')

        def work():
            res = subprocess.run(['pkexec', self.LOGIN_HELPER, action], capture_output=True, text=True)
            GLib.idle_add(self._login_changed, action, res)
        threading.Thread(target=work, daemon=True).start()

    def _login_changed(self, action, res):
        self._refresh_login()
        if res.returncode == 0:
            self.login_note.set_text('Done. It applies the next time you start or restart the computer.' if action == 'enable'
                                     else 'Done. The previous login screen returns at the next start.')
        elif res.returncode in (126, 127):
            self.login_note.set_text('Cancelled: no changes were made.')
        else:
            self.login_note.set_text('Could not change it: ' + (res.stderr or res.stdout).strip()[:300])
        return False

    # ================================================================ About
    def _page_about(self):
        box = page_box()
        box.append(label('ABOUT', 'am-heading'))
        info = system.os_info()
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        col.append(label(f'Amerika OS {__version__}', 'am-appname'))
        col.append(label('Its own desktop, with Claude and ChatGPT at the centre. Retro-future by Amerika LLC.', 'am-sub', wrap=True))
        for k, v in (('Base system', info.get('distribution')), ('Kernel', info.get('kernel')), ('Machine', info.get('machine')),
                     ('Host', info.get('host'))):
            col.append(label(f'{k.upper()}', 'am-label'))
            col.append(label(str(v), None))
        box.append(card(col))
        sw = Gtk.Button(label='Open Amerika Software')
        sw.add_css_class('am-secondary')
        sw.connect('clicked', lambda *_: (lambda i: apps.launch(i) if i else None)(apps.lookup('amerika-software')))
        box.append(sw)
        return box


def main():
    return SettingsApp().run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
