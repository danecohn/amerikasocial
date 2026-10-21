"""Unit tests for the Amerika Agent UI layer: CLI wrapper + secret handling (fake CLI), status/state machines, bar chip,
launcher triggers, loopback policy, the agent tools and their permissions, the dock migration and the shell service.
GTK widget behaviour is exercised by the rig scripts in tests/rig/agent_*.sh.
Run: PYTHONPATH=src/os python3 -m unittest discover -s tests"""
import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src/os'))

from amerika import common, firstrun  # noqa: E402
from amerika.agent import activity, cli, model  # noqa: E402
from amerika.ai import tools as tools_mod  # noqa: E402
from amerika.ai.broker import CLIENT_NAMES, Broker  # noqa: E402
from amerika.ai.tools import Tools  # noqa: E402

FAKE = ROOT / 'tests/fixtures/amerika-agent'
FAKE_KEY = 'sk-test-FAKE-0123456789abcdef'


def fake_shell(mode='safe', clients=None, **extra):
    settings = json.loads(json.dumps(common.DEFAULTS))
    settings['ai']['mode'] = mode
    settings['ai']['clients'] = clients or {}
    return SimpleNamespace(settings=settings, windows=SimpleNamespace(app_windows=lambda: [], state={}, command=lambda *a, **k: None),
                           notifications=SimpleNamespace(history=[], notify=lambda *a, **k: 1, dnd=False, set_dnd=lambda v: None), **extra)


class FakeCliCase(unittest.TestCase):
    """Each test gets its own runtime dir, state file and call log; the CLI under test is the fake."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {'AMERIKA_AGENT_BIN': str(FAKE), 'XDG_RUNTIME_DIR': str(self.tmp / 'run'), 'FAKE_AGENT_STATE': str(self.tmp / 'state.json'),
                    'FAKE_AGENT_LOG': str(self.tmp / 'calls.log'), 'FAKE_AGENT_DELAY': '0'}
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def calls(self):
        try:
            return [json.loads(line) for line in (self.tmp / 'calls.log').read_text().splitlines()]
        except OSError:
            return []


class CliAndSecrets(FakeCliCase):
    def test_status_roundtrip(self):
        st = cli.status()
        self.assertTrue(st.installed)
        self.assertEqual((st.engine, st.engine_version), ('openclaw', '2026.10.5'))
        self.assertFalse(st.running)
        self.assertFalse(st.has_key)
        self.assertEqual(st.listen_text(), '127.0.0.1:18789')

    def test_not_installed_is_a_clean_state(self):
        with mock.patch.dict(os.environ, {'AMERIKA_AGENT_BIN': str(self.tmp / 'nope')}):
            self.assertFalse(cli.available())
            self.assertFalse(cli.status().installed)
            ok, msg = cli.set_key('anthropic', FAKE_KEY)
            self.assertFalse(ok)
            self.assertIn('not installed', msg)
            self.assertEqual(cli.models('openai'), [])
            self.assertIsNone(cli.dashboard_url())
            self.assertEqual(model.page_view(cli.status())['mode'], 'not-installed')

    def test_key_goes_to_stdin_only(self):
        ok, msg = cli.set_key('anthropic', '  ' + FAKE_KEY + '  \n')
        self.assertTrue(ok, msg)
        rec = self.calls()[0]
        self.assertEqual(rec['argv'], ['key', 'set', 'anthropic'])
        self.assertEqual(rec['stdin_sha256'], hashlib.sha256(FAKE_KEY.encode()).hexdigest())
        self.assertFalse(rec['key_in_env'])
        self.assertNotIn(FAKE_KEY, json.dumps(rec['argv']))
        self.assertTrue(cli.status().providers['anthropic'])
        self.assertFalse(cli.status().providers['openai'])

    def test_key_is_never_printed_logged_or_stored(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertNoLogs(level='DEBUG'):
            cli.set_key('openai', FAKE_KEY)
            cli.status()
        self.assertNotIn(FAKE_KEY, out.getvalue() + err.getvalue())
        for path in self.tmp.rglob('*'):  # nothing the fake CLI or the wrapper wrote contains the key
            if path.is_file():
                self.assertNotIn(FAKE_KEY.encode(), path.read_bytes(), path)

    def test_error_text_that_echoes_the_key_is_scrubbed(self):
        with mock.patch.dict(os.environ, {'FAKE_AGENT_FAIL': 'key'}):
            ok, msg = cli.set_key('anthropic', FAKE_KEY)
        self.assertFalse(ok)
        self.assertNotIn(FAKE_KEY, msg)
        self.assertIn('***', msg)

    def test_empty_and_unknown_inputs(self):
        self.assertFalse(cli.set_key('anthropic', '   ')[0])
        self.assertFalse(cli.set_key('gemini', FAKE_KEY)[0])
        self.assertEqual(self.calls(), [])
        self.assertFalse(cli.clear_key('gemini')[0])
        self.assertFalse(cli.config_set('mode', 'yolo')[0])
        self.assertFalse(cli.config_set('apikey', 'x')[0])
        self.assertFalse(cli.control('format-disk')[0])
        self.assertFalse(cli.channel_set('../etc', True)[0])

    def test_clear_key(self):
        cli.set_key('anthropic', FAKE_KEY)
        self.assertTrue(cli.clear_key('anthropic')[0])
        self.assertFalse(cli.status().has_key)

    def test_controls_and_config(self):
        self.assertTrue(cli.control('start')[0])
        self.assertTrue(cli.status().running)
        self.assertTrue(cli.control('restart')[0])
        self.assertTrue(cli.control('enable')[0])
        self.assertTrue(cli.status().autostart)
        self.assertTrue(cli.config_set('mode', 'trusted')[0])
        self.assertTrue(cli.config_set('model', 'claude-sonnet-4-fake')[0])
        self.assertTrue(cli.config_set('autostart', False)[0])
        st = cli.status()
        self.assertEqual((st.mode, st.model, st.autostart), ('trusted', 'claude-sonnet-4-fake', False))
        self.assertTrue(cli.control('stop')[0])
        self.assertFalse(cli.status().running)

    def test_models_dashboard_doctor_channels(self):
        self.assertEqual(cli.models('anthropic')[0], 'claude-opus-4-fake')
        self.assertEqual(len(cli.models('openai')), 2)
        self.assertTrue(cli.dashboard_url().startswith('http://127.0.0.1:'))
        self.assertIn('All checks finished', cli.doctor())
        self.assertEqual(cli.channels(), [('telegram', False), ('discord', False), ('slack', False)])
        self.assertTrue(cli.channel_set('discord', True)[0])
        st = cli.status()
        self.assertEqual(st.channels, ('discord',))
        self.assertIn(('discord', True), cli.channels(st.channels))

    def test_ask_streams_lines(self):
        cli.control('start')
        lines, done = [], threading.Event()
        result = {}
        cli.AskHandle('what time is it?', lines.append, lambda code, err: (result.update(code=code, err=err), done.set()))
        self.assertTrue(done.wait(10))
        self.assertEqual(result['code'], 0)
        self.assertIn('You asked: what time is it?', lines[0])
        self.assertEqual(lines[-1], 'Done.')

    def test_ask_failure_reports_error_text(self):
        done, result = threading.Event(), {}
        cli.AskHandle('hello', lambda line: None, lambda code, err: (result.update(code=code, err=err), done.set()))  # agent not started
        self.assertTrue(done.wait(10))
        self.assertNotEqual(result['code'], 0)
        self.assertIn('not running', result['err'])

    def test_ld_preload_does_not_reach_the_cli(self):
        with mock.patch.dict(os.environ, {'LD_PRELOAD': '/tmp/evil.so'}):
            self.assertNotIn('LD_PRELOAD', cli._env())


class Model(unittest.TestCase):
    def test_status_parsing_is_defensive(self):
        st = model.Status.from_json({'installed': True, 'gateway': 'nonsense', 'providers': None, 'mode': 'root', 'channels': ['a', 5]})
        self.assertTrue(st.installed)
        self.assertEqual((st.mode, st.channels, st.running, st.port), ('ask', ('a',), False, 0))
        with self.assertRaises(ValueError):
            model.Status.from_json([])
        self.assertFalse(model.Status.missing().installed)
        self.assertEqual(model.Status.broken('x').error, 'x')

    def test_page_view_state_machine(self):
        self.assertEqual(model.page_view(model.Status.missing())['mode'], 'not-installed')
        self.assertFalse(model.page_view(model.Status.missing())['keys'])
        stopped = model.page_view(model.Status(installed=True))
        self.assertEqual((stopped['mode'], stopped['gateway'], stopped['start'], stopped['stop']), ('stopped', 'STOPPED', True, False))
        self.assertTrue(stopped['onboarding'])  # no key yet: the guided card shows
        running = model.page_view(model.Status(installed=True, running=True, providers={'openai': True}))
        self.assertEqual((running['gateway'], running['start'], running['stop'], running['restart']), ('RUNNING', False, True, True))
        self.assertFalse(running['onboarding'])
        self.assertEqual(running['models'], {'anthropic': False, 'openai': True})
        busy = model.page_view(model.Status(installed=True, running=True, providers={'openai': True}), busy=True)
        self.assertFalse(busy['stop'] or busy['start'] or busy['restart'])
        broken = model.page_view(model.Status.broken('boom'))
        self.assertEqual((broken['mode'], broken['tone'], broken['onboarding']), ('broken', 'error', False))

    def test_key_text_never_reveals_anything(self):
        self.assertEqual(model.key_text(True), 'Key saved in your keyring')
        self.assertEqual(model.key_text(False), 'No key saved')

    def test_onboarding_steps(self):
        ob = model.Onboarding()
        self.assertEqual(ob.name, 'provider')
        with self.assertRaises(ValueError):
            ob.key_saved()
        with self.assertRaises(ValueError):
            ob.choose_provider('gemini')
        ob.choose_provider('openai')
        self.assertEqual(ob.name, 'key')
        with self.assertRaises(ValueError):
            ob.finish()
        ob.back()
        self.assertEqual(ob.name, 'provider')
        ob.choose_provider('anthropic')
        ob.key_saved()
        self.assertEqual(ob.name, 'mode')
        ob.finish()
        self.assertTrue(ob.done)

    def test_channels_parsing(self):
        self.assertEqual(model.parse_channels('telegram\tdisabled\ndiscord enabled\n', ('discord',)), [('telegram', False), ('discord', True)])
        self.assertEqual(model.parse_channels('["a","b"]', ('b',)), [('a', False), ('b', True)])
        self.assertEqual(model.parse_channels('{"x": true}', ()), [('x', False)])
        self.assertEqual(model.parse_channels('', ('slack',)), [('slack', True)])
        self.assertEqual(model.parse_channels('../bad\n', ()), [])

    def test_activity_parsing(self):
        now = 10_000.0
        self.assertEqual(model.parse_activity('{"state":"tool","text":"windows.list","since":9990}', now), ('tool', 'windows.list', 9990.0))
        self.assertEqual(model.parse_activity('garbage', now)[0], 'idle')
        self.assertEqual(model.parse_activity('[]', now)[0], 'idle')
        self.assertEqual(model.parse_activity('{"state":"dancing"}', now)[0], 'idle')
        self.assertEqual(model.parse_activity('{"state":"thinking","since":1}', now + model.STALE_AFTER + 5)[0], 'idle')  # dead engine
        self.assertEqual(len(model.parse_activity(json.dumps({'state': 'tool', 'text': 'x' * 500}), now)[1]), 80)

    def test_chip_view(self):
        self.assertFalse(model.chip_view('idle', '', installed=False)[2])
        self.assertEqual(model.chip_view('idle', '', False), ('AGENT · IDLE', 'idle', True))
        self.assertEqual(model.chip_view('thinking', '', False)[:2], ('AGENT · THINKING', 'thinking'))
        self.assertEqual(model.chip_view('tool', 'windows.list', False)[0], 'AGENT · WINDOWS.LIST')
        self.assertEqual(model.chip_view('error', '', False)[1], 'error')
        self.assertEqual(model.chip_view('tool', 'x', paused=True), ('AGENT · PAUSED', 'paused', True))
        self.assertLessEqual(len(model.chip_view('tool', 'y' * 80, False)[0]), 35)

    def test_long_task_detection(self):
        self.assertTrue(model.finished_long_task('thinking', 100.0, 'idle', now=130.0))
        self.assertTrue(model.finished_long_task('tool', 100.0, 'error', now=130.0))
        self.assertFalse(model.finished_long_task('thinking', 100.0, 'idle', now=105.0))
        self.assertFalse(model.finished_long_task('idle', 100.0, 'idle', now=500.0))
        self.assertFalse(model.finished_long_task('thinking', 100.0, 'tool', now=500.0))

    def test_launcher_triggers(self):
        cases = {'? what is a mutex': ('what is a mutex', True), '?how': ('how', True), 'ask what time is it': ('what time is it', True),
                 'Ask: summarise my day': ('summarise my day', True), 'ASK hello': ('hello', True),
                 'why is the sky blue?': ('why is the sky blue?', False), 'files': (None, False), 'asking': (None, False),
                 'task list': (None, False), '': (None, False), '   ': (None, False), 'firefox?': (None, False), '?': (None, True)}
        for text, expected in cases.items():
            self.assertEqual(model.parse_ask(text), expected, text)

    def test_loopback_policy(self):
        yes = ['http://127.0.0.1:18789/', 'http://localhost:3000/#token=x', 'https://[::1]/', 'ws://127.0.0.1:1/', 'http://127.5.5.5/', 'http://app.localhost/']
        no = ['https://example.com/', 'http://127.0.0.1.evil.com/', 'http://localhost.evil.com/', 'http://localhost@evil.com/', 'http://evil.com#127.0.0.1',
              'file:///etc/passwd', 'javascript:alert(1)', 'data:text/html,hi', 'about:blank', '', 'http://0.0.0.0/', 'http://192.168.1.2/',
              'http://127.0.0.1@evil.com/', 'ftp://127.0.0.1/', 'http:///']
        for url in yes:
            self.assertTrue(model.is_loopback_url(url), url)
        for url in no:
            self.assertFalse(model.is_loopback_url(url), url)

    def test_window_states_and_header(self):
        self.assertEqual(model.window_state(model.Status.missing()), 'not-installed')
        self.assertEqual(model.window_state(model.Status.broken('x')), 'broken')
        self.assertEqual(model.window_state(model.Status(installed=True)), 'stopped')
        self.assertEqual(model.window_state(model.Status(installed=True), starting=True), 'starting')
        self.assertEqual(model.window_state(model.Status(installed=True, running=True)), 'live')
        run = model.Status(installed=True, running=True)
        self.assertEqual(model.header_text(run, 'tool', 'files.list'), 'files.list')
        self.assertEqual(model.header_text(model.Status(installed=True), 'idle', ''), 'Stopped')
        self.assertEqual(model.header_text(run, 'idle', '', paused=True), 'Paused')

    def test_public_status_leaks_nothing(self):
        st = model.Status(installed=True, running=True, url='http://127.0.0.1:1/#token=SECRET', providers={'anthropic': True}, model='m')
        text = json.dumps(model.public_status(st))
        self.assertNotIn('SECRET', text)
        self.assertNotIn('127.0.0.1', text)
        self.assertEqual(json.loads(text)['providers_configured'], {'anthropic': True, 'openai': False})

    def test_scrub(self):
        self.assertEqual(model.scrub('bad sk-test-abcd here', ['sk-test-abcd']), 'bad *** here')
        self.assertEqual(model.scrub(None, ['abcd1234']), '')
        self.assertEqual(model.scrub('ab', ['ab']), 'ab')  # too short to be a key: do not mangle ordinary text


class ActivityFile(FakeCliCase):
    def test_watcher_reads_file_and_reports_changes_once(self):
        seen = []
        watcher = activity.ActivityWatcher(lambda *v: seen.append(v))
        watcher.read(force=True)
        self.assertEqual(seen[-1][0], 'idle')  # file absent
        watcher.path.parent.mkdir(parents=True, exist_ok=True)
        watcher.path.write_text(json.dumps({'state': 'tool', 'text': 'apps.list', 'since': time.time()}))
        watcher.read()
        watcher.read()
        self.assertEqual([s[0] for s in seen], ['idle', 'tool'])
        self.assertEqual(seen[-1][1], 'apps.list')
        watcher.path.write_text('{ torn write')
        watcher.read()
        self.assertEqual(seen[-1][0], 'idle')

    def test_activity_path_follows_xdg_runtime_dir(self):
        self.assertEqual(cli.activity_path(), self.tmp / 'run/amerika/agent-activity.json')


class ShellService(FakeCliCase):
    def make(self, paused=False):
        from amerika.shell.agent_service import AgentService
        notes = []
        shell = SimpleNamespace(notifications=SimpleNamespace(notify=lambda *a, **k: notes.append((a, k))),
                                broker=SimpleNamespace(paused=paused), windows=None)
        svc = AgentService(shell)
        svc.status = model.Status(installed=True, running=True, autostart=True)
        return svc, notes

    def test_long_task_notifies_once_short_task_does_not(self):
        svc, notes = self.make()
        now = time.time()
        svc._activity('thinking', '', now - 45)
        svc._activity('tool', 'files.read', now - 40)
        svc._activity('idle', '', 0)
        self.assertEqual(len(notes), 1)
        self.assertIn('finished', notes[0][0][3])
        self.assertTrue(notes[0][1]['ai'])
        svc._activity('thinking', '', time.time() - 2)
        svc._activity('idle', '', 0)
        self.assertEqual(len(notes), 1)

    def test_error_after_long_task_says_so_and_pause_silences(self):
        svc, notes = self.make()
        svc._activity('thinking', '', time.time() - 60)
        svc._activity('error', 'model refused', 0)
        self.assertIn('problem', notes[0][0][3])
        self.assertEqual(notes[0][0][4], 'model refused')
        svc2, notes2 = self.make(paused=True)
        svc2._activity('thinking', '', time.time() - 60)
        svc2._activity('idle', '', 0)
        self.assertEqual(notes2, [])

    def test_stop_switch_stops_the_agent_and_resume_restarts_it(self):
        svc, _ = self.make()
        def sync(work, done=None):
            result = work()
            if done:
                done(result)
        with mock.patch.object(cli, 'in_thread', sync):
            cli.control('enable')
            cli.control('start')
            self.assertTrue(cli.status().running)
            svc.on_paused(True)
            self.assertFalse(cli.status().running)
            self.assertEqual([c['argv'] for c in self.calls() if c['argv'][0] in ('start', 'stop')], [['start'], ['stop']])
            svc.on_paused(False)  # autostart is on: it comes back
            self.assertTrue(cli.status().running)

    def test_resume_does_not_start_an_agent_the_user_never_wanted(self):
        svc, _ = self.make()
        svc.status = model.Status(installed=True, running=False, autostart=False)
        with mock.patch.object(cli, 'in_thread', lambda work, done=None: (done(work()) if done else work())):
            svc.on_paused(True)
            svc.on_paused(False)
        self.assertNotIn(['start'], [c['argv'] for c in self.calls()])

    def test_chip_reflects_pause_and_install(self):
        svc, _ = self.make()
        svc.state, svc.text = 'tool', 'apps.launch'
        self.assertEqual(svc.chip(), ('AGENT · APPS.LAUNCH', 'tool', True))
        svc.shell.broker.paused = True
        self.assertEqual(svc.chip()[1], 'paused')
        svc.status = model.Status.missing()
        self.assertFalse(svc.chip()[2])


class AgentTools(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        patch = mock.patch.object(tools_mod, 'HOME', self.home)
        patch.start()
        self.addCleanup(patch.stop)
        self.tools = Tools(fake_shell())

    def test_new_tools_exist_with_the_right_risk(self):
        want = {'agent.status': 'read', 'screenshot.take': 'sensitive', 'shell.run': 'critical', 'power.suspend': 'critical',
                'power.poweroff': 'critical', 'power.reboot': 'critical', 'clipboard.get': 'sensitive', 'clipboard.set': 'act',
                'files.list': 'read', 'files.read': 'sensitive', 'files.write': 'sensitive', 'notifications.send': 'act',
                'apps.list': 'read', 'apps.launch': 'act', 'windows.list': 'read', 'windows.focus': 'act', 'windows.move_resize': 'act',
                'windows.close': 'sensitive', 'settings.get': 'read', 'settings.set': 'act', 'system.info': 'read'}
        for name, risk in want.items():
            self.assertEqual(self.tools.risk(name), risk, name)

    def test_every_tool_has_a_strict_schema_and_description(self):
        for name, tool in self.tools.table.items():
            schema = tool['schema']
            self.assertEqual(schema['type'], 'object', name)
            self.assertIs(schema['additionalProperties'], False, name)
            self.assertTrue(tool['description'].strip(), name)
            for req in schema['required']:
                self.assertIn(req, schema['properties'], name)
        names = {d['name'] for d in self.tools.describe()}
        self.assertIn('agent.status', names)

    def test_the_agent_cannot_spawn_or_message_agents(self):
        for name in self.tools.table:
            self.assertFalse(name.startswith('agent.') and name != 'agent.status', name)
        for forbidden in ('agent.ask', 'agent.start', 'agent.stop', 'agent.key', 'agent.send'):
            self.assertNotIn(forbidden, self.tools.table)

    def test_screenshot_schema(self):
        tool = self.tools.table['screenshot.take']
        self.tools.validate(tool, {})
        self.tools.validate(tool, {'target': 'window'})
        for bad in ({'target': 'rm -rf'}, {'target': 5}, {'x': 1}):
            with self.assertRaises(ValueError, msg=bad):
                self.tools.validate(tool, bad)
        from amerika.agent import screen
        with self.assertRaises(ValueError):
            screen.capture('everything')

    def test_agent_status_hides_secrets(self):
        st = model.Status(installed=True, running=True, url='http://127.0.0.1:1/#token=SECRET', providers={'anthropic': True}, model='m', mode='safe')
        tools = Tools(fake_shell(agent=SimpleNamespace(status=st, state='tool', text='files.list')))
        out = tools.call('agent.status', {})
        self.assertTrue(out['gateway_running'])
        self.assertEqual(out['activity'], {'state': 'tool', 'text': 'files.list'})
        self.assertNotIn('SECRET', json.dumps(out))
        with self.assertRaises(ValueError):
            tools.call('agent.status', {'x': 1})

    def test_agent_status_without_service_uses_the_cli(self):
        with mock.patch.dict(os.environ, {'AMERIKA_AGENT_BIN': str(self.home / 'missing')}):
            fut = Tools(fake_shell()).call('agent.status', {})
            self.assertFalse(fut.result(10)['installed'])

    def test_shell_run_is_critical_and_can_never_be_granted(self):
        for mode in ('ask', 'safe', 'trusted'):
            b = Broker(fake_shell(mode, {'amerika-agent': {'always': ['shell.run']}}))
            self.assertEqual(b.decision('amerika-agent', 'shell.run'), 'ask', mode)
        b = Broker(fake_shell('trusted'))
        b.grant_always('amerika-agent', 'shell.run')
        self.assertNotIn('shell.run', b.shell.settings['ai']['clients'].get('amerika-agent', {}).get('always', []))
        self.assertIn('critical', self.tools.table['shell.run']['description'].lower() + 'critical')

    def test_agent_client_follows_the_single_ai_mode(self):
        self.assertEqual(CLIENT_NAMES['amerika-agent'], 'Amerika Agent')
        self.assertEqual(Broker(fake_shell('ask')).decision('amerika-agent', 'audio.set_volume'), 'ask')
        self.assertEqual(Broker(fake_shell('safe')).decision('amerika-agent', 'audio.set_volume'), 'allow')
        self.assertEqual(Broker(fake_shell('safe')).decision('amerika-agent', 'screenshot.take'), 'ask')
        self.assertEqual(Broker(fake_shell('trusted')).decision('amerika-agent', 'screenshot.take'), 'allow')
        self.assertEqual(Broker(fake_shell('safe')).decision('amerika-agent', 'agent.status'), 'allow')
        b = Broker(fake_shell('trusted'))
        b.paused = True
        self.assertEqual(b.decision('amerika-agent', 'agent.status'), 'deny')

    def test_files_stay_in_home_and_protected_places_are_off_limits(self):
        (self.home / 'notes.txt').write_text('hello')
        self.assertEqual(self.tools.call('files.read', {'path': str(self.home / 'notes.txt')})['text'], 'hello')
        self.assertEqual(self.tools.call('files.write', {'path': str(self.home / 'docs/a.txt'), 'text': 'x'})['bytes'], 1)
        for secret in ('.ssh/id_ed25519', '.gnupg/key', '.local/share/keyrings/login.keyring', '.config/amerika-agent/token', '.aws/credentials'):
            p = self.home / secret
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('secret')
            with self.assertRaises(ValueError, msg=secret):
                self.tools.call('files.read', {'path': str(p)})
        for target in ('.bashrc', '.profile', '.config/autostart/evil.desktop', '.config/systemd/user/evil.service', '.config/amerika-os/settings.json',
                       '.local/state/amerika-os/ai-audit.log', '.ssh/authorized_keys', '.local/bin/ls', '.config/Claude/claude_desktop_config.json'):
            with self.assertRaises(ValueError, msg=target):
                self.tools.call('files.write', {'path': str(self.home / target), 'text': 'x'})
        self.assertFalse((self.home / '.bashrc').exists())

    def test_symlinks_cannot_smuggle_protected_or_outside_paths(self):
        (self.home / '.ssh').mkdir()
        (self.home / '.ssh/id').write_text('k')
        (self.home / 'link').symlink_to(self.home / '.ssh')
        with self.assertRaises(ValueError):
            self.tools.call('files.read', {'path': str(self.home / 'link/id')})
        outside = Path(tempfile.mkdtemp())
        (outside / 'f').write_text('x')
        (self.home / 'out').symlink_to(outside)
        with self.assertRaises(ValueError):
            self.tools.call('files.read', {'path': str(self.home / 'out/f')})

    def test_copilot_setting_accepts_agent(self):
        applied = []
        self.tools.shell.update_setting = lambda k, v: applied.append((k, v))
        self.tools.call('settings.set', {'key': 'copilot_app', 'value': 'agent'})
        self.assertEqual(applied, [('copilot_app', 'agent')])
        with self.assertRaises(ValueError):
            self.tools.call('settings.set', {'key': 'copilot_app', 'value': 'gemini'})


class DockAndDefaults(unittest.TestCase):
    def setUp(self):
        self.cfg = Path(tempfile.mkdtemp())
        patch = mock.patch.object(common, 'CONFIG', self.cfg)
        patch.start()
        self.addCleanup(patch.stop)

    def stored(self):
        return json.loads((self.cfg / 'settings.json').read_text())

    def test_new_users_get_the_agent_pinned_by_default(self):
        self.assertIn('amerika-agent', common.DEFAULTS['dock_pinned'])
        self.assertEqual(common.DEFAULTS['dock_pinned'][:3], ['com.anthropic.Claude', 'chatgpt', 'amerika-agent'])

    def test_migration_appends_once_next_to_the_ai_apps(self):
        (self.cfg / 'settings.json').write_text(json.dumps({'dock_pinned': ['com.anthropic.Claude', 'chatgpt', 'amerika-files'], 'accent': '#123456'}))
        self.assertTrue(firstrun.migrate_dock_agent())
        self.assertEqual(self.stored()['dock_pinned'], ['com.anthropic.Claude', 'chatgpt', 'amerika-agent', 'amerika-files'])
        self.assertEqual(self.stored()['accent'], '#123456')
        self.assertFalse(firstrun.migrate_dock_agent())
        self.assertEqual(self.stored()['dock_pinned'].count('amerika-agent'), 1)

    def test_user_who_removes_it_keeps_it_removed(self):
        (self.cfg / 'settings.json').write_text(json.dumps({'dock_pinned': ['amerika-files']}))
        firstrun.migrate_dock_agent()
        data = self.stored()
        data['dock_pinned'].remove('amerika-agent')
        (self.cfg / 'settings.json').write_text(json.dumps(data))
        firstrun.migrate_dock_agent()
        self.assertNotIn('amerika-agent', self.stored()['dock_pinned'])

    def test_new_user_without_a_pinned_list_is_only_marked(self):
        self.assertTrue(firstrun.migrate_dock_agent())
        self.assertNotIn('dock_pinned', self.stored())
        self.assertIn('amerika-agent', common.load_settings()['dock_pinned'])

    def test_malformed_settings_are_not_clobbered_into_garbage(self):
        (self.cfg / 'settings.json').write_text('[1, 2]')
        self.assertFalse(firstrun.migrate_dock_agent())
        (self.cfg / 'settings.json').write_text(json.dumps({'dock_pinned': 'not a list'}))
        firstrun.migrate_dock_agent()
        self.assertEqual(self.stored()['dock_pinned'], 'not a list')


class Packaging(unittest.TestCase):
    def test_window_launcher_and_desktop_entry(self):
        exe = ROOT / 'src/os/bin/amerika-agent-window'
        self.assertTrue(os.access(exe, os.X_OK))
        self.assertIn('amerika.agent.window', exe.read_text())
        entry = (ROOT / 'src/os/applications/amerika-agent.desktop').read_text()
        from amerika.agent import window
        self.assertIn('Exec=amerika-agent-window', entry)
        self.assertIn(f'StartupWMClass={window.APP_ID}', entry)

    def test_window_profile_dir_is_private(self):
        tmp = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {'XDG_DATA_HOME': tmp + '/d', 'XDG_CACHE_HOME': tmp + '/c'}):
            from amerika.agent import window
            data, cache = window.profile_dirs()
        for d in (data, cache):
            self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        self.assertIn('amerika-os', str(data))

    def test_css_block_is_present_and_formats(self):
        from amerika import theme
        self.assertIn('/* ---------- agent ---------- */', theme.CSS)
        css = theme.CSS % {'accent': '#ff2e63', 'secondary': '#19e3ff'}
        for cls in ('.am-agent-chip', '.am-risk.critical', '.am-pill.on', '.am-answer', '.am-agent-frame'):
            self.assertIn(cls, css)

    def test_secret_hygiene_in_ui_sources(self):
        for rel in ('agent/cli.py', 'agent/model.py', 'agent/window.py', 'settings/page_agent.py', 'shell/agent_ask.py', 'shell/agent_service.py'):
            src = (ROOT / 'src/os/amerika' / rel).read_text()
            self.assertNotIn('print(key', src, rel)
            self.assertNotIn('logging', src, rel)
            self.assertIsNone(re.search(r'self\._key\b', src), rel)
        page = (ROOT / 'src/os/amerika/settings/page_agent.py').read_text()
        self.assertGreaterEqual(page.count("set_text('')  # cleared immediately"), 2)
        self.assertNotIn("'--key'", page)


if __name__ == '__main__':
    unittest.main()


class GatewayOrigin(unittest.TestCase):
    def test_only_the_configured_gateway_origin_is_embedded(self):
        self.assertTrue(model.is_gateway_url('http://127.0.0.1:18790/#bootstrapToken=FAKE',18790))
        for url in ('http://127.0.0.1:18791/', 'http://localhost:18790/', 'http://user@127.0.0.1:18790/',
                    'https://127.0.0.1:18790/', 'http://127.0.0.1:bad/', 'http://127.0.0.1:18790.evil/'):
            self.assertFalse(model.is_gateway_url(url,18790),url)

    def test_model_picker_parses_backend_json(self):
        data={'anthropic':[{'id':'anthropic/example','description':'A human label'}]}
        with mock.patch.object(cli,'run',return_value=cli.Result(0,json.dumps(data),'')):
            self.assertEqual(cli.models('anthropic'),['anthropic/example'])


class StopExecution(unittest.TestCase):
    def test_pause_after_approval_prevents_execution(self):
        from concurrent.futures import Future
        shell=fake_shell(mode='ask', cancel_approvals=lambda:None)
        broker=Broker(shell)
        approved=Future();approved.set_result('allow')
        shell.ask_approval=lambda *args:approved
        def on_main(fn,*args):
            result=Future()
            try:
                if fn.__name__=='execute':broker.paused=True
                result.set_result(fn(*args))
            except Exception as error:result.set_exception(error)
            return result
        with mock.patch.object(broker,'on_main',side_effect=on_main), mock.patch.object(broker.tools,'call') as call, \
             mock.patch.object(common,'audit'):
            ok,message=broker.handle('amerika-agent','audio.set_volume',{'percent':30})
        self.assertFalse(ok);self.assertIn('paused',message);call.assert_not_called()

    def test_stop_interrupts_a_running_command_without_blocking_ui(self):
        tools=Tools(fake_shell())
        start=time.monotonic()
        with tempfile.TemporaryDirectory() as home, mock.patch.object(tools_mod,'HOME',Path(home)):
            answer=tools.shell_run({'command':'sleep 20'})
            self.assertLess(time.monotonic()-start,1)
            tools.cancel_commands()
            with self.assertRaisesRegex(ValueError,'stopped'):answer.result(timeout=3)
        self.assertFalse(tools._commands)
