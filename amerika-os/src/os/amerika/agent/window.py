"""amerika-agent-window: the native Amerika Agent window.

Embeds OpenClaw's Control UI with WebKitGTK 6 using an ephemeral browser session.
A one-time pairing URL is fetched through the CLI and kept in memory only.
Embedded navigation stays on the configured gateway origin. Without WebKitGTK, the default browser opens instead.
"""
import os
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version('WebKit', '6.0')
    from gi.repository import WebKit  # noqa: E402
except (ValueError, ImportError):  # gir1.2-webkit-6.0 is not installed
    WebKit = None

from .. import common, theme  # noqa: E402
from . import cli, model  # noqa: E402
from .activity import ActivityWatcher  # noqa: E402

APP_ID = 'org.amerika.AgentWindow'
POLL_SECONDS = 4


def profile_dirs():
    """(data dir, cache dir): a dedicated WebKit profile, private to the user."""
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'amerika-os' / 'agent-window'
    cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'amerika-os' / 'agent-window'
    for d in (data, cache):
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(d, 0o700)
    return data, cache


def _label(text, css=None, xalign=0.0, wrap=False):
    lab = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    for c in (css or '').split():
        lab.add_css_class(c)
    return lab


def open_settings():
    try:
        subprocess.Popen(['amerika-settings', 'agent'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


class AgentWindow(Gtk.ApplicationWindow):
    def __init__(self, app, auto_start=False, embed=True):
        super().__init__(application=app, title='Amerika Agent')
        self.add_css_class('am-agent-window')
        self.set_default_size(1180, 780)
        self.embed = bool(embed and WebKit is not None)
        self.status = model.Status.missing()
        self.activity = ('idle', '', 0.0)
        self.web = None
        self._starting = False
        self._live = False          # the Control UI is (being) shown
        self._loading = False
        self._auto_start = auto_start
        self._auto_tried = False
        self._status_seen = False
        self._opened_external = False

        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.add_css_class('am-agent-frame')
        self.set_child(frame)

        # ---- header: title, live status, Stop/Start, Settings
        header = Gtk.Box(spacing=12)
        header.add_css_class('am-agent-header')
        icon = Gtk.Image.new_from_icon_name('amerika-ai')
        icon.set_pixel_size(22)
        header.append(icon)
        header.append(_label('AMERIKA AGENT', 'am-agent-title'))
        self.dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self.dot.add_css_class('am-agent-dot')
        self.dot.add_css_class('off')
        header.append(self.dot)
        self.status_label = _label('Checking…', 'am-agent-status')
        self.status_label.set_hexpand(True)
        header.append(self.status_label)
        self.reload_btn = Gtk.Button(label='Reload')
        self.reload_btn.add_css_class('am-agent-link')
        self.reload_btn.connect('clicked', lambda *_: self.reload())
        header.append(self.reload_btn)
        link = Gtk.Button(label='Settings')
        link.add_css_class('am-agent-link')
        link.connect('clicked', lambda *_: open_settings())
        header.append(link)
        self.stop_btn = Gtk.Button(label='Stop')
        self.stop_btn.add_css_class('am-secondary')
        self.stop_btn.connect('clicked', lambda *_: self._stop_or_start())
        header.append(self.stop_btn)
        frame.append(header)

        self.banner = Gtk.Box(spacing=8)
        self.banner.add_css_class('am-agent-banner')
        self.banner.append(_label('No API key saved yet, so the agent cannot answer. Add one in Settings, it takes a minute.', None, wrap=True))
        self.banner.set_visible(False)
        frame.append(self.banner)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True, hexpand=True)
        frame.append(self.stack)
        self._build_state_page()
        if self.embed:
            self._build_web()

        self.watcher = ActivityWatcher(self._activity)
        self.connect('close-request', self._closing)
        self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._tick)
        self.watcher.start()
        self._show_state('checking')
        self.refresh()

    # ------------------------------------------------------------------ pages
    def _build_state_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        box.add_css_class('am-agent-state')
        img = Gtk.Image.new_from_icon_name('amerika-ai')
        img.set_pixel_size(72)
        box.append(img)
        self.state_title = _label('', 'am-agent-state-title', 0.5)
        self.state_text = _label('', 'am-sub', 0.5, wrap=True)
        self.state_text.set_max_width_chars(60)
        self.state_text.set_justify(Gtk.Justification.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(28, 28)
        self.state_btn = Gtk.Button(halign=Gtk.Align.CENTER)
        self.state_btn.add_css_class('am-primary')
        self.state_btn.connect('clicked', lambda *_: self._state_action())
        self._state_action = lambda: None
        for w in (self.state_title, self.state_text, self.spinner, self.state_btn):
            box.append(w)
        self.stack.add_named(box, 'state')

    def _build_web(self):
        # Device credentials and chat data stay in the lifetime of this window.
        session = WebKit.NetworkSession.new_ephemeral()
        session.connect('download-started', lambda _s, download: download.cancel())  # the Control UI never needs downloads
        self.web = WebKit.WebView(network_session=session)
        settings = self.web.get_settings()
        for name, value in (('enable_developer_extras', False), ('enable_write_console_messages_to_stdout', False),
                            ('enable_media_stream', False), ('enable_webrtc', False), ('javascript_can_open_windows_automatically', False)):
            try:
                getattr(settings, 'set_' + name)(value)
            except (AttributeError, TypeError):
                pass
        self.web.set_background_color(Gdk.RGBA(red=0.043, green=0.039, blue=0.078, alpha=1))
        self.web.connect('decide-policy', self._decide)
        self.web.connect('permission-request', lambda _v, request: (request.deny(), True)[1])
        self.web.connect('context-menu', lambda *_: True)
        self.web.connect('load-failed', self._load_failed)
        self.web.connect('load-changed', self._load_changed)
        self.web.connect('web-process-terminated', lambda *_: self._show_state('unreachable'))
        self.stack.add_named(self.web, 'web')

    # ------------------------------------------------------------------ navigation policy (loopback only)
    def _decide(self, view, decision, dtype):
        kinds = WebKit.PolicyDecisionType
        try:
            if dtype in (kinds.NAVIGATION_ACTION, kinds.NEW_WINDOW_ACTION):
                action = decision.get_navigation_action()
                uri = action.get_request().get_uri() or ''
                if model.is_gateway_url(uri, self.status.port) or uri == 'about:blank':
                    if dtype == kinds.NEW_WINDOW_ACTION:
                        decision.ignore()
                        view.load_uri(uri)
                    else:
                        decision.use()
                else:
                    decision.ignore()
                    if action.is_user_gesture() and uri.startswith(('http://', 'https://')):
                        Gio.AppInfo.launch_default_for_uri(uri, None)  # a link the user clicked goes to the real browser
                return True
            if dtype == kinds.RESPONSE:
                if decision.is_mime_type_supported():
                    decision.use()
                else:
                    decision.ignore()
                return True
        except (GLib.Error, AttributeError):
            decision.ignore()
            return True
        return False

    def _load_failed(self, _view, _event, _uri, _error):
        self._loading = False
        self._live = False
        self._show_state('unreachable')
        return True

    def _load_changed(self, _view, event):
        if event == WebKit.LoadEvent.FINISHED:
            self._loading = False

    # ------------------------------------------------------------------ state machine
    def refresh(self):
        cli.in_thread(cli.status, self._status_loaded)

    def _tick(self):
        if not self._starting:
            self.refresh()
        return True

    def _status_loaded(self, status):
        if isinstance(status, Exception):
            status = model.Status.broken(str(status))
        self.status = status
        first = not self._status_seen
        self._status_seen = True
        if first and status.installed and not status.running and (self._auto_start or status.autostart) and not self._auto_tried:
            self._auto_tried = True
            self._start()
        self.banner.set_visible(status.installed and not status.error and not status.has_key)
        self._update_header()
        state = model.window_state(status, self._starting)
        if state == 'live':
            if not self._live:
                self._open_dashboard()
        else:
            if self._live:
                self._live = False
                if self.web is not None:
                    self.web.load_uri('about:blank')
            self._show_state(state)

    def _activity(self, state, text, since):
        self.activity = (state, text, since)
        self._update_header()

    def _update_header(self):
        st = self.status
        state, text, _since = self.activity
        self.status_label.set_text(model.header_text(st, state, text).upper())
        for c in ('idle', 'thinking', 'tool', 'error', 'off'):
            self.dot.remove_css_class(c)
        self.dot.add_css_class(state if (st.installed and st.running) else 'off')
        self.stop_btn.set_visible(st.installed)
        self.stop_btn.set_sensitive(not self._starting)
        self.stop_btn.set_label('Stop' if st.running else 'Start')
        self.reload_btn.set_visible(st.installed and st.running)

    def _show_state(self, kind):
        titles = {
            'checking': ('CHECKING THE AGENT…', 'One moment.', None, True),
            'not-installed': ('AMERIKA AGENT IS NOT INSTALLED', 'Install the amerika-agent package, then open this window again. '
                              'Open Amerika Software and search for "Amerika Agent", or run  sudo apt install amerika-agent.',
                              ('Open Amerika Software', self._open_software), False),
            'stopped': ('THE AGENT IS STOPPED', 'Start it to chat with your agent. It only runs on this computer.',
                        ('Start Amerika Agent', self._start), False),
            'starting': ('STARTING THE AGENT…', 'This takes a few seconds.', None, True),
            'broken': ('THE AGENT ENGINE REPORTS A PROBLEM', (self.status.error or 'Unknown error') + '. Open Settings and run the diagnostics.',
                       ('Open Settings', open_settings), False),
            'unreachable': ('CANNOT REACH THE AGENT', 'The Control UI did not load. The engine may still be starting.',
                            ('Try again', self.reload), False),
            'browser': ('OPENED IN YOUR BROWSER', 'The embedded view needs WebKitGTK (package gir1.2-webkit-6.0), which is not installed, '
                        'so the Control UI opened in your default browser.', ('Open it again', self._open_dashboard), False),
        }
        title, text, action, spin = titles[kind]
        self.state_title.set_text(title)
        self.state_text.set_text(text)
        self.spinner.set_visible(spin)
        self.spinner.set_spinning(spin)
        self.state_btn.set_visible(bool(action))
        if action:
            self.state_btn.set_label(action[0])
            self._state_action = action[1]
        self.stack.set_visible_child_name('state')

    # ------------------------------------------------------------------ actions
    def _open_software(self):
        from ..shell import apps
        info = apps.lookup('amerika-software')
        if info:
            apps.launch(info)

    def _start(self):
        self._starting = True
        self._update_header()
        self._show_state('starting')

        def finished(result):
            self._starting = False
            ok, msg = result if isinstance(result, tuple) else (False, 'Could not start the agent.')
            if not ok:
                self.status = model.Status.broken(msg or 'Could not start the agent')
            self.refresh()
        cli.in_thread(lambda: cli.control('start'), finished)

    def _stop_or_start(self):
        if not self.status.running:
            self._start()
            return
        self._starting = True
        self.stop_btn.set_sensitive(False)

        def finished(_result):
            self._starting = False
            self._live = False
            if self.web is not None:
                self.web.load_uri('about:blank')
            self.refresh()
        cli.in_thread(lambda: cli.control('stop'), finished)

    def reload(self):
        self._live = False
        self.refresh()

    def _open_dashboard(self):
        """Fetch the one-time pairing URL (in memory only) and show it: embedded, or in the default browser as a fallback."""
        if self._loading:
            return
        self._loading = True
        self._live = True

        def loaded(url):
            if not isinstance(url, str) or not url:
                self._loading = False
                self._live = False
                self._show_state('unreachable')
                return
            if not model.is_gateway_url(url, self.status.port):
                self._loading = False
                self._live = False
                self.status = model.Status.broken('The agent returned an address outside this computer, so it was not opened')
                self._show_state('broken')
                return
            if self.web is not None:
                self.stack.set_visible_child_name('web')
                self.web.load_uri(url)
            else:
                self._loading = False
                try:
                    Gio.AppInfo.launch_default_for_uri(url, None)
                except GLib.Error:
                    pass
                self._show_state('browser')
        cli.in_thread(cli.dashboard_url, loaded)

    def _closing(self, *_):
        self.watcher.stop()
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        return False

    def shoot(self, path):
        from ..shell.app import save_widget
        return save_widget(self, Path(path))


class AgentApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if self.win is None:
            self._setup()
            self.win = AgentWindow(self, auto_start='--start' in args,
                                   embed=os.environ.get('AMERIKA_AGENT_WINDOW_NOWEB') != '1')
        elif '--start' in args and not self.win.status.running:
            self.win._start()
        self.win.present()
        return 0

    def _setup(self):
        display = Gdk.Display.get_default()
        dev_icons = os.environ.get('AMERIKA_ICONS')
        icons = Gtk.IconTheme.get_for_display(display)
        if dev_icons:
            icons.set_search_path([dev_icons] + list(icons.get_search_path() or []))
        Gtk.Settings.get_default().set_property('gtk-icon-theme-name', 'AmerikaOS')
        s = common.load_settings()
        theme.apply(s.get('accent', '#ff2e63'), s.get('secondary', '#19e3ff'))


def main(argv=None):
    return AgentApp().run(argv if argv is not None else sys.argv)


if __name__ == '__main__':
    sys.exit(main())
