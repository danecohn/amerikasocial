"""Unit tests for the AI layer: permissions, tool validation, the MCP server, connection helpers and window-command safety.
Run: PYTHONPATH=src/os python3 -m unittest discover tests"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src/os'))

from amerika import common  # noqa: E402
from amerika.ai import connect, mcp  # noqa: E402
from amerika.ai.broker import Broker  # noqa: E402
from amerika.ai.tools import Tools  # noqa: E402


def fake_shell(mode='safe', clients=None):
    settings = json.loads(json.dumps(common.DEFAULTS))
    settings['ai']['mode'] = mode
    settings['ai']['clients'] = clients or {}
    return SimpleNamespace(settings=settings, windows=SimpleNamespace(app_windows=lambda: [], state={}, command=lambda *a, **k: None),
                           notifications=SimpleNamespace(history=[], notify=lambda *a, **k: 1, dnd=False, set_dnd=lambda v: None))


class Permissions(unittest.TestCase):
    def broker(self, mode='safe', clients=None):
        return Broker(fake_shell(mode, clients))

    def test_read_tools_never_ask(self):
        for mode in ('ask', 'safe', 'trusted'):
            self.assertEqual(self.broker(mode).decision('claude', 'system.status'), 'allow')

    def test_act_tools_by_mode(self):
        self.assertEqual(self.broker('ask').decision('claude', 'audio.set_volume'), 'ask')
        self.assertEqual(self.broker('safe').decision('claude', 'audio.set_volume'), 'allow')
        self.assertEqual(self.broker('trusted').decision('claude', 'audio.set_volume'), 'allow')

    def test_sensitive_tools_ask_unless_trusted(self):
        self.assertEqual(self.broker('safe').decision('claude', 'shell.run'), 'ask')
        self.assertEqual(self.broker('ask').decision('claude', 'files.write'), 'ask')
        self.assertEqual(self.broker('trusted').decision('claude', 'shell.run'), 'allow')

    def test_critical_tools_always_ask_even_when_trusted_or_granted(self):
        b = self.broker('trusted', {'claude': {'always': ['power.poweroff']}})
        for tool in ('power.poweroff', 'power.reboot', 'files.delete'):
            self.assertEqual(b.decision('claude', tool), 'ask')

    def test_always_grant_is_per_client_and_not_in_ask_mode(self):
        b = self.broker('safe', {'claude': {'always': ['shell.run']}})
        self.assertEqual(b.decision('claude', 'shell.run'), 'allow')
        self.assertEqual(b.decision('chatgpt', 'shell.run'), 'ask')
        b2 = self.broker('ask', {'claude': {'always': ['audio.set_volume']}})
        self.assertEqual(b2.decision('claude', 'audio.set_volume'), 'ask')

    def test_pause_and_disable_deny_everything(self):
        b = self.broker('trusted')
        b.paused = True
        self.assertEqual(b.decision('claude', 'system.status'), 'deny')
        b.paused = False
        b.shell.settings['ai']['clients'] = {'chatgpt': {'enabled': False}}
        self.assertEqual(b.decision('chatgpt', 'system.status'), 'deny')
        self.assertEqual(b.decision('claude', 'system.status'), 'allow')

    def test_per_client_mode_override(self):
        b = self.broker('safe', {'chatgpt': {'mode': 'ask'}})
        self.assertEqual(b.decision('chatgpt', 'audio.set_volume'), 'ask')
        self.assertEqual(b.decision('claude', 'audio.set_volume'), 'allow')

    def test_every_tool_has_a_known_risk_class(self):
        tools = Tools(fake_shell())
        for name, tool in tools.table.items():
            self.assertIn(tool['risk'], ('read', 'act', 'sensitive', 'critical'), name)
        self.assertEqual(tools.risk('shell.run'), 'sensitive')
        self.assertEqual(tools.risk('power.poweroff'), 'critical')
        self.assertEqual(tools.risk('windows.close'), 'sensitive')


class Validation(unittest.TestCase):
    def setUp(self):
        self.tools = Tools(fake_shell())

    def test_rejects_bad_arguments(self):
        for name, args in (('audio.set_volume', {}), ('audio.set_volume', {'percent': '50'}), ('audio.set_volume', {'percent': True}),
                           ('audio.set_volume', {'percent': 50, 'extra': 1}), ('windows.tile', {'id': 'x', 'side': 'diagonal'}),
                           ('files.read', {'path': 5}), ('shell.run', 'ls')):
            with self.assertRaises(ValueError, msg=(name, args)):
                self.tools.validate(self.tools.table[name], args)

    def test_accepts_good_arguments(self):
        self.tools.validate(self.tools.table['audio.set_volume'], {'percent': 40})
        self.tools.validate(self.tools.table['windows.tile'], {'id': 'abc', 'side': 'left'})

    def test_files_are_confined_to_home(self):
        for bad in ('/etc/passwd', '/', '~/../../etc/passwd'):
            with self.assertRaises(ValueError, msg=bad):
                self.tools.call('files.read', {'path': bad})

    def test_settings_values_are_checked(self):
        for key, value in (('copilot_app', 'gemini'), ('accent', 'red'), ('accent', '#12'), ('wallpaper', '../../x'), ('dock_size', 5), ('dock_size', '60'), ('clock_24h', 'yes')):
            with self.assertRaises(ValueError, msg=(key, value)):
                self.tools.table['settings.set']['handler']({'key': key, 'value': value})


class CopilotKey(unittest.TestCase):
    def test_copilot_setting_accepts_known_choices(self):
        tools = Tools(fake_shell())
        applied = []
        tools.shell.update_setting = lambda k, v: applied.append((k, v))
        for choice in ('claude', 'chatgpt', 'ask'):
            tools.table['settings.set']['handler']({'key': 'copilot_app', 'value': choice})
        self.assertEqual(applied, [('copilot_app', 'claude'), ('copilot_app', 'chatgpt'), ('copilot_app', 'ask')])

    def test_launched_apps_never_inherit_ld_preload(self):
        import gi
        gi.require_version('Gio', '2.0')
        from amerika.shell import apps
        ctx = apps.launch_context()
        os.environ['LD_PRELOAD'] = '/tmp/evil.so'
        try:
            env = ctx.get_environment()
            self.assertFalse(any(e.startswith('LD_PRELOAD=') for e in env), env)
        finally:
            os.environ.pop('LD_PRELOAD')


class Mcp(unittest.TestCase):
    def run_server(self, lines, broker):
        out = io.StringIO()
        mcp.serve('claude', io.StringIO('\n'.join(json.dumps(m) if isinstance(m, dict) else m for m in lines) + '\n'), out, broker)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_protocol_flow(self):
        calls = []

        def broker(req):
            calls.append(req)
            if req['method'] == 'list':
                return {'ok': True, 'result': [{'name': 'system.info', 'description': 'x', 'inputSchema': {'type': 'object'}}]}
            if req['tool'] == 'system.info':
                return {'ok': True, 'result': {'machine': 'aarch64'}}
            return {'ok': False, 'error': 'The user declined this action.'}
        out = self.run_server([
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'system.info', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'shell.run', 'arguments': {'command': 'ls'}}},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'resources/list'},
            'not json'], broker)
        self.assertEqual(out[0]['result']['protocolVersion'], '2025-03-26')
        self.assertEqual(out[0]['result']['serverInfo']['name'], 'amerika-system')
        self.assertEqual(out[1]['result']['tools'][0]['name'], 'system.info')
        self.assertFalse(out[2]['result'].get('isError'))
        self.assertEqual(json.loads(out[2]['result']['content'][0]['text'])['machine'], 'aarch64')
        self.assertTrue(out[3]['result']['isError'])
        self.assertEqual(out[4]['error']['code'], -32601)
        self.assertEqual(out[5]['error']['code'], -32700)
        self.assertTrue(all(c['client'] == 'claude' for c in calls))

    def test_shell_not_running_gives_a_clear_error(self):
        def broker(req):
            raise FileNotFoundError('no socket')
        out = self.run_server([{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'system.info'}}], broker)
        self.assertTrue(out[0]['result']['isError'])
        self.assertIn('not running', out[0]['result']['content'][0]['text'])


class Connect(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ['AMERIKA_CLAUDE_CONFIG'] = str(self.tmp / 'claude.json')
        os.environ['AMERIKA_CODEX_CONFIG'] = str(self.tmp / 'config.toml')

    def test_claude_connect_preserves_everything_and_backs_up(self):
        path = self.tmp / 'claude.json'
        path.write_text(json.dumps({'preferences': {'a': 1}, 'mcpServers': {'other': {'command': 'x'}}}))
        connect.connect_claude()
        data = json.loads(path.read_text())
        self.assertEqual(data['preferences'], {'a': 1})
        self.assertIn('other', data['mcpServers'])
        self.assertEqual(data['mcpServers']['amerika']['args'], ['--client', 'claude'])
        self.assertTrue((self.tmp / 'claude.json.amerika-backup').exists())
        self.assertTrue(connect.status()['claude'])
        connect.disconnect_claude()
        data = json.loads(path.read_text())
        self.assertNotIn('amerika', data['mcpServers'])
        self.assertIn('other', data['mcpServers'])
        self.assertEqual(data['preferences'], {'a': 1})

    def test_claude_never_overwrites_unreadable_config(self):
        (self.tmp / 'claude.json').write_text('{ not json')
        with self.assertRaises(ValueError):
            connect.connect_claude()
        self.assertEqual((self.tmp / 'claude.json').read_text(), '{ not json')

    def test_codex_block_is_added_and_removed_exactly(self):
        path = self.tmp / 'config.toml'
        original = '[desktop]\nfollowUpQueueMode = "steer"\n\n[plugins."x"]\nenabled = true\n'
        path.write_text(original)
        connect.connect_chatgpt()
        connect.connect_chatgpt()  # idempotent
        text = path.read_text()
        self.assertEqual(text.count('[mcp_servers.amerika]'), 1)
        self.assertIn('--client", "chatgpt"', text)
        self.assertTrue(connect.status()['chatgpt'])
        connect.disconnect_chatgpt()
        self.assertEqual(path.read_text().strip(), original.strip())
        self.assertFalse(connect.status()['chatgpt'])

    def test_codex_refuses_to_duplicate_a_hand_written_entry(self):
        (self.tmp / 'config.toml').write_text('[mcp_servers.amerika]\ncommand = "x"\n')
        with self.assertRaises(ValueError):
            connect.connect_chatgpt()


class WindowCommands(unittest.TestCase):
    def test_window_ids_cannot_inject_script(self):
        from amerika.windows import WindowBridge
        for bad in ('"); evil(); ("', "1; process.exit()", '', 'a' * 100, "{x}\n"):
            with self.assertRaises(ValueError, msg=bad):
                WindowBridge._find(bad)
        self.assertIn('"{1a2b3c4d-1111-2222-3333-444455556666}"', WindowBridge._find('{1a2b3c4d-1111-2222-3333-444455556666}'))


class Audit(unittest.TestCase):
    def test_audit_roundtrip(self):
        tmp = tempfile.mkdtemp()
        os.environ['XDG_STATE_HOME'] = tmp
        import importlib
        importlib.reload(common)
        common.audit('call', client='claude', tool='system.info', ok=True)
        common.audit('denied', client='chatgpt', tool='shell.run')
        events = common.read_audit()
        self.assertEqual([e['event'] for e in events], ['call', 'denied'])
        os.environ.pop('XDG_STATE_HOME')


if __name__ == '__main__':
    unittest.main()
