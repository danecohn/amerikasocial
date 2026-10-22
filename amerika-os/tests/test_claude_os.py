"""Unit tests for the Claude-first shell pieces: settings schema/migration/snapshot revert, the bar layout engine, the launch command
builder (scale flag), the Caster state machine and the home supervisor (fake clock and process). GTK behaviour is covered by
tests/rig/claude_os_test.sh.  Run: python3 -m unittest tests.test_claude_os"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src/os'))

from amerika import common, deskconf, firstrun, inputdev  # noqa: E402
from amerika.settings import api, pageindex  # noqa: E402
from amerika.shell import apps, barlayout, caster, home, launcher  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class SettingsSchema(unittest.TestCase):
    def test_defaults_keep_the_classic_desktop(self):
        d = common.DEFAULTS
        self.assertEqual(d['home_mode'], 'off')
        self.assertTrue(d['dock_enabled'])
        self.assertEqual(d['copilot_app'], 'claude')
        self.assertEqual(d['ai_text_scale'], {'chatgpt': 1.25, 'claude': 1.0})
        self.assertIsNone(d['bar_layout'])
        self.assertEqual(barlayout.zones(None)['left'][:1], ['launcher'])

    def test_api_accepts_new_values(self):
        self.assertEqual(api.validate('copilot_app', 'caster'), 'caster')
        self.assertEqual(api.validate('home_mode', 'claude'), 'claude')
        self.assertEqual(api.validate('dock_enabled', False), False)
        with self.assertRaises(ValueError):
            api.validate('home_mode', 'both')
        with self.assertRaises(ValueError):
            api.validate('bar_height', 100)

    def test_copilot_set_accepts_caster(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(common, 'CONFIG', tmp):
            self.assertEqual(inputdev.copilot_set('caster'), 'caster')
            self.assertEqual(common.load_settings()['copilot_app'], 'caster')
            with self.assertRaises(ValueError):
                inputdev.copilot_set('nothing')
        self.assertIn('caster', dict(inputdev.COPILOT_CHOICES))

    def test_pages_registered_and_deep_links(self):
        self.assertEqual(pageindex.resolve('home'), 'home')
        self.assertEqual(pageindex.resolve('caster'), 'home')
        self.assertEqual(pageindex.resolve('topbar'), 'topbar')
        self.assertEqual(pageindex.resolve('bar'), 'topbar')
        from amerika.settings import app as settings_app
        ids = {row[0] for row in settings_app.PAGES}
        self.assertTrue({'home', 'topbar'} <= ids)
        self.assertEqual(ids, set(pageindex.page_ids()))

    def test_bridge_config_carries_home_rules(self):
        off = deskconf.bridge_config(common.DEFAULTS)
        self.assertEqual(off['home'], {'enabled': False, 'key': None, 'classes': [], 'release': []})
        self.assertEqual(deskconf.bridge_config(common.DEFAULTS, release=['ChatGPT'])['home']['release'], ['chatgpt'])
        s = dict(common.DEFAULTS, home_mode='claude')
        cfg = deskconf.bridge_config(s)
        self.assertTrue(cfg['home']['enabled'])
        self.assertIn('com.anthropic.claude', cfg['home']['classes'])
        self.assertNotIn('chatgpt', cfg['home']['classes'])      # only the active home app's classes

    def test_migration_only_records_the_prompt(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / 'settings.json').write_text(json.dumps({'dock_pinned': ['a'], 'copilot_app': 'chatgpt'}))
        with mock.patch.object(common, 'CONFIG', tmp):
            self.assertTrue(firstrun.migrate_claude_os())
            self.assertFalse(firstrun.migrate_claude_os())      # once
            stored = json.loads((tmp / 'settings.json').read_text())
            loaded = common.load_settings()
        self.assertEqual(stored['claude_os_prompt'], 'pending')
        self.assertEqual(stored['dock_pinned'], ['a'])
        self.assertEqual(stored['copilot_app'], 'chatgpt')       # the existing setup is untouched
        self.assertEqual(loaded['home_mode'], 'off')
        self.assertTrue(loaded['dock_enabled'])


class ModeSnapshot(unittest.TestCase):
    def base(self):
        s = json.loads(json.dumps(common.DEFAULTS))
        s.update(copilot_app='chatgpt', dock_pinned=['x'], bar_layout=barlayout.preset('classic'))
        return s

    def test_apply_claude_style_sets_coherent_defaults(self):
        out = home.apply_style(self.base(), 'claude')
        self.assertEqual((out['home_mode'], out['dock_enabled'], out['copilot_app'], out['bar_preset']), ('claude', True, 'caster', 'home'))
        self.assertEqual((out['dock_position'], out['ui_style']), ('right', 'tesla'))
        self.assertEqual(barlayout.zones(out['bar_layout'])['center'], ['clock', 'date'])
        self.assertEqual(out['dock_pinned'], ['x'])               # dock_pinned is never touched
        self.assertEqual(out['claude_first_snapshot']['copilot_app'], 'chatgpt')

    def test_revert_restores_everything_and_removes_snapshot(self):
        before = self.base()
        out = home.apply_style(before, 'claude')
        back = home.revert(out)
        for k in home.MANAGED_KEYS:
            self.assertEqual(back.get(k), before.get(k), k)
        self.assertNotIn('claude_first_snapshot', back)
        self.assertIsNone(home.revert(back))

    def test_revert_removes_keys_that_did_not_exist(self):
        s = {'accent': '#fff'}
        back = home.revert(home.apply_style(s, 'claude'))
        for k in home.MANAGED_KEYS:
            self.assertNotIn(k, back)

    def test_switching_between_styles_keeps_the_original_snapshot(self):
        before = self.base()
        a = home.apply_style(before, 'claude')
        b = home.apply_style(a, 'chatgpt')
        self.assertEqual(b['home_mode'], 'chatgpt')
        self.assertEqual(home.revert(b)['copilot_app'], 'chatgpt')
        self.assertEqual(home.revert(b)['home_mode'], 'off')

    def test_classic_style_restores_dock_and_drops_snapshot(self):
        out = home.apply_style(home.apply_style(self.base(), 'claude'), 'off')
        self.assertEqual((out['home_mode'], out['dock_enabled'], out['copilot_app']), ('off', True, 'claude'))
        self.assertNotIn('claude_first_snapshot', out)

    def test_bad_style(self):
        with self.assertRaises(ValueError):
            home.apply_style({}, 'nope')

    def test_text_scale(self):
        self.assertEqual(home.text_scale({}, 'chatgpt'), 1.25)
        self.assertEqual(home.text_scale({}, 'claude'), 1.0)
        self.assertEqual(home.text_scale({'ai_text_scale': {'claude': 9}}, 'claude'), 2.0)
        self.assertEqual(home.text_scale({'ai_text_scale': {'claude': 0.1}}, 'claude'), 0.8)
        self.assertEqual(home.text_scale({'ai_text_scale': {'claude': 'x'}}, 'claude'), 1.0)
        self.assertEqual(home.text_scale({'ai_text_scale': 'bad'}, 'chatgpt'), 1.25)
        self.assertIsNone(home.scale_for_desktop_id({}, 'com.anthropic.Claude.desktop'))      # 1.0: no flag
        self.assertEqual(home.scale_for_desktop_id({}, 'chatgpt'), 1.25)
        self.assertIsNone(home.scale_for_desktop_id({}, 'amerika-files'))

    def test_rules_only_for_configured_classes(self):
        s = {'home_mode': 'chatgpt', 'home_classes': {'chatgpt': ['My-Class']}}
        r = home.rules(s)
        self.assertTrue(r['enabled'])
        self.assertIn('my-class', r['classes'])
        self.assertFalse(home.rules({'home_mode': 'off'})['enabled'])
        self.assertFalse(home.rules({'home_mode': 'junk'})['enabled'])
        wins = [{'cls': 'ChatGPT', 'normal': True}, {'cls': 'firefox', 'normal': True}, {'cls': 'chatgpt', 'normal': False}]
        self.assertEqual(len(home.home_windows(wins, s)), 1)


class BarLayout(unittest.TestCase):
    def test_default_and_presets_are_complete(self):
        for name in ('classic', 'home'):
            ids = [r['id'] for r in barlayout.preset(name)]
            self.assertEqual(sorted(ids), sorted(barlayout.WIDGETS))
        self.assertEqual(barlayout.zones(barlayout.preset('home'))['left'], ['launcher', 'home', 'title'])
        self.assertIn('ai_apps', barlayout.zones(barlayout.preset('classic'))['left'])

    def test_normalize_survives_garbage(self):
        for bad in (None, 'x', 5, [], [1, 'a', {}], [{'id': 'nope'}], [{'id': 'clock', 'zone': 'moon', 'order': 'x'}]):
            out = barlayout.normalize(bad)
            self.assertEqual(sorted(r['id'] for r in out), sorted(barlayout.WIDGETS))
            self.assertTrue(all(r['zone'] in barlayout.ZONES for r in out))
        self.assertTrue(barlayout.zones(None)['right'])        # None: the classic bar is shown

    def test_duplicates_dropped_and_missing_added_disabled(self):
        out = barlayout.normalize([{'id': 'clock', 'enabled': True, 'zone': 'left', 'order': 0}, {'id': 'clock', 'enabled': False, 'zone': 'right', 'order': 1}])
        self.assertEqual([r['id'] for r in out].count('clock'), 1)
        self.assertEqual(next(r for r in out if r['id'] == 'clock')['zone'], 'left')
        self.assertFalse(next(r for r in out if r['id'] == 'bell')['enabled'])      # a user layout never gains widgets by itself

    def test_edit_operations(self):
        lay = barlayout.preset('classic')
        lay = barlayout.set_enabled(lay, 'tray', False)
        self.assertNotIn('tray', barlayout.zones(lay)['right'])
        lay = barlayout.set_zone(lay, 'clock', 'right')
        self.assertEqual(barlayout.zones(lay)['right'][-1], 'clock')
        self.assertNotIn('clock', barlayout.zones(lay)['center'])
        lay = barlayout.move(lay, 'clock', -1)
        r = barlayout.zones(lay)['right']
        self.assertEqual(r.index('clock'), len(r) - 2)
        self.assertEqual(barlayout.move(lay, 'launcher', -5)[0]['id'], 'launcher')       # clamped
        with self.assertRaises(ValueError):
            barlayout.set_zone(lay, 'clock', 'top')

    def test_orders_are_renumbered(self):
        lay = barlayout.normalize([{'id': 'clock', 'zone': 'center', 'order': 77}, {'id': 'date', 'zone': 'center', 'order': 5}])
        center = [r for r in lay if r['zone'] == 'center']
        self.assertEqual([r['order'] for r in center], list(range(len(center))))
        self.assertEqual([r['id'] for r in center][:2], ['date', 'clock'])

    def test_clock_and_date_share_one_button(self):
        self.assertEqual(barlayout.runs(['date', 'clock']), [('date', 'clock')])
        self.assertEqual(barlayout.runs(['title', 'clock', 'tray']), [('title',), ('clock',), ('tray',)])
        self.assertEqual(barlayout.runs(['clock', 'date', 'bell']), [('clock', 'date'), ('bell',)])

    def test_clock_formats(self):
        t = time.struct_time((2026, 10, 21, 15, 4, 9, 2, 294, 0))
        c = barlayout.clock_format({'clock_24h': False})
        self.assertEqual(barlayout.format_time(c, t), '03:04 PM')
        c = barlayout.clock_format({'clock_24h': True, 'bar_clock_format': {'seconds': True}})
        self.assertEqual(barlayout.format_time(c, t), '15:04:09')
        c = barlayout.clock_format({'clock_24h': True, 'bar_clock_format': {'hour24': False}})
        self.assertFalse(c['hour24'])                           # the bar setting wins over the legacy one
        for style, text in (('short', 'WED 21 OCT'), ('numeric', '2026-10-21'), ('long', 'WEDNESDAY 21 OCTOBER 2026'), ('none', '')):
            self.assertEqual(barlayout.format_date({'date': style}, t), text)
        self.assertEqual(barlayout.clock_format({'bar_clock_format': {'date': 'weird'}})['date'], 'short')

    def test_height_opacity_clamped(self):
        self.assertEqual(barlayout.height({'bar_height': 5}), barlayout.HEIGHT_MIN)
        self.assertEqual(barlayout.height({'bar_height': 999}), barlayout.HEIGHT_MAX)
        self.assertEqual(barlayout.height({'bar_height': 'x'}), barlayout.HEIGHT_DEFAULT)
        self.assertEqual(barlayout.opacity({'bar_opacity': 0}), barlayout.OPACITY_MIN)
        self.assertEqual(barlayout.opacity({'bar_opacity': 7}), 1.0)

    def test_signature_changes_only_when_the_bar_would(self):
        a = dict(common.DEFAULTS)
        sig = barlayout.signature(a)
        self.assertEqual(sig, barlayout.signature(dict(a, caster_last='chatgpt', accent='#000000', dock_size=80)))
        for change in ({'bar_height': 44}, {'bar_opacity': 0.5}, {'bar_layout': barlayout.preset('home')},
                       {'bar_clock_format': {'seconds': True}}, {'clock_24h': True}, {'bar_ai_apps': ['x']}, {'home_mode': 'claude'}):
            self.assertNotEqual(sig, barlayout.signature(dict(a, **change)), change)


class LaunchCommand(unittest.TestCase):
    def test_strips_field_codes_and_adds_flag(self):
        self.assertEqual(apps.build_command('claude-desktop %U', 1.25), ['claude-desktop', '--force-device-scale-factor=1.25'])
        self.assertEqual(apps.build_command('chatgpt %U', 1.0), ['chatgpt', '--force-device-scale-factor=1'])
        self.assertEqual(apps.build_command('app %f %F %i %c %k %d %D %n %N'), ['app'])

    def test_uris_replace_field_codes(self):
        self.assertEqual(apps.build_command('claude-desktop %U', 1.5, ['claude://x/y']), ['claude-desktop', '--force-device-scale-factor=1.5', 'claude://x/y'])

    def test_quotes_percent_and_env_prefix(self):
        self.assertEqual(apps.build_command('env A=1 B=2 chatgpt --foo "a b" 100%%', 2.0),
                         ['env', 'A=1', 'B=2', 'chatgpt', '--force-device-scale-factor=2', '--foo', 'a b', '100%'])

    def test_existing_flag_is_replaced_not_duplicated(self):
        argv = apps.build_command('chatgpt --force-device-scale-factor=3 %U', 1.25)
        self.assertEqual(argv.count('--force-device-scale-factor=1.25'), 1)
        self.assertFalse(any(a.endswith('=3') for a in argv))

    def test_no_scale_leaves_command_alone(self):
        self.assertEqual(apps.build_command('chatgpt --x %U'), ['chatgpt', '--x'])

    def test_launch_uses_clean_environment_and_flag(self):
        class Info:
            def get_id(self):
                return 'chatgpt.desktop'

            def get_commandline(self):
                return 'chatgpt %U'
        seen = {}

        class P:
            def __init__(self, argv, **kw):
                seen['argv'], seen['env'] = argv, kw['env']

            def wait(self):
                pass
        with mock.patch.dict('os.environ', {'LD_PRELOAD': '/x/libgtk4-layer-shell.so.0'}), mock.patch.object(subprocess, 'Popen', P):
            self.assertTrue(apps.launch(Info(), scale=1.25))
        self.assertEqual(seen['argv'], ['chatgpt', '--force-device-scale-factor=1.25'])
        self.assertNotIn('LD_PRELOAD', seen['env'])

    def test_launch_without_scale_goes_through_gio(self):
        class Info:
            called = None

            def get_id(self):
                return 'x.desktop'

            def launch(self, uris, ctx):
                Info.called = (uris, ctx)
                return True
        self.assertTrue(apps.launch(Info(), scale=None))
        self.assertIsNotNone(Info.called)

    def test_category_groups(self):
        self.assertEqual(apps.group_of('Network;WebBrowser;'), 'Internet')
        self.assertEqual(apps.group_of('Utility;Development;'), 'Develop')
        self.assertEqual(apps.group_of('Game;'), 'Games')
        self.assertEqual(apps.group_of(''), 'Other')
        self.assertEqual(apps.group_of(None), 'Other')

    def test_ask_row_follows_home_mode(self):
        ids = launcher.ask_order({'home_mode': 'chatgpt', 'bar_ai_apps': ['com.anthropic.Claude', 'chatgpt']})
        self.assertEqual(ids[0], 'chatgpt')
        self.assertEqual(sorted(ids), ['chatgpt', 'com.anthropic.Claude'])
        self.assertEqual(launcher.ask_order({'home_mode': 'claude', 'bar_ai_apps': []})[0], 'com.anthropic.Claude')
        self.assertEqual(launcher.ask_order({'home_mode': 'off', 'bar_ai_apps': ['chatgpt', 'com.anthropic.Claude']})[0], 'chatgpt')


class CasterStateMachine(unittest.TestCase):
    def test_initial_focus_is_last_choice(self):
        st = caster.CasterState()
        st.open('chatgpt')
        self.assertEqual(st.focused, 'chatgpt')
        st.open('weird')
        self.assertEqual(st.focused, 'claude')

    def test_keys(self):
        st = caster.CasterState()
        st.open('claude')
        self.assertEqual(st.key('Right'), ('focus', 1))
        self.assertEqual(st.focused, 'chatgpt')
        self.assertEqual(st.key('Right'), ('focus', 0))         # wraps
        self.assertEqual(st.key('Left'), ('focus', 1))
        self.assertEqual(st.key('Tab'), ('focus', 0))
        self.assertEqual(st.key('ISO_Left_Tab'), ('focus', 1))
        self.assertEqual(st.key('Return'), ('choose', 'chatgpt'))
        self.assertEqual(st.key('KP_Enter'), ('choose', 'chatgpt'))
        self.assertEqual(st.key('1'), ('choose', 'claude'))
        self.assertEqual(st.key('2'), ('choose', 'chatgpt'))
        self.assertIsNone(st.key('3'))
        self.assertIsNone(st.key('x'))
        self.assertEqual(st.key('Escape'), ('close',))
        self.assertFalse(st.visible)
        self.assertIsNone(st.key('Return'))                      # keys do nothing while closed

    def test_copilot_key_again_cycles(self):
        st = caster.CasterState()
        st.open('claude')
        st.copilot_again()
        self.assertEqual(st.focused, 'chatgpt')
        st.copilot_again()
        self.assertEqual(st.focused, 'claude')

    def test_ago(self):
        now = 1_000_000
        self.assertEqual(caster.ago(None, now), 'never opened')
        self.assertEqual(caster.ago(now - 5, now), 'just now')
        self.assertEqual(caster.ago(now - 125, now), '2 min ago')
        self.assertEqual(caster.ago(now - 7300, now), '2 h ago')
        self.assertEqual(caster.ago(now - 86400, now), '1 day ago')
        self.assertEqual(caster.ago(now - 3 * 86400, now), '3 days ago')
        self.assertEqual(caster.ago(now + 50, now), 'just now')

    def test_ease_bounds(self):
        self.assertEqual(caster.ease_out(0), 0)
        self.assertEqual(caster.ease_out(1), 1)
        self.assertTrue(0 < caster.ease_out(0.5) < 1)


class Supervisor(unittest.TestCase):
    def make(self, **kw):
        self.clock = FakeClock()
        self.window = False
        self.launched = []
        self.gave_up = []

        def launch():
            self.launched.append(self.clock())
        self.sup = home.HomeSupervisor(lambda: self.window, launch, self.clock, on_give_up=lambda: self.gave_up.append(1), **kw)
        return self.sup

    def run_for(self, seconds, step=1.0):
        for _ in range(int(seconds / step)):
            self.clock.advance(step)
            self.sup.tick()

    def test_starts_the_app_once(self):
        self.make()
        self.sup.start()
        self.assertEqual(len(self.launched), 1)
        self.window = True
        self.run_for(5)
        self.assertEqual((self.sup.state, len(self.launched)), ('running', 1))

    def test_already_running_is_not_launched_again(self):
        self.make()
        self.window = True
        self.sup.start()
        self.assertEqual(self.launched, [])
        self.assertEqual(self.sup.state, 'running')

    def test_relaunch_after_close_with_backoff(self):
        self.make()
        self.sup.start()
        self.window = True
        self.run_for(10)
        self.window = False                                   # the user closed it
        self.run_for(1)
        self.assertEqual(self.sup.state, 'waiting')
        self.assertEqual(len(self.launched), 1)               # not instantly: backoff 2 s
        self.run_for(3)
        self.assertEqual(len(self.launched), 2)

    def test_backoff_grows_when_it_keeps_dying(self):
        self.make(backoff=(2, 4, 8, 16), startup_grace=5)
        self.sup.start()
        gaps = []
        for _ in range(4):
            self.window = True
            self.run_for(2)
            self.window = False
            n = len(self.launched)
            t0 = self.clock()
            while len(self.launched) == n and self.clock() - t0 < 60:
                self.run_for(1)
            gaps.append(self.launched[-1] - t0)
        self.assertEqual(gaps, sorted(gaps))
        self.assertGreater(gaps[-1], gaps[0])

    def test_stable_run_resets_the_backoff(self):
        self.make(backoff=(2, 4, 8), stable_after=30)
        self.sup.start()
        self.window = True
        self.run_for(40)
        self.window = False
        self.run_for(1)
        self.assertEqual(self.sup.failures, 1)
        self.run_for(3)
        self.assertEqual(len(self.launched), 2)
        self.window = True
        self.run_for(40)
        self.assertEqual(self.sup.failures, 0)

    def test_gives_up_when_it_never_shows_a_window(self):
        self.make(backoff=(1, 1), startup_grace=3, max_failures=3)
        self.sup.start()
        self.run_for(60)
        self.assertEqual(self.sup.state, 'gave-up')
        self.assertFalse(self.sup.active)
        self.assertEqual(self.gave_up, [1])
        n = len(self.launched)
        self.run_for(30)
        self.assertEqual(len(self.launched), n)               # no more launches

    def test_stop_stops_relaunching(self):
        self.make()
        self.sup.start()
        self.window = True
        self.run_for(5)
        self.sup.stop()
        self.window = False
        self.run_for(30)
        self.assertEqual((self.sup.state, len(self.launched)), ('stopped', 1))

    def test_pause_lets_an_intentional_restart_happen(self):
        self.make()
        self.sup.start()
        self.window = True
        self.run_for(5)
        self.sup.pause(20)
        self.window = False
        self.run_for(15)
        self.assertEqual(len(self.launched), 1)                # not relaunched while paused
        self.sup.start(launch_now=False)
        self.window = True
        self.run_for(3)
        self.assertEqual(self.sup.state, 'running')


class Wiring(unittest.TestCase):
    def test_bridge_has_home_rules_and_shortcut(self):
        js = (ROOT / 'src/os/amerika/bridge/bridge.js').read_text()
        self.assertIn('"Meta+H"', js)
        self.assertIn('CFG.home.enabled', js)
        self.assertIn('function homeApply', js)
        self.assertIn('!isHome(w)', js)                       # show-desktop / minimize skip the home window
        node = shutil.which('node')
        if node:
            self.assertEqual(subprocess.run([node, '--check', str(ROOT / 'src/os/amerika/bridge/bridge.js')], capture_output=True).returncode, 0)

    def test_session_start_kicks_the_home_app_after_shell_ready(self):
        sh = (ROOT / 'src/os/session/session-start').read_text()
        self.assertIn('home-start', sh)
        self.assertIn('shell-ready', sh)
        self.assertEqual(subprocess.run(['sh', '-n', str(ROOT / 'src/os/session/session-start')], capture_output=True).returncode, 0)

    def test_chosen_classes_cover_the_electron_apps(self):
        self.assertIn('com.anthropic.claude', home.classes({}, 'claude'))
        self.assertIn('chatgpt', home.classes({}, 'chatgpt'))


if __name__ == '__main__':
    unittest.main()
