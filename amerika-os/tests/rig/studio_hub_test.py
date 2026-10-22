"""Rig: the Amerika Studio hub, the keys dialog and the Settings page. Screenshots in dist/studio/."""
import json
import os
from pathlib import Path

from studio_rig import FAKE_KEY, OUT, T, kill_bridge, settle, shot, spin, widget_texts  # noqa: F401

from gi.repository import Gtk  # noqa: E402

from amerika_studio import common, hub, keyring, keys, ui  # noqa: E402

try:
    app = hub.HubApp()
    assert app.register(None)
    ui.setup()
    app.win = hub.Hub(app)
    app.win.present()
    win = app.win
    spin(lambda: win.status is not None, what='first status')
    spin(lambda: win.bridge_pill.get_text() == 'BRIDGE ONLINE', timeout=15, what='bridge started by the hub')
    assert win.key_state.get_text() == 'No key saved yet', win.key_state.get_text()
    assert win.tiles['render'].p_installed.get_text() == 'INSTALLED'
    assert win.tiles['engine'].p_installed.get_text() == 'NOT INSTALLED'
    shot(win, 'hub-1-fresh.png')

    # key dialog: the key leaves the entry at once and is never shown
    dlg = keys.KeysWindow(None, parent=win, on_change=win.refresh)
    dlg.present()
    spin(lambda: dlg.state.get_text() == 'No key saved', what='dialog state')
    shot(dlg, 'keys-1-empty.png')
    dlg.entry.set_text(FAKE_KEY)
    dlg.save()
    assert dlg.entry.get_text() == ''
    spin(lambda: dlg.state.get_text() == 'Key saved in your keyring', what='key saved')
    assert FAKE_KEY not in ' '.join(widget_texts(dlg)), 'key leaked into the dialog'
    assert keyring.lookup() == FAKE_KEY
    log = (T / 'secrets/argv.log').read_text()
    assert 'FAKE' not in log, 'key was passed on a command line'
    shot(dlg, 'keys-2-saved.png')
    dlg.destroy()
    spin(lambda: win.key_state.get_text() == 'Key saved in your keyring', what='hub shows the key')
    assert FAKE_KEY not in ' '.join(widget_texts(win))
    assert win.tiles['box'].p_key.get_text() == 'KEY SET'

    # model, budget, new game, agent switch
    win.model_dd.set_selected(1)
    spin(lambda: common.load_settings()['model'] == 'claude-opus-5-5', what='model saved')
    win.budget_dd.set_selected(0)
    spin(lambda: common.load_settings()['daily_budget_tokens'] == 500000, what='budget saved')
    win.game_entry.set_text('Neon Racer')
    win.new_game()
    assert (common.Paths().project_dir('engine') / 'Neon-Racer/project.godot').is_file()
    win.refresh_recent()
    win.tiles['sprite'].own.set_active(True)        # asks for the sprite key: opens the dialog, own key not stored yet
    settle(0.5)
    shot(win, 'hub-2-configured.png')
    for w in list(Gtk.Window.list_toplevels()):
        if isinstance(w, keys.KeysWindow):
            w.destroy()

    # Settings > Amerika Studio
    from amerika.settings.app import SettingsApp
    sapp = SettingsApp()
    assert sapp.register(None)
    sapp._pending_page = 'studio'
    sapp.activate()
    sapp.win.set_default_size(1100, 820)
    spin(lambda: 'studio' in sapp._built, what='studio page built')
    settle(1.0)
    texts = ' '.join(widget_texts(sapp._built['studio']))
    assert 'could not be loaded' not in texts, texts
    assert 'Set up Anthropic key' in texts or 'Change key' in texts
    assert FAKE_KEY not in texts
    shot(sapp.win, 'settings-studio.png')
    print('STUDIO HUB RIG OK', flush=True)
finally:
    kill_bridge()
