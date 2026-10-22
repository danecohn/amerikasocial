"""Settings > Amerika Studio: Anthropic key, model, daily budget, Amerika Agent tools, and a shortcut to the Studio hub.

Keys go through amerika_studio.keys.KeysWindow (password entry -> keyring helper over stdin). This page only ever shows
"saved / not saved".
"""
import subprocess

from gi.repository import GLib, Gtk

from . import ui

try:
    from amerika_studio import agent_link, cli as studio_cli, common as studio, keys as studio_keys, ui as studio_ui
except ImportError:          # the package is optional: show how to get it
    studio = None

BUDGETS = [(500_000, '500 thousand tokens'), (1_000_000, '1 million tokens'), (2_000_000, '2 million tokens'),
           (5_000_000, '5 million tokens'), (10_000_000, '10 million tokens'), (0, 'Unlimited')]
REFRESH_SECONDS = 5


def build(app):
    box = ui.page('Amerika Studio', 'Describe it, Claude builds it: 3D, games, pixel art and chiptune.')
    if studio is None:
        box.append(ui.section('Not installed', ui.label(
            'Install the amerika-studio package (or the amerika-developer meta package) to use Amerika Studio. '
            'Open Amerika Software and search for "Amerika Developer", or run  sudo apt install amerika-developer.', 'am-sub', wrap=True)))
        return box

    paths = studio.Paths()
    state = {'status': None, 'busy': False}
    key_state = ui.label('', 'am-keystate')
    key_btn = ui.button('Set up Anthropic key', lambda: studio_keys.KeysWindow(None, parent=app.win, on_change=refresh).present(), primary=True)
    key_btn.set_halign(Gtk.Align.START)
    budget_text = ui.label('', 'am-sub')
    bridge_pill = ui.label('', 'am-pill off')
    agent_msg = ui.label('', 'am-sub', wrap=True)
    cfg = studio.load_settings(paths)

    def save(**changes):
        s = studio.load_settings(paths)
        s.update(changes)
        studio.save_settings(s, paths)

    model_row = ui.dropdown_row('Model', 'Used by all four apps unless they say otherwise',
                                [(m['id'], f'{m["name"]}  -  {m["note"]}') for m in studio.MODELS], cfg['model'],
                                lambda v: save(model=v))
    budget_row = ui.dropdown_row('Daily token budget', 'Studio stops asking Claude when it is used up', BUDGETS,
                                 cfg['daily_budget_tokens'] if cfg['daily_budget_tokens'] in [b[0] for b in BUDGETS] else 2_000_000,
                                 lambda v: (save(daily_budget_tokens=v), refresh()))
    reuse_row = ui.switch_row("Use Amerika Agent's key", 'Fall back to the key you saved for Amerika Agent when Studio has none',
                              cfg['reuse_agent_key'], lambda on: (save(reuse_agent_key=on), refresh()))

    def agent_changed(on):
        agent_msg.set_text('Working...')

        def work():
            return agent_link.set_agent_tools(on, paths)

        def done(msg, err):
            agent_msg.set_text(str(err) if err else msg)
        studio_ui.in_thread(work, done)
    agent_row = ui.switch_row('Amerika Agent can use these tools',
                              'Lets Amerika Agent drive Render, Engine, Sprite and Box. Anything that runs code still asks you first.',
                              cfg['agent_tools'], agent_changed)

    def refresh():
        if state['busy']:
            return
        state['busy'] = True
        studio_ui.in_thread(lambda: studio_cli.build_status(paths), on_status)

    def on_status(st, err):
        state['busy'] = False
        if err or not st:
            return
        state['status'] = st
        key_state.set_text('Key saved in your keyring' if st['shared_key'] else 'No key saved yet')
        key_state.remove_css_class('saved')
        if st['shared_key']:
            key_state.add_css_class('saved')
        key_btn.set_label('Change key' if st['shared_key'] else 'Set up Anthropic key')
        b = st['budget']
        budget_text.set_text(f'{b["used_today"]:,} tokens used today' + (f' of {b["daily_tokens"]:,}' if b['daily_tokens'] else ' (no limit)'))
        bridge_pill.set_text('BRIDGE ONLINE' if st['bridge'] else 'BRIDGE OFFLINE')
        for cls in ('on', 'off'):
            bridge_pill.remove_css_class(cls)
        bridge_pill.add_css_class('on' if st['bridge'] else 'off')

    def open_hub():
        try:
            subprocess.Popen(['amerika-studio-hub'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass

    head = Gtk.Box(spacing=10)
    head.append(ui.label('STATUS', 'am-label'))
    head.get_first_child().set_hexpand(True)
    head.append(bridge_pill)
    box.append(ui.section('Anthropic key', head, key_state, key_btn, reuse_row,
                          note='The key lives in your login keyring. The Studio apps talk to a local bridge on this computer and never see it.'))
    box.append(ui.section('Model and budget', model_row, budget_row, budget_text))
    box.append(ui.section('Amerika Agent', agent_row, agent_msg))
    hub_btn = ui.button('Open Amerika Studio', open_hub, primary=True)
    hub_btn.set_halign(Gtk.Align.START)
    box.append(ui.section('Studio', hub_btn,
                          note='Four apps: Amerika Render (Blender), Amerika Engine (Godot), Amerika Sprite and AmerikaBox. Projects live in ~/Studio.'))
    GLib.timeout_add_seconds(REFRESH_SECONDS, lambda: (refresh(), box.get_root() is not None)[1])
    refresh()
    return box
