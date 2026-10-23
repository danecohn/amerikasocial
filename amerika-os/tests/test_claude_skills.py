"""Tests for the Claude skills and plugin: format, tool-name accuracy, installer round trips (temp HOME only), export layout, new MCP tools."""
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src/os'))
sys.path.insert(0, str(ROOT / 'src/os/claude'))

from amerika import common  # noqa: E402
from amerika.ai import connect  # noqa: E402
from amerika.ai import tools as tools_mod  # noqa: E402
from amerika.ai.broker import Broker  # noqa: E402
from amerika.ai.tools import Tools  # noqa: E402
from amerika_claude import core  # noqa: E402

CLAUDE = ROOT / 'src/os/claude'
PLUGIN = CLAUDE / 'plugin/amerika-os'
REAL_HOME = Path(os.path.expanduser('~'))


def fake_shell(actions=('launcher',)):
    settings = json.loads(json.dumps(common.DEFAULTS))
    updated = []

    class Shell:
        def __init__(self):
            self.settings = settings
            self.windows = SimpleNamespace(app_windows=lambda: [], state={}, command=mock.Mock(), windows_for=lambda i: [{'id': '7'}] if i == 'files' else [])
            self.notifications = SimpleNamespace(history=[], notify=lambda *a, **k: 1, dnd=False, set_dnd=lambda v: None)
            self.called = []

        def action(self, name):
            if name in actions:
                self.called.append(name)
            return False

        def update_setting(self, key, value):
            updated.append((key, value))
            self.settings[key] = value
    shell = Shell()
    shell.updated = updated
    return shell


def tool_names():
    return set(Tools(fake_shell()).table)


def studio_names():
    data = json.loads((ROOT / 'src/os/studio/tools.json').read_text())
    names = {'studio_status', 'studio_launch'}
    for app, spec in data['apps'].items():
        for t in spec['tools']:
            names.add(f'{app}_{t["name"].replace(".", "_")}')
    return names


def skill_dirs():
    return sorted(d for d in (PLUGIN / 'skills').iterdir() if d.is_dir())


class PluginFiles(unittest.TestCase):
    def test_plugin_json_and_mcp_json(self):
        meta = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(meta['name'], 'amerika-os')
        self.assertTrue(re.fullmatch(r'\d+\.\d+\.\d+', meta['version']))
        self.assertTrue(meta['description'])
        mcp = json.loads((PLUGIN / '.mcp.json').read_text())
        self.assertEqual(mcp['mcpServers']['amerika']['command'], '/usr/bin/amerika-mcp')
        self.assertIn('amerika-studio', mcp['mcpServers'])
        self.assertEqual(mcp['mcpServers']['amerika']['args'], ['--client', 'claude'])

    def test_all_json_files_parse(self):
        for f in PLUGIN.rglob('*.json'):
            json.loads(f.read_text())

    def test_eleven_skills_with_valid_frontmatter(self):
        expected = {'amerika-os-overview', 'operate-desktop', 'system-settings', 'files-and-projects', 'software-and-updates',
                    'diagnose-and-repair', 'game-dev-studio', 'hardware-surface-laptop-7', 'voice-and-notifications',
                    'schedule-and-automation', 'privacy-and-safety'}
        self.assertEqual({d.name for d in skill_dirs()}, expected)
        for d in skill_dirs():
            text = (d / 'SKILL.md').read_text()
            meta, body = core.parse_frontmatter(text)
            self.assertEqual(meta['name'], d.name)
            self.assertRegex(meta['name'], r'^[a-z0-9-]{1,64}$')
            self.assertTrue(20 < len(meta['description']) <= 1024, d.name)
            self.assertLess(len(text.splitlines()), 250, d.name)
            self.assertIn('Failure handling', body, d.name)
            self.assertTrue(body.strip().startswith('#'), d.name)

    def test_commands_have_description(self):
        cmds = list((PLUGIN / 'commands').glob('*.md'))
        self.assertGreaterEqual(len(cmds), 5)
        for f in cmds:
            meta, body = core.parse_frontmatter(f.read_text())
            self.assertTrue(meta.get('description'), f.name)
            self.assertTrue(body.strip())

    def test_manual_copies_are_identical(self):
        main = (CLAUDE / 'AMERIKA.md').read_text()
        self.assertEqual((PLUGIN / 'AMERIKA.md').read_text(), main)
        self.assertEqual((PLUGIN / 'skills/amerika-os-overview/references/AMERIKA.md').read_text(), main)

    def test_references_exist(self):
        for d in skill_dirs():
            for ref in re.findall(r'`(references/[^`]+)`', (d / 'SKILL.md').read_text()):
                self.assertTrue((d / ref).exists(), f'{d.name}: {ref}')

    def test_no_secrets_or_real_paths_anywhere(self):
        bad = [re.compile(r'sk-ant-[A-Za-z0-9_-]{6,}'), re.compile(r'sk-[A-Za-z0-9]{20,}'), re.compile(r'BEGIN [A-Z ]*PRIVATE KEY'),
               re.compile(r'(?i)(api[_-]?key|password|token)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}'), re.compile(r'/home/ant')]
        files = [f for f in list(CLAUDE.rglob('*')) + [ROOT / 'docs/claude-os/skills.md', ROOT / 'tools/builders/claude.py'] if f.is_file()
                 and '__pycache__' not in f.parts]
        self.assertGreater(len(files), 20)
        for f in files:
            text = f.read_text(errors='replace')
            for rx in bad:
                self.assertIsNone(rx.search(text), f'{f}: {rx.pattern}')


class ToolReferences(unittest.TestCase):
    def test_every_amerika_tool_mentioned_exists(self):
        names = tool_names()
        rx = re.compile(r'(?<![\w./-])amerika\.([a-z_]+\.[a-z_]+)')
        seen = set()
        for f in list(PLUGIN.rglob('*.md')) + [CLAUDE / 'AMERIKA.md']:
            for ref in rx.findall(f.read_text()):
                seen.add(ref)
                self.assertIn(ref, names, f'{f.relative_to(CLAUDE)} mentions unknown tool amerika.{ref}')
        self.assertGreater(len(seen), 50)

    def test_every_tool_is_documented_in_the_manual(self):
        manual = (CLAUDE / 'AMERIKA.md').read_text()
        for name in tool_names():
            self.assertIn(f'amerika.{name}', manual, name)

    def test_studio_tool_names_exist(self):
        names = studio_names()
        text = (PLUGIN / 'skills/game-dev-studio/SKILL.md').read_text()
        found = set(re.findall(r'`((?:render|engine|sprite|box)_[a-z_]+)`', text))
        self.assertGreater(len(found), 25)
        for n in found:
            self.assertIn(n, names)

    def test_risk_claims_in_overview_match_registry(self):
        t = Tools(fake_shell())
        text = (PLUGIN / 'skills/amerika-os-overview/SKILL.md').read_text()
        for row in re.findall(r'^\| (read|act|sensitive|critical) \|(.*)\|', text, re.M):
            for name in re.findall(r'amerika\.([a-z_.]+)', row[1]):
                self.assertEqual(t.risk(name), row[0], name)
        manual = (CLAUDE / 'AMERIKA.md').read_text()
        for risk in ('read', 'act', 'sensitive', 'critical'):
            line = re.search(rf'^\*\*{risk}\*\*.*$', manual, re.M).group(0)
            for name in re.findall(r'amerika\.([a-z_.]+)', line):
                self.assertEqual(t.risk(name), risk, name)


class Installer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / 'home'
        self.home.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}

    def test_roundtrip_backup_manifest_idempotent(self):
        (self.home / '.claude/skills/my-own-skill').mkdir(parents=True)
        (self.home / '.claude/skills/my-own-skill/SKILL.md').write_text('mine')
        before = self.snapshot()
        r = core.install(self.home)
        self.assertTrue(r['changed'])
        self.assertTrue(Path(r['backup']).is_dir())
        self.assertIn(Path(r['backup']).parent, [self.home / '.local/state/amerika-os/claude-backup'])
        manifest = json.loads((self.home / '.local/state/amerika-os/claude-install.json').read_text())
        self.assertEqual(len([x for x in manifest['roots'] if '/skills/' in x]), 11)
        skill = self.home / '.claude/skills/amerika-operate-desktop/SKILL.md'
        meta, _ = core.parse_frontmatter(skill.read_text())
        self.assertEqual(meta['name'], 'amerika-operate-desktop')
        self.assertTrue((self.home / '.claude/skills/amerika-os-overview/references/AMERIKA.md').is_file())
        self.assertTrue((self.home / '.claude/plugins/amerika-marketplace/.claude-plugin/marketplace.json').is_file())
        plugin_mcp = json.loads((self.home / '.claude/plugins/amerika-marketplace/plugins/amerika-os/.mcp.json').read_text())
        self.assertIn('amerika', plugin_mcp['mcpServers'])
        self.assertEqual(core.status(self.home)['installed_skills'].__len__(), 11)
        self.assertEqual((self.home / '.claude/skills/my-own-skill/SKILL.md').read_text(), 'mine')
        again = core.install(self.home)
        self.assertFalse(again['changed'])
        self.assertEqual(len(list((self.home / '.local/state/amerika-os/claude-backup').iterdir())), 1)
        removed = core.remove(self.home)
        self.assertGreater(removed['removed'], 30)
        self.assertEqual(self.snapshot().keys() - {k for k in self.snapshot() if 'claude-backup' in k}, before.keys())
        self.assertFalse((self.home / '.local/state/amerika-os/claude-install.json').exists())
        self.assertFalse((self.home / '.claude/plugins').exists())
        self.assertTrue((self.home / '.claude/skills/my-own-skill').is_dir())

    def test_refuses_to_clobber_foreign_files_and_changes_nothing(self):
        target = self.home / '.claude/skills/amerika-operate-desktop'
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('someone else')
        before = self.snapshot()
        with self.assertRaises(core.InstallError):
            core.install(self.home)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.home / '.local/state/amerika-os').exists())

    def test_refuses_symlink_targets(self):
        (self.home / '.claude/skills').mkdir(parents=True)
        elsewhere = Path(self.tmp.name) / 'elsewhere'
        elsewhere.mkdir()
        (self.home / '.claude/skills/amerika-privacy-and-safety').symlink_to(elsewhere)
        with self.assertRaises(core.InstallError):
            core.install(self.home)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_remove_keeps_files_the_user_edited(self):
        core.install(self.home, plugin=False)
        edited = self.home / '.claude/skills/amerika-system-settings/SKILL.md'
        edited.write_text(edited.read_text() + '\nmy note\n')
        r = core.remove(self.home)
        self.assertEqual(len(r['kept']), 1)
        self.assertTrue(edited.exists())
        self.assertEqual(core.status(self.home)['modified'], ['.claude/skills/amerika-system-settings/SKILL.md'])
        r2 = core.remove(self.home, force=True)
        self.assertFalse(edited.exists())
        self.assertTrue(r2['installed'])

    def test_upgrade_replaces_older_managed_copy_with_backup(self):
        core.install(self.home, plugin=False)
        f = self.home / '.claude/skills/amerika-privacy-and-safety/SKILL.md'
        f.write_text('old version')
        (f.parent / 'stale.txt').write_text('x')
        r = core.install(self.home, plugin=False)
        self.assertTrue(r['changed'])
        self.assertIn('Privacy and safety', f.read_text())
        self.assertFalse((f.parent / 'stale.txt').exists())
        backed = list(Path(r['backup']).rglob('SKILL.md'))
        self.assertTrue(any(b.read_text() == 'old version' for b in backed))

    def test_remove_without_install_is_harmless(self):
        self.assertFalse(core.remove(self.home)['installed'])

    def test_skills_only_and_plugin_only(self):
        core.install(self.home, plugin=False)
        self.assertFalse((self.home / '.claude/plugins').exists())
        core.remove(self.home)
        core.install(self.home, skills=False)
        self.assertFalse((self.home / '.claude/skills').exists())
        self.assertTrue((self.home / '.claude/plugins/amerika-marketplace').is_dir())

    def test_studio_server_only_when_installed(self):
        with mock.patch.object(core, 'STUDIO_MCP_COMMAND', '/nonexistent/amerika-studio-mcp'):
            files = core.plugin_files()
        self.assertNotIn('amerika-studio', json.loads(files['plugins/amerika-os/.mcp.json'])['mcpServers'])
        with mock.patch.object(core, 'STUDIO_MCP_COMMAND', '/bin/sh'):
            files = core.plugin_files()
        self.assertEqual(json.loads(files['plugins/amerika-os/.mcp.json'])['mcpServers']['amerika-studio']['command'], '/bin/sh')

    def test_install_never_touches_the_real_home(self):
        before = REAL_HOME / '.claude'
        existed = before.exists()
        core.install(self.home)
        self.assertEqual(before.exists(), existed)
        if not existed:
            self.assertFalse(before.exists())

    def test_export_layout(self):
        out = Path(self.tmp.name) / 'export'
        written = core.export(out)
        zips = sorted(out.glob('*.zip'))
        self.assertEqual(len(zips), 11)
        self.assertEqual(len(written), 13)
        self.assertIn('/amerika-os:status', (out / 'commands.md').read_text())
        for z in zips:
            name = z.stem
            with zipfile.ZipFile(z) as zf:
                names = zf.namelist()
                self.assertIn(f'{name}/SKILL.md', names)
                self.assertTrue(all(n.startswith(name + '/') for n in names))
                meta, _ = core.parse_frontmatter(zf.read(f'{name}/SKILL.md').decode())
                self.assertEqual(meta['name'], name)
        with zipfile.ZipFile(out / 'amerika-os-overview.zip') as zf:
            self.assertIn('amerika-os-overview/references/AMERIKA.md', zf.namelist())
        text = (out / 'custom-instructions.md').read_text()
        self.assertIn('AltStack Desktop', text)
        self.assertIn('operating manual', text.lower())
        before = zips[0].read_bytes()
        core.export(out)
        self.assertEqual(before, zips[0].read_bytes())

    def test_export_refuses_foreign_instructions_file(self):
        out = Path(self.tmp.name) / 'e2'
        out.mkdir()
        (out / 'custom-instructions.md').write_text('my own')
        with self.assertRaises(core.InstallError):
            core.export(out)
        self.assertEqual((out / 'custom-instructions.md').read_text(), 'my own')
        self.assertEqual(list(out.glob('*.zip')), [])

    def test_doctor_reports_checks(self):
        checks = core.doctor(self.home)
        names = {c['name'] for c in checks}
        self.assertTrue({'plugin files', 'skill frontmatter', 'installed skills', 'Claude MCP connection'} <= names)
        self.assertEqual({c['state'] for c in checks if c['name'] == 'skill frontmatter'}, {'ok'})

    def test_cli_runs_against_temp_home(self):
        import subprocess
        env = dict(os.environ, HOME=str(self.home))
        run = lambda *a: subprocess.run([sys.executable, str(CLAUDE / 'bin/amerika-claude'), *a], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(run('status', '--json').returncode, 0)
        r = run('install')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(run('status', '--json').stdout)['installed_skills'].__len__(), 11)
        self.assertEqual(run('install', '--skills-only', '--plugin-only').returncode, 2)
        self.assertEqual(run('remove').returncode, 0)
        self.assertEqual(run('export', str(Path(self.tmp.name) / 'x')).returncode, 0)
        self.assertEqual(run('bogus').returncode, 2)


class ConnectIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_wrappers(self):
        self.assertTrue(connect.skills_status()['available'])
        self.assertFalse(connect.skills_status()['installed'])
        r = connect.install_skills()
        self.assertTrue(r['changed'])
        self.assertTrue(connect.skills_status()['installed'])
        self.assertTrue((Path(self.tmp.name) / '.claude/skills/amerika-os-overview/SKILL.md').is_file())
        self.assertGreater(connect.remove_skills()['removed'], 30)
        files = connect.export_skills(Path(self.tmp.name) / 'out')
        self.assertEqual(len(files), 13)

    def test_conflict_becomes_value_error(self):
        d = Path(self.tmp.name) / '.claude/skills/amerika-operate-desktop'
        d.mkdir(parents=True)
        with self.assertRaises(ValueError):
            connect.install_skills()

    def test_missing_package_is_reported(self):
        with mock.patch.object(connect, '_skills_core', return_value=None):
            self.assertFalse(connect.skills_status()['available'])
            with self.assertRaises(ValueError):
                connect.install_skills()

    def test_existing_connect_behaviour_unchanged(self):
        cfg = Path(self.tmp.name) / 'claude.json'
        with mock.patch.dict(os.environ, {'AMERIKA_CLAUDE_CONFIG': str(cfg)}):
            connect.connect_claude()
            self.assertTrue(connect.status()['claude'])
            connect.disconnect_claude()
            self.assertFalse(connect.status()['claude'])


class NewTools(unittest.TestCase):
    NEW = {'hw.report': 'read', 'journal.read': 'read', 'units.status': 'read', 'studio.status': 'read', 'bar.get': 'read',
           'ui.home': 'act', 'ui.caster': 'act', 'bar.set': 'act', 'ui.text_scale': 'act', 'ui.settings': 'act',
           'ui.relaunch': 'sensitive', 'ui.mode': 'sensitive', 'units.restart': 'sensitive', 'apps.close': 'sensitive', 'hw.perf': 'critical'}

    def setUp(self):
        self.shell = fake_shell()
        self.tools = Tools(self.shell)

    def test_registered_with_expected_risk_and_schema(self):
        for name, risk in self.NEW.items():
            t = self.tools.table[name]
            self.assertEqual(t['risk'], risk, name)
            self.assertFalse(t['schema']['additionalProperties'])
            self.assertTrue(t['description'])
        listing = {d['name']: d for d in self.tools.describe()}
        self.assertTrue(listing['hw.perf']['description'].startswith('[critical]'))

    def test_permission_decisions(self):
        b = Broker(SimpleNamespace(settings=self.shell.settings))
        for mode in ('ask', 'safe', 'trusted'):
            self.shell.settings['ai']['mode'] = mode
            self.assertEqual(b.decision('claude', 'hw.report'), 'allow')
            self.assertEqual(b.decision('claude', 'hw.perf'), 'ask')
            self.assertEqual(b.decision('claude', 'units.restart'), 'allow' if mode == 'trusted' else 'ask')
        self.shell.settings['ai']['mode'] = 'safe'
        self.assertEqual(b.decision('claude', 'ui.home'), 'allow')
        self.assertEqual(b.decision('claude', 'ui.mode'), 'ask')
        self.assertEqual(b.decision('claude', 'ui.relaunch'), 'ask')
        self.shell.settings['ai']['mode'] = 'ask'
        self.assertEqual(b.decision('claude', 'bar.set'), 'ask')
        self.shell.settings['ai']['clients'] = {'claude': {'always': ['hw.perf']}}
        self.shell.settings['ai']['mode'] = 'trusted'
        self.assertEqual(b.decision('claude', 'hw.perf'), 'ask')

    def test_argument_validation(self):
        call = self.tools.call
        bad = [('journal.read', {'lines': 'x'}), ('journal.read', {'priority': 'debug'}), ('journal.read', {'extra': 1}),
               ('hw.perf', {'mode': 'turbo'}), ('hw.perf', {}), ('units.restart', {}), ('apps.close', {}), ('bar.set', {})]
        for name, args in bad:
            with self.assertRaises(ValueError, msg=(name, args)):
                call(name, args)
        for args in ({'lines': 0}, {'lines': 501}, {'unit': '-x'}, {'unit': 'a b'}, {'unit': '$(id)'}, {'since': 'now; rm -rf ~'}):
            with self.assertRaises(ValueError, msg=args):
                call('journal.read', args)

    def test_journal_command_is_fixed_argv_and_redacts(self):
        captured = {}

        def fake_run(argv, **kw):
            captured['argv'] = argv
            return SimpleNamespace(returncode=0, stdout='ok sk-ant-api03-ABCDEFGH1234 password=hunter2\nline', stderr='')
        with mock.patch.object(tools_mod.subprocess, 'run', fake_run):
            out = self.tools.call('journal.read', {'lines': 50, 'unit': 'amerika-studio-bridge.service', 'priority': 'err', 'since': '1 hour ago'}).result(5)
        self.assertEqual(captured['argv'][:3], ['journalctl', '--user', '--no-pager'])
        self.assertIn('amerika-studio-bridge.service', captured['argv'])
        self.assertNotIn('hunter2', out['stdout'])
        self.assertNotIn('ABCDEFGH', out['stdout'])
        self.assertIn('[redacted]', out['stdout'])

    def test_units_confined_to_amerika(self):
        for unit in ('sshd', 'ssh.service', 'amerika', 'amerika-', 'amerika-x; reboot', '../amerika-x', 'AMERIKA-x', 'amerika-x y'):
            with self.assertRaises(ValueError, msg=unit):
                self.tools.call('units.status', {'unit': unit})
        for unit in ('amerika-shell.service', 'amerika-session.target', 'amerika-login-fallback.service', 'amerika-studio-bridge.timer',
                     'amerika-desktop.service', 'amerika-mcp.service', 'amerika-broker.service'):
            with self.assertRaises(ValueError, msg=unit):
                self.tools.call('units.restart', {'unit': unit})
        argvs = []
        with mock.patch.object(tools_mod.subprocess, 'run', lambda argv, **kw: argvs.append(argv) or SimpleNamespace(returncode=0, stdout='', stderr='')):
            self.tools.call('units.restart', {'unit': 'amerika-studio-bridge'}).result(5)
            self.tools.call('units.status', {'unit': 'amerika-agent-gateway.service'}).result(5)
        self.assertEqual(argvs[0], ['systemctl', '--user', 'restart', 'amerika-studio-bridge.service'])
        self.assertEqual(argvs[1][:3], ['systemctl', '--user', 'show'])

    def test_hw_and_studio_wrappers(self):
        seen = []

        def fake_run(argv, **kw):
            seen.append(argv)
            return SimpleNamespace(returncode=0, stdout='{"cpu": {"cores": 12}}', stderr='')
        with mock.patch.object(tools_mod.subprocess, 'run', fake_run):
            self.assertEqual(self.tools.call('hw.report', {}).result(5)['cpu']['cores'], 12)
            self.tools.call('studio.status', {}).result(5)
            self.tools.call('hw.perf', {'mode': 'game'}).result(5)
        self.assertEqual(seen[0][1:], ['report', '--json'])
        self.assertEqual(seen[1][1:], ['status', '--json'])
        self.assertEqual(seen[2][1:], ['perf', 'game'])

    def test_missing_helper_gives_clear_error(self):
        with mock.patch.dict(os.environ, {'AMERIKA_HW_COMMAND': '/nonexistent/amerika-hw'}):
            with self.assertRaises(ValueError) as cm:
                self.tools.call('hw.report', {}).result(5)
        self.assertIn('not installed', str(cm.exception))

    def test_ui_actions_defensive(self):
        with self.assertRaises(ValueError) as cm:
            self.tools.call('ui.home', {})
        self.assertIn('does not support', str(cm.exception))

        class New:
            settings = self.shell.settings
            windows = self.shell.windows
            called = []

            def action(self, name):
                if name == 'home':
                    self.called.append('home')
                elif name == 'caster':
                    self.called.append('caster')
                elif name.startswith('caster:') and name.split(':')[1] in ('next', 'prev'):
                    self.called.append(name)
                elif name == 'caster:close':
                    self.called.append(name)
                elif name.startswith('relaunch:'):
                    self.called.append(name)
        t = Tools(New())
        self.assertEqual(t.call('ui.home', {}), {'ok': True, 'action': 'home'})
        self.assertEqual(t.call('ui.caster', {})['action'], 'caster')
        t.call('ui.caster', {'op': 'next'})
        t.call('ui.caster', {'op': 'close'})
        t.call('ui.relaunch', {'app': 'claude'})
        self.assertEqual(New.called, ['home', 'caster', 'caster:next', 'caster:close', 'relaunch:claude'])
        for bad in ({'op': 'explode'},):
            with self.assertRaises(ValueError):
                t.call('ui.caster', bad)
        with self.assertRaises(ValueError):
            t.call('ui.relaunch', {'app': 'firefox'})

    def test_bar_set_matches_the_real_bar_model(self):
        from amerika.shell import barlayout
        bad = [{}, {'colour': 1}, {'height': 10}, {'height': 70}, {'opacity': 0.1}, {'opacity': 2}, {'preset': 'weird'}, {'layout': 'x'}, {'layout': []},
               {'layout': [{'id': 'nonsense'}]}, {'layout': [{'id': 'clock', 'zone': 'top'}]}, {'layout': [{'id': 'clock', 'evil': 1}]},
               {'layout': [{'id': 'clock', 'enabled': 'yes'}]}, {'layout': [{'id': 'clock', 'order': -1}]}, {'layout': [{'id': 'clock'}] * 33},
               {'clock_format': {'date': 'tiny'}}, {'clock_format': {'seconds': 1}}, {'clock_format': {'hour24': 'x'}}, {'clock_format': {'zz': 1}}, {'clock_format': {}}]
        for args in bad:
            with self.assertRaises(ValueError, msg=args):
                self.tools.call('bar.set', args)
        self.assertEqual(self.shell.updated, [])
        self.shell.settings['bar_clock_format'] = {'hour24': None, 'seconds': False, 'date': 'short'}
        out = self.tools.call('bar.set', {'clock_format': {'seconds': True}, 'height': 40, 'opacity': 0.8})
        self.assertEqual(out['bar_clock_format'], {'hour24': None, 'seconds': True, 'date': 'short'})
        self.assertEqual((out['bar_height'], out['bar_opacity']), (40, 0.8))
        out = self.tools.call('bar.set', {'preset': 'home'})
        self.assertEqual(out['bar_preset'], 'home')
        self.assertEqual(out['bar_layout'], barlayout.preset('home'))
        out = self.tools.call('bar.set', {'layout': [{'id': 'clock', 'enabled': True, 'zone': 'left'}]})
        self.assertEqual(out['bar_preset'], 'custom')
        self.assertEqual(len(out['bar_layout']), len(barlayout.WIDGETS))  # normalised to the complete layout
        got = self.tools.call('bar.get', {})
        self.assertEqual(set(got), set(Tools.BAR_KEYS))
        self.assertEqual(got['bar_preset'], 'custom')

    def test_text_scale(self):
        for bad in (0.5, 2.5, True):
            with self.assertRaises(ValueError):
                self.tools.call('ui.text_scale', {'app': 'claude', 'scale': bad})
        self.shell.settings['ai_text_scale'] = {'chatgpt': 1.25}
        out = self.tools.call('ui.text_scale', {'app': 'claude', 'scale': 1.4})
        self.assertEqual(out['ai_text_scale'], {'chatgpt': 1.25, 'claude': 1.4})
        self.assertEqual(self.shell.updated[-1], ('ai_text_scale', {'chatgpt': 1.25, 'claude': 1.4}))

    def test_ui_mode_uses_the_shell_presets_and_revert(self):
        from amerika.shell import home
        shell = self.shell
        changes = []
        shell.update_settings = lambda c: (changes.append(c), shell.settings.update(c))
        shell.settings.update({'home_mode': 'off', 'dock_enabled': True, 'copilot_app': 'claude'})
        out = self.tools.call('ui.mode', {'mode': 'claude'})
        self.assertEqual((out['home_mode'], out['dock_enabled']), ('claude', True))
        self.assertEqual(shell.settings['copilot_app'], 'caster')
        self.assertIn('claude_first_snapshot', shell.settings)
        self.tools.call('ui.mode', {'mode': 'revert'})
        self.assertEqual((shell.settings['home_mode'], shell.settings['dock_enabled'], shell.settings['copilot_app']), ('off', True, 'claude'))
        self.assertNotIn('claude_first_snapshot', shell.settings)
        with self.assertRaises(ValueError):
            self.tools.call('ui.mode', {'mode': 'revert'})
        self.tools.call('ui.mode', {'mode': 'chatgpt'})
        self.tools.call('ui.mode', {'mode': 'off'})
        self.assertEqual(home.mode(shell.settings), 'off')
        self.assertTrue(shell.settings['dock_enabled'])

    def test_ui_settings_opens_known_pages_only(self):
        with mock.patch.object(tools_mod.subprocess, 'Popen') as popen:
            self.assertEqual(self.tools.call('ui.settings', {'page': 'bluetooth'}), {'opened': 'bluetooth'})
            self.assertEqual(popen.call_args[0][0][1:], ['bluetooth'])
            for bad in ('--classic', 'x; reboot', 'nope'):
                with self.assertRaises(ValueError):
                    self.tools.call('ui.settings', {'page': bad})
            self.assertEqual(popen.call_count, 1)

    def test_apps_close(self):
        self.assertEqual(self.tools.call('apps.close', {'id': 'files'}), {'closed': 1})
        self.shell.windows.command.assert_called_with('close', '7')
        with self.assertRaises(ValueError):
            self.tools.call('apps.close', {'id': 'nothing'})

    def test_settings_set_follows_api_rules(self):
        from amerika.settings.api import RULES
        self.assertEqual(set(self.tools.table['settings.set']['schema']['properties']['key']['enum']), set(RULES))
        for key in ('home_mode', 'dock_enabled', 'bar_height', 'copilot_app'):
            self.assertIn(key, RULES)
        with self.assertRaises(ValueError):
            self.tools.call('settings.set', {'key': 'ai', 'value': {'mode': 'trusted'}})
        with self.assertRaises(ValueError):
            self.tools.call('settings.set', {'key': 'home_mode', 'value': 'plasma'})

    def test_new_calls_are_audited_with_the_existing_audit_path(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(common, 'STATE', Path(tmp)):
            common.audit('call', client='claude', tool='hw.perf', args={'mode': 'game'}, ok=True)
            events = common.read_audit()
            self.assertEqual(events[-1]['tool'], 'hw.perf')

    def test_redaction(self):
        text = 'a Bearer abcdefghijklmnop12345 b token=abc123 c api_key: zzz d ' + 'a' * 45
        out = tools_mod.redact_secrets(text)
        for leak in ('abcdefghijklmnop12345', 'abc123', 'zzz', 'a' * 45):
            self.assertNotIn(leak, out)


def command_files():
    return sorted((PLUGIN / 'commands').glob('*.md'))


class Commands(unittest.TestCase):
    REQUIRED = ('amerika status hw perf bench tune home caster chatgpt windows raise tile close move-desktop open apps quit bar clock theme wallpaper '
                'dock text-size settings volume brightness wifi bluetooth dnd night power-profile files find recent tidy clip shot notify remind install '
                'update uninstall journal fix restart-shell recover lock sleep logout reboot shutdown studio render engine sprite box game focus '
                'gamedev-mode presentation-mode classic-mode claude-mode agent').split()

    def test_full_set_present(self):
        names = {f.stem for f in command_files()}
        self.assertLessEqual(set(self.REQUIRED), names)
        self.assertTrue(40 <= len(names) <= 70, len(names))

    def test_frontmatter_and_arguments(self):
        for f in command_files():
            meta, body = core.parse_frontmatter(f.read_text())
            self.assertRegex(f.stem, r'^[a-z][a-z0-9-]*$')
            self.assertTrue(10 < len(meta['description']) < 160, f.name)
            self.assertLessEqual(set(meta), {'description', 'argument-hint', 'allowed-tools'}, f.name)
            if meta.get('argument-hint'):
                self.assertIn('$ARGUMENTS', body, f.name)
            if f.stem not in ('amerika',):
                self.assertIn('Verify the result with a read tool and report only what you verified', body, f.name)
            self.assertIn('follow the', body)

    def test_allowed_tools_are_read_only_amerika_tools(self):
        t = Tools(fake_shell())
        by_alias = {n.replace('.', '_'): n for n in t.table}
        for f in command_files():
            meta, _ = core.parse_frontmatter(f.read_text())
            for item in [x.strip() for x in meta.get('allowed-tools', '').split(',') if x.strip()]:
                m = re.fullmatch(r'mcp__(?:plugin_amerika-os_)?amerika__([a-z_]+)', item)
                self.assertTrue(m, (f.name, item))
                self.assertIn(m.group(1), by_alias, (f.name, item))
                self.assertEqual(t.risk(by_alias[m.group(1)]), 'read', (f.name, item))

    def test_tool_references_exist(self):
        names = tool_names()
        studio = studio_names()
        rx = re.compile(r'(?<![\w./-])amerika\.([a-z_]+\.[a-z_]+)')
        for f in command_files():
            text = f.read_text()
            for ref in rx.findall(text):
                self.assertIn(ref, names, f'{f.name}: amerika.{ref}')
            for ref in re.findall(r'`((?:render|engine|sprite|box)_[a-z_]+)`', text):
                self.assertIn(ref, studio, f'{f.name}: {ref}')
            for ref in re.findall(r'`(studio_[a-z_]+)', text):
                self.assertIn(ref, studio, f'{f.name}: {ref}')

    def test_dangerous_commands_confirm_and_use_critical_tools(self):
        expect = {'reboot': 'amerika.power.reboot', 'shutdown': 'amerika.power.poweroff', 'sleep': 'amerika.power.suspend',
                  'logout': 'amerika.shell.run', 'perf': 'amerika.hw.perf'}
        for name, tool in expect.items():
            text = (PLUGIN / 'commands' / f'{name}.md').read_text()
            self.assertIn(tool, text)
            self.assertRegex(text, r'(?i)confirm|clear yes|wait for a yes')
        for name in ('tidy', 'install', 'update', 'uninstall', 'close', 'quit'):
            self.assertRegex((PLUGIN / 'commands' / f'{name}.md').read_text(), r'(?i)wait for|approve|confirm|ask')
        self.assertNotIn('amerika.files.delete', (PLUGIN / 'commands/tidy.md').read_text().replace('goes through `amerika.files.delete`', ''))
        for name in ('install', 'update', 'uninstall'):
            text = (PLUGIN / 'commands' / f'{name}.md').read_text()
            self.assertIn('Never', text)

    def test_cheat_sheet_lists_every_command(self):
        sheet = (CLAUDE / 'commands.md').read_text()
        self.assertEqual(sheet, (PLUGIN / 'commands.md').read_text())
        for f in command_files():
            self.assertIn(f'`/amerika-os:{f.stem}`', sheet)
        index = (PLUGIN / 'commands/amerika.md').read_text()
        for f in command_files():
            if f.stem != 'amerika':
                self.assertIn(f'/amerika-os:{f.stem}', index)

    def test_docs_list_the_commands(self):
        doc = (ROOT / 'docs/claude-os/skills.md').read_text()
        for f in command_files():
            self.assertIn(f'/amerika-os:{f.stem}', doc, f.stem)

    def test_generator_is_in_sync(self):
        import subprocess
        before = {f: f.read_text() for f in command_files()}
        r = subprocess.run([sys.executable, str(ROOT / 'tools/gen-claude-commands.py')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({f: f.read_text() for f in command_files()}, before)


class McpAliases(unittest.TestCase):
    def test_alias_is_a_valid_anthropic_tool_name_for_every_tool(self):
        from amerika.ai import mcp
        names = tool_names()
        aliased = [mcp.alias(n) for n in names]
        self.assertEqual(len(set(aliased)), len(names), 'two tools collide after aliasing')
        for a in aliased:
            self.assertRegex(a, r'^[a-zA-Z0-9_-]{1,64}$')

    def test_list_advertises_aliases_and_call_maps_back(self):
        import io
        from amerika.ai import mcp
        t = Tools(fake_shell())
        calls = []

        def broker(req):
            calls.append(req)
            if req['method'] == 'list':
                return {'ok': True, 'result': t.describe()}
            return {'ok': True, 'result': {'tool': req['tool']}}
        lines = [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                 {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'windows_move_resize', 'arguments': {'id': '1'}}},
                 {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'windows.list', 'arguments': {}}}]
        out = io.StringIO()
        mcp.serve('claude', io.StringIO('\n'.join(json.dumps(m) for m in lines) + '\n'), out, broker)
        res = [json.loads(x) for x in out.getvalue().splitlines()]
        advertised = [x['name'] for x in res[0]['result']['tools']]
        self.assertIn('windows_move_resize', advertised)
        self.assertFalse([n for n in advertised if '.' in n])
        self.assertEqual(len(advertised), len(t.table))
        self.assertEqual([c['tool'] for c in calls if c['method'] == 'call'], ['windows.move_resize', 'windows.list'])

    def test_call_before_list_still_maps(self):
        import io
        from amerika.ai import mcp
        t = Tools(fake_shell())
        seen = []

        def broker(req):
            seen.append(req)
            return {'ok': True, 'result': t.describe()} if req['method'] == 'list' else {'ok': True, 'result': 1}
        out = io.StringIO()
        mcp.serve('claude', io.StringIO(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'audio_set_volume', 'arguments': {'percent': 5}}}) + '\n'), out, broker)
        self.assertEqual([r['tool'] for r in seen if r['method'] == 'call'], ['audio.set_volume'])

    def test_instructions_use_valid_names(self):
        from amerika.ai import mcp
        self.assertNotIn('windows.list', mcp.INSTRUCTIONS)


class Packaging(unittest.TestCase):
    def test_builder(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('claude_builder', ROOT / 'tools/builders/claude.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        calls = {}

        class Pkg:
            def __init__(self, name, version, desc, **kw):
                calls.update(name=name, kw=kw, copies=[], scripts={})
                self.scripts = calls['scripts']
                self.root = Path(tempfile.mkdtemp())

            def path(self, p):
                return self.root / str(p).lstrip('/')

            def copy(self, src, dest, mode=None):
                calls['copies'].append((str(dest), Path(src).exists()))

            def copyright(self, t):
                pass
        b = SimpleNamespace(Pkg=Pkg, OS=ROOT / 'src/os', ROOT=ROOT, DE_VERSION='3.2.2')
        builders = mod.register(b)
        self.assertEqual(list(builders), ['amerika-claude'])
        builders['amerika-claude']()
        self.assertEqual(calls['kw']['arch'], 'all')
        self.assertIn('amerika-desktop-shell', calls['kw']['depends'])
        self.assertEqual(calls['scripts'], {})
        self.assertTrue(all(ok for _d, ok in calls['copies']), calls['copies'])
        self.assertIn('/usr/bin/amerika-claude', [d for d, _ in calls['copies']])


if __name__ == '__main__':
    unittest.main()
