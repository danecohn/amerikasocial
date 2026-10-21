"""Rig: Settings > Amerika Agent against the fake CLI. Screenshots in dist/agent-ui/."""
import hashlib
import json
import os
from pathlib import Path

from agent_rig import FAKE_KEY, fake_state, settle, shot, spin, widget_texts  # noqa: F401  (also repoints the environment)

from gi.repository import Gtk  # noqa: E402

from amerika import common  # noqa: E402
from amerika.settings.app import SettingsApp  # noqa: E402

app = SettingsApp()
assert app.register(None)
app._pending_page = 'agent'
app.activate()
spin(lambda: getattr(app, 'agent_page', None) is not None and app.agent_page._loaded, what='agent page status')
page = app.agent_page
app.win.set_default_size(1100, 900)
print('page built', flush=True)

# ---- fresh install: no key yet -> the guided 3-step card
spin(lambda: page.onboard_card.get_visible(), what='onboarding card')
assert page.onboarding.name == 'provider'
assert not page.missing_card.get_visible()
assert page.pill.get_text() == 'STOPPED', page.pill.get_text()
assert 'Not installed' not in page.engine_value.get_text() and 'OpenClaw 2026.10.5' == page.engine_value.get_text(), page.engine_value.get_text()
shot(app.win, 'settings-agent-1-onboarding-provider.png')
page._ob_provider('anthropic')
settle(0.3)
assert page.onboarding.name == 'key'
shot(app.win, 'settings-agent-2-onboarding-key.png')

# ---- a key that fails to save: the error must not echo the key, and the entry is cleared at once
os.environ['FAKE_AGENT_FAIL'] = 'key'
page._ob_entry.set_text(FAKE_KEY)
page._ob_save()
assert page._ob_entry.get_text() == '', 'entry must be cleared immediately'
spin(lambda: 'keyring error' in page._ob_msg.get_text() or '***' in page._ob_msg.get_text(), what='failure message')
assert FAKE_KEY not in ' '.join(widget_texts(page.widget)), 'key leaked into the UI'
assert page.onboarding.name == 'key'
del os.environ['FAKE_AGENT_FAIL']

# ---- the real save
page._ob_entry.set_text(FAKE_KEY)
page._ob_save()
assert page._ob_entry.get_text() == ''
spin(lambda: page.onboarding.name == 'mode', what='step 3')
assert fake_state()['keys'].get('anthropic'), 'fake CLI did not receive the key'
calls = [json.loads(line) for line in Path(os.environ['FAKE_AGENT_LOG']).read_text().splitlines()]
sets = [c for c in calls if c['argv'][:2] == ['key', 'set']]
assert sets and sets[-1]['stdin_sha256'] == hashlib.sha256(FAKE_KEY.encode()).hexdigest()
assert all(FAKE_KEY not in json.dumps(c['argv']) for c in calls) and not sets[-1]['key_in_env']
assert FAKE_KEY not in ' '.join(widget_texts(page.widget))
shot(app.win, 'settings-agent-3-onboarding-mode.png')
page._ob_mode.set_selected(0)
page._ob_finish()
spin(lambda: page.status.running and not page.onboard_card.get_visible(), what='agent started after onboarding')
assert app.settings['ai']['mode'] == 'ask'
assert json.loads((common.CONFIG / 'settings.json').read_text())['ai']['mode'] == 'ask'
spin(lambda: fake_state().get('mode') == 'ask', what='engine mode follows the Amerika AI mode')
assert page.key_rows['anthropic']['state'].get_text() == 'Key saved in your keyring'
assert page.key_rows['openai']['state'].get_text() == 'No key saved'
spin(lambda: page.model_drops['anthropic'].get_sensitive(), what='anthropic models')
assert not page.model_drops['openai'].get_sensitive()
page.model_drops['anthropic'].set_selected(2)
spin(lambda: fake_state().get('model') == 'claude-sonnet-4-fake', what='model saved')
spin(lambda: page.channel_rows.get_first_child() is not None and len(widget_texts(page.channel_rows)) > 2, what='channels list')
page.autostart.set_active(True)
spin(lambda: fake_state().get('autostart') is True, what='autostart')

# ---- one source of truth for the permission mode
page._mode_toggled('trusted')
spin(lambda: fake_state().get('mode') == 'trusted', what='mode pushed to the engine')
assert app.settings['ai']['mode'] == 'trusted' and page.mode_radios['trusted'].get_active()
app.show_page('ai')
settle(0.4)
assert app.mode_buttons['trusted'].get_active(), 'AI page radio must follow'
app.mode_buttons['safe'].set_active(True)  # change it from the other page
spin(lambda: fake_state().get('mode') == 'safe', what='AI page change reaches the engine')
assert page.mode_radios['safe'].get_active(), 'Agent page radio must follow'
app.show_page('agent')

# ---- channels: turning on needs a confirmation, off does not
assert page._channel_switched(None, True, 'telegram') is True  # blocked, dialog asked
assert page._last_dialog is not None and 'outside this computer' in page._last_dialog.get_detail()
settle(0.3)
assert fake_state()['channels'] == [], 'nothing may be enabled before the user confirms'
page._set_channel('telegram', True)  # what the "Turn on" button does
spin(lambda: fake_state()['channels'] == ['telegram'], what='telegram enabled')
spin(lambda: 'ON' in widget_texts(page.channel_rows), what='channel row shows ON')
assert page._channel_switched(None, False, 'telegram') is False
spin(lambda: fake_state()['channels'] == [], what='telegram disabled without a dialog')

# ---- diagnostics
page._run_doctor()
spin(lambda: 'All checks finished' in page.doctor_view.get_buffer().get_text(page.doctor_view.get_buffer().get_start_iter(),
                                                                           page.doctor_view.get_buffer().get_end_iter(), False), what='doctor output')
app.win.set_default_size(1100, 2000)
settle(0.8)
shot(app.win, 'settings-agent-4-running-full-page.png')
app.win.set_default_size(1100, 900)
shot(app.win, 'settings-agent-5-running-window.png')

# ---- stop / start buttons
page._control('stop')
spin(lambda: not page.status.running and page.pill.get_text() == 'STOPPED', what='stopped')
assert page.btn_start.get_sensitive() and not page.btn_stop.get_sensitive()
page._control('start')
spin(lambda: page.status.running, what='running again')

# ---- remove key
page._remove_key('anthropic')
spin(lambda: not fake_state()['keys'], what='key removed')
spin(lambda: page.onboard_card.get_visible() is False and page.key_rows['anthropic']['state'].get_text() == 'No key saved', what='state after removal')

# ---- not installed
os.environ['AMERIKA_AGENT_BIN'] = '/nonexistent/amerika-agent'
page.refresh()
spin(lambda: page.missing_card.get_visible() and page.pill.get_text() == 'NOT INSTALLED', what='not-installed state')
assert not page.keys_card.get_visible() and not page.btn_start.get_sensitive()
shot(app.win, 'settings-agent-6-not-installed.png')

# ---- broken engine
os.environ['AMERIKA_AGENT_BIN'] = str(Path(os.environ['T']) / 'broken-agent')
Path(os.environ['AMERIKA_AGENT_BIN']).write_text('#!/bin/sh\necho engine exploded >&2\nexit 9\n')
os.chmod(os.environ['AMERIKA_AGENT_BIN'], 0o755)
page.refresh()
spin(lambda: page.error_card.get_visible(), what='error state')
shot(app.win, 'settings-agent-7-broken.png')
print('SETTINGS RIG OK', flush=True)
