"""Settings pages "Home & Caster" and "Top bar" built and driven in a private session (run via claude_os_rig.sh). No system changes:
settings.json lives in the rig's throwaway XDG_CONFIG_HOME. Screenshots go to dist/claude-os/."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/os'))
OUT = Path(os.environ.get('CLAUDE_OS_SHOTS') or ROOT / 'dist/claude-os')
OUT.mkdir(parents=True, exist_ok=True)
os.environ.update({'AMERIKA_SETTINGS_FAKE': '1', 'AMERIKA_ICONS': str(ROOT / 'src/os/icons'), 'AMERIKA_SHARE': str(ROOT / 'src/os/amerika'), 'GTK_A11Y': 'none'})

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

Gtk.init()
from amerika import common  # noqa: E402
from amerika.settings.app import SettingsApp  # noqa: E402
from amerika.shell import barlayout, home  # noqa: E402
from amerika.shell.app import save_widget  # noqa: E402

failures = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        failures.append(name)


def settle(seconds=0.5):
    end = time.monotonic() + seconds
    ctx = GLib.MainContext.default()
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def shot(app, name):
    settle(0.7)
    ok = save_widget(app.win, OUT / name)
    check('screenshot ' + name, ok)


def texts(widget):
    out = []

    def walk(w):
        if isinstance(w, Gtk.Label):
            out.append(w.get_text())
        child = w.get_first_child()
        while child:
            walk(child)
            child = child.get_next_sibling()
    walk(widget)
    return out


def find(widget, pred):
    hits = []

    def walk(w):
        if pred(w):
            hits.append(w)
        child = w.get_first_child()
        while child:
            walk(child)
            child = child.get_next_sibling()
    walk(widget)
    return hits


def button_with(widget, text):
    return next(iter(find(widget, lambda w: isinstance(w, Gtk.Button) and text in ' '.join(texts(w)))), None)


app = SettingsApp()
assert app.register(None)
app.activate()
settle(0.5)

# ---- Home & Caster
app.show_page('home')
page = app._built['home'].get_child().get_child()
settle(0.5)
check('opt-in card is shown before the user answers', any('CLAUDE-FIRST MODE' in t for t in texts(page)))
check('current style is Classic', home.mode(common.load_settings()) == 'off')
shot(app, 'settings-home-classic.png')
page.mode_buttons['claude'].emit('clicked')
settle(0.3)
s = common.load_settings()
check('Claude first applies coherent defaults', (s['home_mode'], s['dock_enabled'], s['copilot_app'], s['bar_preset']) == ('claude', False, 'caster', 'home'), s['home_mode'])
check('a snapshot of the old setup is stored', isinstance(s.get('claude_first_snapshot'), dict) and s['claude_first_snapshot']['dock_enabled'] is True)
check('the opt-in card is gone and a Revert button appears', not any('CLAUDE-FIRST MODE' in t for t in texts(page)) and button_with(page, 'Revert to previous settings') is not None)
shot(app, 'settings-home-claude.png')
page.mode_buttons['chatgpt'].emit('clicked')
settle(0.3)
check('ChatGPT first keeps the original snapshot', common.load_settings()['home_mode'] == 'chatgpt' and common.load_settings()['claude_first_snapshot']['home_mode'] == 'off')
button_with(page, 'Revert to previous settings').emit('clicked')
settle(0.3)
s = common.load_settings()
check('Revert restores home mode, dock and Copilot key', (s['home_mode'], s['dock_enabled'], s['copilot_app']) == ('off', True, 'claude') and 'claude_first_snapshot' not in s, (s['home_mode'], s['dock_enabled'], s['copilot_app']))
check('the Revert button is gone again', button_with(page, 'Revert to previous settings') is None)
page.home_row.drop.set_selected(0)       # home app: Claude
settle(0.3)
check('home app dropdown writes home_mode', common.load_settings()['home_mode'] == 'claude')
page.dock_row.switch.set_active(True)
settle(0.3)
check('dock switch writes dock_enabled', common.load_settings()['dock_enabled'] is True)
sample = page.sample_labels['chatgpt']
check('text size sample exists for both apps', set(page.sample_labels) == {'claude', 'chatgpt'} and sample.get_attributes() is not None)
rows = find(page, lambda w: isinstance(w, Gtk.Scale))
check('text size sliders run 0.8 to 2.0', len(rows) == 2 and all(abs(r.get_adjustment().get_lower() - 0.8) < 1e-6 and abs(r.get_adjustment().get_upper() - 2.0) < 1e-6 for r in rows))
check('the Electron note is on the page', any('ignores that flag' in t or 'ignored' in t or 'ignores' in t for t in texts(page)))
shot(app, 'settings-home-after.png')

# ---- AI page carries the one-time card too (fresh state)
s = common.load_settings()
s['claude_os_prompt'] = 'pending'
s['home_mode'] = 'off'
common.save_settings(s)
app._built.pop('ai', None)
app.show_page('ai')
settle(0.4)
check('AI & Assistants page shows the opt-in card', any('CLAUDE-FIRST MODE' in t for t in texts(app._built['ai'])))

# ---- Top bar
common.save_settings(common.load_settings())
app.show_page('topbar')
page = app._built['topbar'].get_child().get_child()
settle(0.5)
check('every widget has a row', set(page.rows) == set(barlayout.WIDGETS), sorted(page.rows))
check('preview bar is drawn', page.preview is not None and len(texts(page.preview)) >= 6, texts(page.preview))
shot(app, 'settings-topbar.png')
page.rows['tray'].switch.set_active(False)
settle(0.3)
check('toggling a widget changes bar_layout', 'tray' not in barlayout.zones(common.load_settings()['bar_layout'])['right'])
check('preview follows the change', 'SYSTEM TRAY' not in texts(page.preview))
page.rows['clock'].zone_drop.set_selected(2)       # right
settle(0.3)
check('choosing a zone moves the widget', 'clock' in barlayout.zones(common.load_settings()['bar_layout'])['right'])
up = button_with(page.rows['bell'], 'Up')
before = barlayout.zones(common.load_settings()['bar_layout'])['right']
up.emit('clicked')
settle(0.3)
after = barlayout.zones(common.load_settings()['bar_layout'])['right']
check('Up moves a widget earlier in its zone', after.index('bell') == before.index('bell') - 1, (before, after))
hour = next(iter(find(page, lambda w: isinstance(w, Gtk.DropDown) and [o[1] for o in getattr(w, 'options', [])] == ['12-hour', '24-hour'])))
hour.set_selected(1)
settle(0.3)
check('24-hour clock option is saved', common.load_settings()['bar_clock_format']['hour24'] is True)
shot(app, 'settings-topbar-custom.png')
button_with(page, 'Reset to default').emit('clicked')
settle(0.4)
s = common.load_settings()
check('Reset to default restores the classic bar', barlayout.zones(s['bar_layout']) == barlayout.zones(None) and s['bar_height'] == 36 and s['bar_clock_format']['hour24'] is None)
button_with(page, 'Use the Home layout').emit('clicked')
settle(0.4)
check('the Home preset puts clock and date in the centre', barlayout.zones(common.load_settings()['bar_layout'])['center'] == ['clock', 'date'])
shot(app, 'settings-topbar-home.png')

print('CLAUDE-OS SETTINGS RIG: %d failure(s)' % len(failures), failures, flush=True)
sys.exit(1 if failures else 0)
