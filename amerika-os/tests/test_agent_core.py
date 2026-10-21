"""Agent configuration, keyring protocol and activity. No real keyring/model calls."""
import contextlib
import copy
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/os/agent'))
from amerika_agent import activity, cli, common, config, keyring, secret

FAKE = 'sk-test-FAKE-agent-core'


class Core(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        variables = {name: str(self.base / name) for name in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_DATA_HOME', 'XDG_RUNTIME_DIR')}
        patch = mock.patch.dict(os.environ, variables)
        patch.start(); self.addCleanup(patch.stop)
        self.paths = common.Paths()

    def test_default_is_opt_in_and_loopback(self):
        c = config.build_config(config.DEFAULT_SETTINGS, paths=self.paths)
        self.assertEqual(c['gateway']['bind'], 'loopback')
        self.assertEqual(c['gateway']['auth']['mode'], 'token')
        self.assertEqual(c['gateway']['auth']['token'], config.secret_ref('gateway-token'))
        self.assertNotIn('channels', c)
        self.assertFalse(c['plugins']['entries']['linux-node']['enabled'])
        self.assertFalse(c['plugins']['entries']['mcp-relay']['enabled'])
        self.assertFalse(config.DEFAULT_SETTINGS['autostart'])
        self.assertFalse(c['update']['auto']['enabled'])

    def test_every_mode_routes_mutations_through_broker(self):
        for mode in common.MODES:
            settings = dict(config.DEFAULT_SETTINGS, mode=mode)
            c = config.build_config(settings, paths=self.paths)
            self.assertIn('amerika__*', c['tools']['allow'])
            for group in ('group:runtime', 'group:fs', 'group:ui', 'group:nodes', 'group:automation'):
                self.assertIn(group, c['tools']['deny'])
            self.assertFalse(c['tools']['elevated']['enabled'])

    def test_credentials_are_references_only(self):
        c = config.build_config(config.DEFAULT_SETTINGS, {'openai': True, 'anthropic': True}, paths=self.paths)
        for provider in common.PROVIDERS:
            self.assertEqual(c['models']['providers'][provider]['apiKey'], config.secret_ref(provider))
        self.assertNotIn(FAKE, config.render(c))

    def test_invalid_settings_fail_closed(self):
        for change in ({'mode':'full'}, {'port':True}, {'port':80}, {'autostart':'true'}, {'model':'evil/x'},
                       {'channels':{'evil':True}}, {'channels':{'discord':'yes'}}, {'linux_node':1}):
            with self.subTest(change=change), self.assertRaises(common.AgentError):
                config.validate_settings(change)

    def test_config_and_workspace_are_private_and_separate(self):
        with mock.patch.object(common, 'SHARE', ROOT/'src/os/agent'):
            config.write_config(self.paths, providers={})
        self.assertEqual(stat.S_IMODE(self.paths.openclaw_config.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.paths.config_dir.stat().st_mode), 0o700)
        self.assertTrue((self.paths.workspace/'AGENTS.md').is_file())
        env = self.paths.engine_env()
        self.assertIn('amerika-agent', env['OPENCLAW_STATE_DIR'])
        self.assertNotIn('.openclaw', env['OPENCLAW_STATE_DIR'])
        self.assertNotIn(FAKE, self.paths.openclaw_config.read_text())

    def test_workspace_notes_survive_updates(self):
        with mock.patch.object(common, 'SHARE', ROOT/'src/os/agent'):
            config.seed_workspace(self.paths)
            p=self.paths.workspace/'AGENTS.md';p.write_text(p.read_text()+'\nMy notes stay.\n')
            config.seed_workspace(self.paths)
        self.assertIn('My notes stay.',p.read_text())
        self.assertEqual(p.read_text().count(config.BLOCK_BEGIN),1)

    def test_key_store_passes_value_only_on_stdin(self):
        with mock.patch.object(keyring.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')) as run:
            keyring.store('openai',FAKE)
        argv=run.call_args.args[0]
        self.assertNotIn(FAKE,repr(argv))
        self.assertEqual(run.call_args.kwargs['input'],FAKE)

    def test_keyring_errors_never_echo_child_output(self):
        with mock.patch.object(keyring,'_tool',return_value=SimpleNamespace(returncode=2,stdout='',stderr=FAKE)):
            for fn in (lambda:keyring.store('openai',FAKE),lambda:keyring.lookup('openai')):
                with self.assertRaises(common.AgentError) as err:fn()
                self.assertNotIn(FAKE,str(err.exception))

    def test_locked_keyring_does_not_replace_gateway_token(self):
        with mock.patch.object(keyring,'lookup',side_effect=common.AgentError('locked')),mock.patch.object(keyring,'store') as store:
            with self.assertRaises(common.AgentError):keyring.ensure_gateway_token()
            store.assert_not_called()

    def test_secret_helper_protocol(self):
        response=io.StringIO()
        with mock.patch.object(keyring,'lookup',return_value=FAKE):
            self.assertEqual(secret.resolve(io.StringIO('{"protocolVersion":1,"ids":["openai"]}'),response),0)
        self.assertEqual(json.loads(response.getvalue())['values']['openai'],FAKE)

    def test_secret_protocol_rejects_unbounded_or_invalid_ids(self):
        for request in ([], {}, {'protocolVersion':True,'ids':['openai']},
                        {'protocolVersion':1,'ids':['unexpected']}, {'protocolVersion':1,'ids':[[FAKE]]},
                        {'protocolVersion':1,'ids':['openai']*100}):
            with self.subTest(request=request), mock.patch.object(keyring,'lookup') as lookup:
                reply=io.StringIO()
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(secret.resolve(io.StringIO(json.dumps(request)),reply),2)
                self.assertEqual(reply.getvalue(),'');lookup.assert_not_called()

    def test_secret_helper_refuses_terminal_even_force(self):
        terminal=io.StringIO();terminal.isatty=lambda:True
        with contextlib.redirect_stderr(io.StringIO()),mock.patch.object(keyring,'lookup') as lookup:
            self.assertNotEqual(secret.get('openai',force=True,stdout=terminal),0)
        self.assertEqual(terminal.getvalue(),'');lookup.assert_not_called()

    def test_engine_env_drops_inherited_provider_keys(self):
        with mock.patch.dict(os.environ,{'OPENAI_API_KEY':FAKE,'ANTHROPIC_API_KEY':FAKE,'OPENCLAW_GATEWAY_TOKEN':FAKE}):
            env=cli.engine_env(self.paths)
        self.assertFalse(any(v==FAKE for v in env.values()))

    def test_mcp_wrapper_uses_exact_broker_client(self):
        wrapper=(ROOT/'src/os/agent/amerika-mcp-wrapper').read_text()
        self.assertIn('--client amerika-agent',wrapper)
        self.assertNotIn('AMERIKA_MCP_CLIENT',wrapper)

    def test_dashboard_default_has_no_credentials(self):
        with mock.patch.object(cli,'require_engine'),mock.patch.object(cli,'port_open',return_value=True),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.cmd_dashboard_url(SimpleNamespace(bootstrap=False),self.paths),0)
        self.assertEqual(output.getvalue().strip(),f'http://127.0.0.1:{common.DEFAULT_PORT}/')

    def test_dashboard_never_falls_back_to_shared_token(self):
        with mock.patch.object(cli,'require_engine'),mock.patch.object(cli,'port_open',return_value=True),\
             mock.patch.object(common,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='')),\
             mock.patch.object(keyring,'lookup') as lookup,contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(common.AgentError):cli.cmd_dashboard_url(SimpleNamespace(bootstrap=True),self.paths)
        self.assertEqual(output.getvalue(),'');lookup.assert_not_called()

    def test_activity_records_no_untrusted_text(self):
        a=activity.Activity(self.paths)
        self.assertFalse(a.update({'phase':'run-start','text':FAKE}))
        self.assertTrue(a.update({'phase':'run-start','key':'a'}))
        self.assertEqual(a.state,'thinking')
        a.update({'phase':'tool-start','key':'a'});self.assertEqual(a.state,'tool')
        a.update({'phase':'tool-end','key':'a'});self.assertEqual(a.state,'thinking')
        a.update({'phase':'error','key':'a'});self.assertEqual(a.state,'error')
        self.assertNotIn(FAKE,self.paths.activity_file.read_text())
        self.assertEqual(stat.S_IMODE(self.paths.activity_file.stat().st_mode),0o600)

    def test_concurrent_activity_stays_busy_until_all_runs_finish(self):
        a=activity.Activity(self.paths)
        for key in ('a','b'):a.update({'phase':'run-start','key':key})
        a.update({'phase':'run-end','key':'a'});self.assertEqual(a.state,'thinking')
        a.update({'phase':'run-end','key':'b'});self.assertEqual(a.state,'idle')

    def test_systemd_services_are_not_auto_enabled(self):
        builder=(ROOT/'tools/builders/agent.py').read_text()
        self.assertNotIn('enable --now',builder)
        unit=(ROOT/'src/os/agent/systemd/amerika-agent-gateway.service').read_text()
        self.assertIn('KillMode=control-group',unit)
        self.assertIn('NoNewPrivileges=yes',unit)


class SharedMode(unittest.TestCase):
    setUp = Core.setUp
    def test_cli_mode_updates_broker_without_replacing_other_settings(self):
        target=self.paths.config_dir.parent/'amerika-os/settings.json'
        common.atomic_write(target,json.dumps({'accent':'#123456','ai':{'audit':True,'mode':'safe'}}))
        config.save_settings(self.paths,dict(config.DEFAULT_SETTINGS,mode='ask'))
        saved=json.loads(target.read_text())
        self.assertEqual(saved['ai']['mode'],'ask');self.assertTrue(saved['ai']['audit'])
        self.assertEqual(saved['accent'],'#123456')
