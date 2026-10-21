"""Settings > Amerika Agent: status, API keys (keyring only), models, permissions, autostart, channels, diagnostics.

Security: a pasted key is read from the Gtk.PasswordEntry once, the entry is cleared immediately, the key goes to
`amerika-agent key set <provider>` on stdin in a worker thread, and the page afterwards only ever shows
"Key saved in your keyring". The key is never stored on `self`, never logged, never put in argv or the environment.
"""
import subprocess

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

from ..agent import cli, model
from ..shell import apps

MODE_ROWS = [('ask', 'Ask every time', 'The agent asks before changing anything. Read-only tools still work.'),
             ('safe', 'Balanced (recommended)', 'Everyday changes run on their own (open apps, windows, volume). Anything that could lose or expose data asks first.'),
             ('trusted', 'Trusted', 'Also lets the agent read your clipboard and screen, close windows and read and write files in your home folder without asking. '
                                    'Shell commands, power-off, restart and delete always ask.')]
REFRESH_SECONDS = 5


def _label(text, css=None, xalign=0.0, wrap=False):
    lab = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    for c in (css or '').split():
        lab.add_css_class(c)
    return lab


def _card(*children, spacing=10, css=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    box.add_css_class('am-card')
    for c in (css or '').split():
        box.add_css_class(c)
    for c in children:
        box.append(c)
    return box


def _clear(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


class AgentPage:
    """Builds the page widget (`.widget`) for a SettingsApp-like `app` (needs .settings, .save(), ._set_mode())."""

    def __init__(self, app):
        self.app = app
        self.status = model.Status.missing()
        self.busy = False
        self.onboarding = model.Onboarding()
        self._onboarding_dismissed = False
        self._onboarding_active = False   # once the card has been shown it stays until the user finishes (the key step flips has_key)
        self._ob_rendered = None
        self._channels_rendered = None
        self._models_for = {}      # provider -> list of ids already loaded
        self._model_busy = False
        self._channel_busy = set()
        self._syncing = False
        self._channel_names = None
        self._loaded = False
        self.widget = self._build()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(box, f'set_margin_{m}')(26)
        head = Gtk.Box(spacing=12)
        head.append(apps.icon_image('amerika-ai', 40))
        title = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title.append(_label('AMERIKA AGENT', 'am-heading'))
        title.append(_label('An assistant that works on this computer for you, under your rules.', 'am-sub'))
        head.append(title)
        box.append(head)

        self.missing_card = _card(_label('AMERIKA AGENT IS NOT INSTALLED', 'am-label'),
                                  _label('Install the amerika-agent package to add the agent. Open Amerika Software and search for "Amerika Agent", '
                                         'or run  sudo apt install amerika-agent  in a terminal. Then come back to this page.', 'am-sub', wrap=True),
                                  css='am-agent-missing')
        sw = Gtk.Button(label='Open Amerika Software', halign=Gtk.Align.START)
        sw.add_css_class('am-secondary')
        sw.connect('clicked', lambda *_: (lambda i: apps.launch(i) if i else None)(apps.lookup('amerika-software')))
        self.missing_card.append(sw)
        box.append(self.missing_card)

        self.onboard_card = _card(css='am-agent-onboard')
        box.append(self.onboard_card)

        self.error_card = _card(_label('THE AGENT ENGINE REPORTS A PROBLEM', 'am-label'))
        self.error_text = _label('', 'am-sub', wrap=True)
        self.error_card.append(self.error_text)
        self.error_card.add_css_class('am-agent-error')
        box.append(self.error_card)

        # ---- status card
        self.status_card = _card()
        row = Gtk.Box(spacing=10)
        row.append(_label('STATUS', 'am-label'))
        row.get_first_child().set_hexpand(True)
        self.pill = _label('', 'am-pill off')
        row.append(self.pill)
        self.status_card.append(row)
        grid = Gtk.Grid(column_spacing=24, row_spacing=4)
        self.engine_value = _label('', 'am-appname')
        self.listen_value = _label('', 'am-appname am-mono')
        grid.attach(_label('ENGINE', 'am-label'), 0, 0, 1, 1)
        grid.attach(self.engine_value, 0, 1, 1, 1)
        grid.attach(_label('LISTENING ON', 'am-label'), 1, 0, 1, 1)
        grid.attach(self.listen_value, 1, 1, 1, 1)
        self.status_card.append(grid)
        ctl = Gtk.Box(spacing=8)
        self.btn_start = self._button('Start', 'am-primary', lambda: self._control('start'))
        self.btn_stop = self._button('Stop', 'am-secondary', lambda: self._control('stop'))
        self.btn_restart = self._button('Restart', 'am-secondary', lambda: self._control('restart'))
        self.btn_window = self._button('Open Agent window', 'am-secondary', self._open_window)
        for b in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_window):
            ctl.append(b)
        self.status_card.append(ctl)
        auto = Gtk.Box(spacing=10)
        self.autostart = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.autostart.connect('state-set', self._autostart_set)
        auto.append(self.autostart)
        auto.append(_label('Start the agent when I log in', None))
        self.status_card.append(auto)
        self.note = _label('', 'am-sub', wrap=True)
        self.status_card.append(self.note)
        box.append(self.status_card)

        # ---- keys
        self.keys_card = _card()
        self.keys_card.append(_label('API KEYS', 'am-label'))
        self.keys_card.append(_label('Your key goes straight into the login keyring (the same place your Wi-Fi passwords live). '
                                     'Amerika never shows it again and never writes it to a file.', 'am-sub', wrap=True))
        self.key_rows = {}
        for provider in model.PROVIDERS:
            self.key_rows[provider] = self._key_row(provider)
            self.keys_card.append(self.key_rows[provider]['box'])
        box.append(self.keys_card)

        # ---- models
        self.models_card = _card()
        self.models_card.append(_label('MODEL', 'am-label'))
        self.models_card.append(_label('Pick which model the agent uses. A provider needs a saved key first.', 'am-sub', wrap=True))
        self.model_drops = {}
        for provider in model.PROVIDERS:
            row = Gtk.Box(spacing=12)
            name = _label(model.PROVIDER_NAMES[provider], 'am-appname')
            name.set_size_request(170, -1)
            row.append(name)
            drop = Gtk.DropDown.new_from_strings(['No key saved'])
            drop.set_hexpand(True)
            drop.set_sensitive(False)
            drop.connect('notify::selected', lambda d, _p, p=provider: self._model_picked(p))
            row.append(drop)
            self.models_card.append(row)
            self.model_drops[provider] = drop
        box.append(self.models_card)

        # ---- permissions (the single source of truth is the Amerika AI mode setting)
        mode_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mode_col.append(_label('PERMISSIONS', 'am-label'))
        mode_col.append(_label('The same setting as AI & Assistants: one rule for Claude, ChatGPT and the agent. '
                               'Power-off, restart, delete and shell commands always ask.', 'am-sub', wrap=True))
        group = None
        self.mode_radios = {}
        for key, title, text in MODE_ROWS:
            row = Gtk.Box(spacing=12)
            radio = Gtk.CheckButton()
            if group:
                radio.set_group(group)
            group = group or radio
            radio.set_active(self.app.settings['ai']['mode'] == key)
            radio.connect('toggled', lambda r, k=key: self._mode_toggled(k) if r.get_active() else None)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            col.append(_label(title, 'am-appname'))
            col.append(_label(text, 'am-sub', wrap=True))
            row.append(radio)
            row.append(col)
            mode_col.append(row)
            self.mode_radios[key] = radio
        self.mode_card = _card(mode_col)
        box.append(self.mode_card)

        # ---- channels
        self.channels_card = _card()
        self.channels_card.append(_label('CHANNELS', 'am-label'))
        self.channels_card.append(_label('Let the agent receive messages from chat services. Off by default; turning one on asks you to confirm.',
                                         'am-sub', wrap=True))
        self.channel_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.channels_card.append(self.channel_rows)
        box.append(self.channels_card)

        # ---- diagnostics
        diag = _card()
        row = Gtk.Box(spacing=10)
        row.append(_label('DIAGNOSTICS', 'am-label'))
        row.get_first_child().set_hexpand(True)
        self.btn_doctor = self._button('Run diagnostics', 'am-secondary', self._run_doctor)
        row.append(self.btn_doctor)
        diag.append(row)
        self.doctor_view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.doctor_view.add_css_class('am-term')
        self.doctor_view.get_buffer().set_text('Press "Run diagnostics" to check the agent, its keyring access and its tools.')
        scroller = Gtk.ScrolledWindow(min_content_height=110, max_content_height=260, propagate_natural_height=True)
        scroller.set_child(self.doctor_view)
        diag.append(scroller)
        self.diag_card = diag
        box.append(diag)

        # ---- attribution
        about = _card(spacing=6)
        about.append(_label('BUILT ON OPENCLAW (MIT)', 'am-label'))
        about.append(_label('Amerika Agent bundles OpenClaw, an open-source agent engine, and connects it to this desktop, your login keyring '
                            'and the Amerika approval system. OpenClaw is released under the MIT licence by the OpenClaw contributors.',
                            'am-sub', wrap=True))
        link = Gtk.LinkButton.new_with_label(model.OPENCLAW_URL, 'github.com/openclaw/openclaw')
        link.set_halign(Gtk.Align.START)
        about.append(link)
        about.append(_label('Licence and notices: /usr/share/doc/amerika-agent/', 'am-sub am-mono'))
        box.append(about)
        return box

    def _button(self, text, css, fn):
        b = Gtk.Button(label=text)
        b.add_css_class(css)
        b.connect('clicked', lambda *_: fn())
        return b

    def _key_row(self, provider):
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        top = Gtk.Box(spacing=10)
        name = _label(model.PROVIDER_NAMES[provider], 'am-appname')
        name.set_hexpand(True)
        state = _label('', 'am-keystate')
        top.append(name)
        top.append(state)
        col.append(top)
        line = Gtk.Box(spacing=8)
        entry = Gtk.PasswordEntry(show_peek_icon=False, hexpand=True)
        entry.set_property('placeholder-text', 'Paste your key here')
        save = self._button('Save key', 'am-primary', lambda p=provider: self._save_key(p))
        remove = self._button('Remove key', 'am-secondary', lambda p=provider: self._remove_key(p))
        entry.connect('activate', lambda *_, p=provider: self._save_key(p))
        for w in (entry, save, remove):
            line.append(w)
        col.append(line)
        msg = _label('', 'am-sub', wrap=True)
        col.append(msg)
        return {'box': col, 'state': state, 'entry': entry, 'save': save, 'remove': remove, 'msg': msg}

    # ------------------------------------------------------------------ status refresh
    def _tick(self):
        if self.widget.get_mapped() and not self.busy:
            self.refresh()
        return True

    def refresh(self):
        cli.in_thread(cli.status, self._status_loaded)

    def _status_loaded(self, status):
        if isinstance(status, Exception):
            status = model.Status.broken(str(status))
        first = not self._loaded
        self._loaded = True
        self.status = status
        self._apply()
        if status.installed and not status.error:
            # one source of truth: the Amerika AI mode wins; push it to the engine if they differ
            if status.mode != self.app.settings['ai']['mode']:
                cli.in_thread(lambda m=self.app.settings['ai']['mode']: cli.config_set('mode', m))
            for provider in model.PROVIDERS:
                if status.providers[provider] and (first or provider not in self._models_for):
                    self._load_models(provider)
            if self._channel_names is None:
                self._channel_names = []
                cli.in_thread(lambda: cli.channels(status.channels), self._channels_loaded)
            else:
                self._fill_channels(self._channel_names_state())

    def _channel_names_state(self):
        names = [n for n, _ in self._channel_names] if self._channel_names else []
        return model.parse_channels('\n'.join(names), self.status.channels)

    def _apply(self):
        st = self.status
        view = model.page_view(st, self.busy)
        self.missing_card.set_visible(view['mode'] == 'not-installed')
        self.error_card.set_visible(view['mode'] == 'broken')
        self.error_text.set_text(f'{st.error}. Run diagnostics below for details.' if st.error else '')
        for card in (self.keys_card, self.models_card, self.mode_card, self.channels_card, self.diag_card):
            card.set_visible(view['controls'])
        self.status_card.set_visible(True)
        self.pill.set_text(view['gateway'])
        for tone in ('on', 'off', 'error'):
            self.pill.remove_css_class(tone)
        self.pill.add_css_class(view['tone'])
        engine = {'openclaw': 'OpenClaw'}.get(st.engine, st.engine)
        self.engine_value.set_text(f'{engine} {st.engine_version}'.strip() if st.installed else 'Not installed')
        self.listen_value.set_text(st.listen_text() if st.running else ('stopped' if st.installed else '-'))
        for btn, key in ((self.btn_start, 'start'), (self.btn_stop, 'stop'), (self.btn_restart, 'restart'), (self.btn_window, 'open_window')):
            btn.set_sensitive(view[key])
        self.autostart.set_sensitive(view['controls'] and not self.busy)
        self._syncing = True
        self.autostart.set_active(st.autostart)
        self._syncing = False
        for provider, row in self.key_rows.items():
            has = st.providers[provider]
            row['state'].set_text(model.key_text(has))
            row['state'].remove_css_class('saved')
            if has:
                row['state'].add_css_class('saved')
            row['remove'].set_sensitive(has and not self.busy)
            row['save'].set_sensitive(not self.busy)
            row['entry'].set_property('placeholder-text', 'Paste a new key to replace it' if has else 'Paste your key here')
        for provider, drop in self.model_drops.items():
            if not st.providers[provider]:
                drop.set_model(Gtk.StringList.new(['No key saved']))
                drop.set_sensitive(False)
                self._models_for.pop(provider, None)
        self._sync_mode_radios(self.app.settings['ai']['mode'])
        self._apply_onboarding(view['onboarding'])

    # ------------------------------------------------------------------ onboarding card
    def _apply_onboarding(self, wanted):
        show = (wanted or self._onboarding_active) and not self._onboarding_dismissed
        self.onboard_card.set_visible(show)
        if not show:
            return
        self._onboarding_active = True
        ob = self.onboarding
        rendered = (ob.step, ob.provider)
        if rendered == self._ob_rendered:  # never rebuild under the user's hands: it would wipe a half-typed key
            return
        self._ob_rendered = rendered
        _clear(self.onboard_card)
        steps = Gtk.Box(spacing=8)
        for i, title in enumerate(('1  Choose a provider', '2  Paste your key', '3  Pick permissions')):
            lab = _label(title.upper(), 'am-step' + (' active' if i == ob.step else (' done' if i < ob.step else '')))
            steps.append(lab)
        self.onboard_card.append(_label('GET STARTED', 'am-label'))
        self.onboard_card.append(steps)
        if ob.name == 'provider':
            self.onboard_card.append(_label('Which AI service should power your agent? You need an account and an API key from that service. '
                                            'You can add the other one later.', 'am-sub', wrap=True))
            row = Gtk.Box(spacing=10)
            for provider in model.PROVIDERS:
                b = self._button(model.PROVIDER_NAMES[provider], 'am-secondary', lambda p=provider: self._ob_provider(p))
                row.append(b)
            self.onboard_card.append(row)
        elif ob.name == 'key':
            self.onboard_card.append(_label(f'Paste your {model.PROVIDER_NAMES[ob.provider]} API key. It is stored in your keyring and never shown again.',
                                            'am-sub', wrap=True))
            line = Gtk.Box(spacing=8)
            entry = Gtk.PasswordEntry(show_peek_icon=False, hexpand=True)
            entry.set_property('placeholder-text', 'Paste your key here')
            self._ob_entry = entry
            save = self._button('Save key', 'am-primary', lambda: self._ob_save())
            entry.connect('activate', lambda *_: self._ob_save())
            line.append(entry)
            line.append(save)
            self.onboard_card.append(line)
            self._ob_msg = _label('', 'am-sub', wrap=True)
            self.onboard_card.append(self._ob_msg)
            back = self._button('Back', 'am-secondary', lambda: (ob.back(), self._apply_onboarding(True)))
            back.set_halign(Gtk.Align.START)
            self.onboard_card.append(back)
            entry.grab_focus()
        else:
            self.onboard_card.append(_label('How much may the agent do without asking? You can change this any time on this page.', 'am-sub', wrap=True))
            drop = Gtk.DropDown.new_from_strings([m[1] for m in MODE_ROWS])
            drop.set_selected(next((i for i, m in enumerate(MODE_ROWS) if m[0] == self.app.settings['ai']['mode']), 1))
            self._ob_mode = drop
            self.onboard_card.append(drop)
            done = self._button('Finish and start the agent', 'am-primary', self._ob_finish)
            done.set_halign(Gtk.Align.START)
            self.onboard_card.append(done)

    def _ob_provider(self, provider):
        self.onboarding.choose_provider(provider)
        self._apply_onboarding(True)

    def _ob_save(self):
        key = self._ob_entry.get_text()
        self._ob_entry.set_text('')  # cleared immediately: the key never lives in the widget
        self._ob_msg.set_text('Saving…' if key.strip() else 'Paste a key first.')
        if not key.strip():
            return
        provider = self.onboarding.provider
        self._store_key(provider, key, lambda ok, msg: self._ob_saved(ok, msg))

    def _ob_saved(self, ok, msg):
        if ok:
            self.onboarding.key_saved()
            self.status.providers[self.onboarding.provider] = True  # optimistic until the next refresh
            self._apply_onboarding(True)
            self.refresh()
        elif hasattr(self, '_ob_msg'):
            self._ob_msg.set_text(msg)

    def _ob_finish(self):
        mode = MODE_ROWS[self._ob_mode.get_selected()][0]
        self.onboarding.finish()
        self._onboarding_dismissed = True
        self._onboarding_active = False
        self.app._set_mode(mode)
        self.onboard_card.set_visible(False)
        self._control('start')

    # ------------------------------------------------------------------ keys
    def _save_key(self, provider):
        row = self.key_rows[provider]
        key = row['entry'].get_text()
        row['entry'].set_text('')  # cleared immediately
        if not key.strip():
            row['msg'].set_text('Paste a key first.')
            return
        row['msg'].set_text('Saving to your keyring…')
        self._store_key(provider, key, lambda ok, msg, r=row: self._key_saved(r, ok, msg))

    def _store_key(self, provider, key, done):
        """Hand the key to the CLI on a worker thread. The only reference is the closure below, dropped when it returns."""
        self._set_busy(True)

        def work():
            return cli.set_key(provider, key)

        def finished(result):
            self._set_busy(False)
            ok, msg = result if isinstance(result, tuple) else (False, 'The key could not be saved.')
            done(ok, msg)
        cli.in_thread(work, finished)
        key = None

    def _key_saved(self, row, ok, msg):
        row['msg'].set_text('Saved. Your key is in the keyring.' if ok else msg)
        self.refresh()

    def _remove_key(self, provider):
        row = self.key_rows[provider]
        row['msg'].set_text('Removing…')
        self._set_busy(True)

        def finished(result):
            self._set_busy(False)
            ok, msg = result if isinstance(result, tuple) else (False, 'Could not remove the key.')
            row['msg'].set_text('Key removed.' if ok else msg)
            self.refresh()
        cli.in_thread(lambda: cli.clear_key(provider), finished)

    # ------------------------------------------------------------------ models
    def _load_models(self, provider):
        self._models_for[provider] = []

        def finished(ids):
            if isinstance(ids, Exception):
                ids = []
            self._models_for[provider] = ids
            drop = self.model_drops[provider]
            self._syncing = True
            if ids:
                drop.set_model(Gtk.StringList.new(['Choose a model…'] + ids))
                current = self.status.model
                drop.set_selected(ids.index(current) + 1 if current in ids else 0)
                drop.set_sensitive(True)
            else:
                drop.set_model(Gtk.StringList.new(['Could not load models']))
                drop.set_sensitive(False)
            self._syncing = False
        cli.in_thread(lambda: cli.models(provider), finished)

    def _model_picked(self, provider):
        if self._syncing:
            return
        drop = self.model_drops[provider]
        ids = self._models_for.get(provider) or []
        pos = drop.get_selected()
        if not ids or pos == Gtk.INVALID_LIST_POSITION or pos < 1 or pos > len(ids):
            return
        chosen = ids[pos - 1]
        # only one model is active: reflect that in the other provider's picker
        other = next(p for p in model.PROVIDERS if p != provider)
        self._syncing = True
        self.model_drops[other].set_selected(0)
        self._syncing = False
        self.status.model = chosen
        cli.in_thread(lambda: cli.config_set('model', chosen), lambda r: self.note.set_text(
            f'Model: {chosen}' if isinstance(r, tuple) and r[0] else (r[1] if isinstance(r, tuple) else 'Could not set the model.')))

    # ------------------------------------------------------------------ mode (one source of truth: settings ai.mode)
    def _mode_toggled(self, mode):
        if self._syncing:
            return
        self.app._set_mode(mode)  # saves settings.json and (via mode_changed) updates every view and the engine

    def mode_changed(self, mode):
        """Called by SettingsApp._set_mode for every change, wherever it came from."""
        self._sync_mode_radios(mode)
        if self.status.installed and not self.status.error and self.status.mode != mode:
            self.status.mode = mode
            # SettingsApp sends the CLI update once, even if this page was never built.

    def _sync_mode_radios(self, mode):
        self._syncing = True
        if mode in self.mode_radios and not self.mode_radios[mode].get_active():
            self.mode_radios[mode].set_active(True)
        self._syncing = False

    # ------------------------------------------------------------------ gateway control
    def _set_busy(self, busy):
        self.busy = busy
        self._apply()

    def _control(self, action):
        labels = {'start': 'Starting the agent…', 'stop': 'Stopping the agent…', 'restart': 'Restarting the agent…'}
        self.note.set_text(labels[action])
        self._set_busy(True)

        def finished(result):
            self._set_busy(False)
            ok, msg = result if isinstance(result, tuple) else (False, 'The command failed.')
            self.note.set_text('' if ok else (msg or 'The command failed.'))
            self.refresh()
        cli.in_thread(lambda: cli.control(action), finished)

    def _autostart_set(self, _switch, on):
        if self._syncing:
            return False
        cli.in_thread(lambda: cli.control('enable' if on else 'disable'), lambda r: self.refresh())
        return False

    def _open_window(self):
        try:
            subprocess.Popen(['amerika-agent-window', '--start'] if self.status.running is False else ['amerika-agent-window'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as error:
            self.note.set_text(f'Could not open the Agent window: {error}')

    # ------------------------------------------------------------------ channels
    def _channels_loaded(self, result):
        if isinstance(result, Exception):
            result = []
        self._channel_names = result
        self._fill_channels(result)

    def _fill_channels(self, channels, force=False):
        signature = (tuple(channels), tuple(sorted(self._channel_busy)))
        if signature == self._channels_rendered and not force:
            return
        self._channels_rendered = signature
        _clear(self.channel_rows)
        if not channels:
            self.channel_rows.append(_label('No channels are available in this version.', 'am-sub'))
            return
        for name, on in channels:
            row = Gtk.Box(spacing=10)
            row.append(_label(name.capitalize(), 'am-appname'))
            row.get_first_child().set_hexpand(True)
            row.append(_label('ON' if on else 'OFF', 'am-pill ' + ('on' if on else 'off')))
            sw = Gtk.Switch(valign=Gtk.Align.CENTER)
            sw.set_active(on)
            sw.set_sensitive(name not in self._channel_busy)
            sw.connect('state-set', lambda s, state, n=name: self._channel_switched(s, state, n))
            row.append(sw)
            self.channel_rows.append(row)

    def _channel_switched(self, switch, state, name):
        if self._syncing:
            return False
        if not state:
            self._set_channel(name, False)
            return False
        # turning ON needs an explicit, plain-language confirmation; the switch stays off until confirmed
        self._confirm_channel(name)
        return True  # block the switch from flipping; _set_channel redraws the rows once it is done

    def _confirm_channel(self, name):
        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message(f'Turn on the {name.capitalize()} channel?')
        dialog.set_detail(model.CHANNEL_RISK)
        dialog.set_buttons(['Keep it off', 'Turn on'])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        self._last_dialog = dialog

        def answered(dlg, result):
            try:
                choice = dlg.choose_finish(result)
            except GLib.Error:
                choice = 0
            if choice == 1:
                self._set_channel(name, True)
            else:
                self._fill_channels(self._channel_names_state(), force=True)
        dialog.choose(self.widget.get_root(), None, answered)

    def _set_channel(self, name, on):
        self._channel_busy.add(name)

        def finished(result):
            self._channel_busy.discard(name)
            ok, msg = result if isinstance(result, tuple) else (False, 'The command failed.')
            self.note.set_text('' if ok else (msg or 'Could not change the channel.'))
            self.refresh()
        cli.in_thread(lambda: cli.channel_set(name, on), finished)

    # ------------------------------------------------------------------ diagnostics
    def _run_doctor(self):
        self.btn_doctor.set_sensitive(False)
        self.doctor_view.get_buffer().set_text('Running checks…')

        def finished(text):
            self.btn_doctor.set_sensitive(True)
            self.doctor_view.get_buffer().set_text(text if isinstance(text, str) else str(text))
        cli.in_thread(cli.doctor, finished)


def build(app):
    """Registry entry point (see settings/app.py PAGES)."""
    app.agent_page = AgentPage(app)
    return app.agent_page.widget
