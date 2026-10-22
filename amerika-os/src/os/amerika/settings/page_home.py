"""Settings > Home & Caster: Claude-first mode (opt-in, reversible), the home app, dock, Copilot key and AI text size."""
import copy

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402

from .. import common
from ..shell import home
from . import ui

MODE_TEXT = {
    'claude': ('Claude first', 'Claude is the home screen: maximized under the top bar, no dock, the Copilot key opens the Caster, and the top bar gets a Home button.'),
    'chatgpt': ('ChatGPT first', 'The same, with the ChatGPT app as the home screen.'),
    'off': ('Classic desktop', 'The wallpaper desktop with the dock and the Copilot key opening a single app, as before.'),
}
COPILOT = [('caster', 'The Caster (choose Claude or ChatGPT)'), ('claude', 'Claude'), ('chatgpt', 'ChatGPT'),
           ('agent', 'Amerika Agent'), ('ask', 'Ask me each time')]
SCALE_NOTE = ('The text size is passed to the app as Electron\'s --force-device-scale-factor flag when Amerika starts it. '
              'It is an application of the app\'s own scaling: if a version of the app ignores that flag, the size will not change '
              'and only the app\'s own zoom (Ctrl + plus) can. Amerika does not modify the apps.')


def shell_action(name):
    """Ask the running shell to do something (Control D-Bus). Returns False when the shell is not running."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync('org.amerika.Shell', '/Control', 'org.amerika.Control', 'Action', GLib.Variant('(s)', (name,)), None,
                      Gio.DBusCallFlags.NONE, 1500, None)
        return True
    except GLib.Error:
        return False


def commit(app, new_settings):
    """Persist a complete settings dict (also lets keys be removed, which the app's merge-save cannot do)."""
    common.save_settings(new_settings)
    app.settings = new_settings
    app._saved_settings = copy.deepcopy(new_settings)
    return new_settings


def fresh():
    return common.load_settings()


def opt_in_card(app, on_done=None):
    """The one-time prompt card; shown on this page and on AI & Assistants while the user has not answered."""
    s = fresh()
    if s.get('claude_os_prompt') in ('answered', 'dismissed') or home.mode(s) != 'off':
        return None

    def switch():
        commit(app, home.apply_style(fresh(), 'claude'))
        on_done and on_done()

    def later():
        s2 = fresh()
        s2['claude_os_prompt'] = 'dismissed'
        commit(app, s2)
        on_done and on_done()
    buttons = Gtk.Box(spacing=10)
    buttons.append(ui.button('Switch to Claude-first mode', switch, primary=True))
    buttons.append(ui.button('Not now', later))
    card = ui.section('NEW: CLAUDE-FIRST MODE', ui.label(
        'Make Claude your home screen: no dock, Claude fills the screen under the top bar, the Copilot key opens the Caster to switch '
        'between Claude and ChatGPT, and the Windows key opens the full app menu. Nothing changes unless you press the button, and '
        'one click on "Revert" in Settings > Home & Caster brings your current setup back.', 'am-sub', wrap=True), buttons)
    card.add_css_class('am-claude-first')
    return card


def build(app):
    box = ui.page('Home & Caster', 'Choose what the computer opens to, what the Copilot key does, and how big the AI apps\' text is.')
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    box.append(body)
    state = {'scales': {k: home.text_scale(fresh(), k) for k in home.APPS}}

    def render():
        ui.clear(body)
        s = fresh()
        style = home.current_style(s)
        prompt = opt_in_card(app, render)
        if prompt is not None:
            body.append(prompt)

        # ---- mode selector
        cards = Gtk.Box(spacing=12, homogeneous=True)
        box.mode_buttons = {}
        for key in ('claude', 'chatgpt', 'off'):
            title, text = MODE_TEXT[key]
            b = Gtk.Button()
            b.add_css_class('am-mode-card')
            if key == style:
                b.add_css_class('selected')
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            col.append(ui.label(title.upper(), 'am-appname'))
            col.append(ui.label(text, 'am-sub', wrap=True))
            b.set_child(col)
            b.connect('clicked', lambda _b, k=key: pick_style(k))
            cards.append(b)
            box.mode_buttons[key] = b
        mode_children = [cards]
        if isinstance(s.get('claude_first_snapshot'), dict):
            mode_children.append(ui.row('Your previous setup is saved', 'Revert restores the home mode, dock, Copilot key and top bar you had.',
                                        ui.button('Revert to previous settings', do_revert)))
            box.revert_button = mode_children[-1]
        body.append(ui.section('Mode', *mode_children, note='These switches are optional and reversible; nothing else on your account is touched.'))

        # ---- the pieces
        home_choice = ui.dropdown_row('Home app', 'Runs at login, stays running, and fills the screen under the top bar', home.MODE_CHOICES,
                                      home.mode(s), lambda v: change(home_mode=v))
        dock_row = ui.switch_row('Show the dock', 'Off hides the dock completely; your pinned apps are kept', bool(s.get('dock_enabled', True)),
                                 lambda on: change(dock_enabled=bool(on)))
        copilot_row = ui.dropdown_row('Copilot key', 'The key on your keyboard (Win+Shift+F23)', COPILOT, s.get('copilot_app', 'claude'),
                                      lambda v: change(copilot_app=v))
        box.home_row, box.dock_row, box.copilot_row = home_choice, dock_row, copilot_row
        tests = Gtk.Box(spacing=8)
        tests.append(ui.button('Open Caster', lambda: shell_action('caster')))
        tests.append(ui.button('Go home (Win+H)', lambda: shell_action('home')))
        body.append(ui.section('Home & keys', home_choice, dock_row, copilot_row, ui.row('Try it', 'Needs the Amerika shell to be running', tests)))

        # ---- text size
        rows = []
        box.sample_labels = {}
        for key in home.APPS:
            rows.append(scale_row(key))
        body.append(ui.section('AI app text size', *rows, note=SCALE_NOTE))

        body.append(ui.section('If something goes wrong', ui.label(
            'Choose "Classic desktop" above to put the dock and the old Copilot behaviour back. If the screen is unusable, press Ctrl+Alt+F3, '
            'log in, and run  amerika-settings --classic  (it needs no display), then log out and in. Win+Q closes the active window; Win+Space always opens the app menu.', 'am-sub', wrap=True)))

    def scale_row(key):
        name = home.APPS[key]['name']
        cur = state['scales'][key]
        sample = Gtk.Label(label='The quick brown fox')
        sample.add_css_class('am-appname')
        box.sample_labels[key] = sample

        def restyle(value):
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_scale_new(value))
            sample.set_attributes(attrs)
        restyle(cur)
        info = {'pending': cur}

        def moved(value):
            info['pending'] = round(float(value), 2)
            state['scales'][key] = info['pending']
            restyle(info['pending'])
        scale = ui.slider(home.SCALE_MIN, home.SCALE_MAX, 0.05, cur, moved, width=240, digits=2)
        apply_btn = ui.button('Apply', lambda: ask_apply(key, info))
        controls = Gtk.Box(spacing=10)
        controls.append(scale)
        controls.append(sample)
        controls.append(apply_btn)
        r = ui.row(name, 'Sample text at this size; applying restarts %s' % name, controls)
        r.scale = scale
        return r

    def ask_apply(key, info):
        name = home.APPS[key]['name']

        def go():
            s = fresh()
            sc = dict(s.get('ai_text_scale') or {})
            sc[key] = max(home.SCALE_MIN, min(home.SCALE_MAX, info['pending']))
            s['ai_text_scale'] = sc
            commit(app, s)
            shell_action('relaunch:' + key)
        ui.confirm(app.win, 'Restart %s?' % name, '%s has to restart to use the new text size. Unsaved work in the app may be lost.' % name,
                   go, yes_label='Restart %s' % name)

    def change(**kw):
        s = fresh()
        s.update(kw)
        commit(app, s)
        if 'home_mode' in kw or 'dock_enabled' in kw:
            GLib.idle_add(lambda: (render(), False)[1])

    def pick_style(style):
        commit(app, home.apply_style(fresh(), style))
        render()

    def do_revert():
        restored = home.revert(fresh())
        if restored is not None:
            commit(app, restored)
        render()

    box.render = render
    render()
    return box
