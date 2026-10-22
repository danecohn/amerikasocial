"""Amerika Engine: recipe schema, components, assembler (golden), tools over the real control endpoint, the GDScript tool
loop against a fake bridge, templates smoke-run, screenshot under the KWin rig, launcher and packaging.

Real Godot is used wherever it can be found (AMERIKA_GODOT, work/tools/godot, or `godot` on PATH); those tests skip with a
clear message otherwise. No network, no real API calls, no keys. Set AMERIKA_UPDATE_GOLDEN=1 to rewrite golden files.
"""
import base64
import http.server
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'src/os/engine'
ADDON = ENGINE / 'addons/amerika_engine'
TEMPLATES = ENGINE / 'templates'
FIX = ROOT / 'tests/fixtures/engine'
GOLDEN = FIX / 'golden'
sys.path.insert(0, str(ENGINE))
from amerika_engine import components_gen, project, recipe as R, theme  # noqa: E402


_REAL_RUN = subprocess.run
_patch = None


def setUpModule():  # other test modules leak a patched subprocess.run; use the real one here
    global _patch
    from unittest import mock
    _patch = mock.patch('subprocess.run', _REAL_RUN)
    _patch.start()


def tearDownModule():
    _patch.stop()


def find_godot():
    env = os.environ.get('AMERIKA_GODOT')
    cands = [env] if env else []
    cands += [str(ROOT.parent / 'tools/godot/Godot_v4.7.2-stable_linux.arm64'), shutil.which('godot4') or '', shutil.which('godot') or '']
    for c in cands:
        if c and os.access(c, os.X_OK):
            return c
    return None


GODOT = find_godot()
need_godot = unittest.skipUnless(GODOT, 'Godot not found (set AMERIKA_GODOT or unpack Godot 4.7.2 arm64 into work/tools/godot)')


def load_template(tid):
    return json.loads((TEMPLATES / tid / 'amerika_recipe.json').read_text())


def run_godot(proj, *args, timeout=120, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([GODOT, '--headless', '--path', str(proj), *args], capture_output=True, text=True, timeout=timeout, env=e)


def make_project(tmp, tid, assemble=True):
    d = Path(tmp) / tid
    project.new_project(d, load_template(tid)['name'], tid if assemble else None, GODOT if assemble else None, assemble=assemble)
    return d


# ---------------------------------------------------------------------------------------------- pure Python

class RecipeSchemaTests(unittest.TestCase):
    def test_all_templates_validate(self):
        for t in sorted(TEMPLATES.iterdir()):
            issues = R.errors(R.validate(json.loads((t / 'amerika_recipe.json').read_text())))
            self.assertEqual(issues, [], t.name)
            meta = json.loads((t / 'template.json').read_text())
            self.assertEqual(meta['id'], t.name)

    def test_five_plus_templates_cover_the_genres(self):
        genres = {json.loads((t / 'template.json').read_text())['genre'] for t in TEMPLATES.iterdir()}
        self.assertTrue({'platformer_2d', 'topdown_2d', 'third_person_3d', 'first_person_3d', 'visual_novel', 'puzzle'} <= genres)

    def test_component_registry_matches_scripts(self):
        committed = json.loads((ADDON / 'components/components.json').read_text())
        self.assertEqual(components_gen.generate(ADDON / 'components'), committed, 'run src/os/engine/amerika_engine/components_gen.py')
        public = [k for k, v in committed['components'].items() if not v['internal']]
        schema = json.loads((ADDON / 'recipe.schema.json').read_text())
        self.assertEqual(sorted(schema['$defs']['component']['properties']['type']['enum']), sorted(public))
        self.assertGreaterEqual(len(public), 15)

    def test_invalid_recipes_report_codes(self):
        base = load_template('platformer_2d')

        def codes(mut):
            r = json.loads(json.dumps(base))
            mut(r)
            return {i['code'] for i in R.validate(r)}
        self.assertIn('E_SCHEMA', codes(lambda r: r.pop('genre')))
        self.assertIn('E_SCHEMA', codes(lambda r: r.update(bogus=1)))
        self.assertIn('E_ENTITY_UNKNOWN', codes(lambda r: r['levels'][0]['legend'].update(c='nothing')))
        self.assertIn('E_LEGEND_CHAR', codes(lambda r: r['levels'][0]['rows'].append('?')))
        self.assertIn('E_SCHEMA', codes(lambda r: r['entities']['coin']['components'].append({'type': 'fly'})))
        self.assertIn('E_PARAM_UNKNOWN', codes(lambda r: r['entities']['coin']['components'][0].update(bad=1)))
        self.assertIn('E_PARAM_TYPE', codes(lambda r: r['entities']['coin']['components'][0].update(value='x')))
        self.assertIn('E_PARAM_ENUM', codes(lambda r: r['entities']['coin']['components'][0].update(kind='nope')))
        self.assertIn('E_COMPONENT_DIMS', codes(lambda r: r['entities']['coin']['components'].append({'type': 'first_person_controller'})))
        self.assertIn('E_NO_PLAYER', codes(lambda r: r['entities'].pop('player')))
        self.assertIn('E_AUDIO_KEY', codes(lambda r: r['levels'][0].update(music='nope')))
        vn = load_template('visual_novel')
        vn['story']['nodes']['intro']['next'] = 'ghost'
        self.assertIn('E_STORY_NODE', {i['code'] for i in R.validate(vn)})

    def test_schema_file_is_valid_json_with_defs(self):
        s = json.loads((ADDON / 'recipe.schema.json').read_text())
        self.assertEqual(s['properties']['recipe_version']['const'], 1)
        self.assertEqual(sorted(s['properties']['genre']['enum']),
                         sorted(['platformer_2d', 'topdown_2d', 'third_person_3d', 'first_person_3d', 'puzzle', 'visual_novel']))


class SafetyTextTests(unittest.TestCase):
    def test_no_api_key_or_network_in_plugin(self):
        for f in ADDON.rglob('*.gd'):
            t = f.read_text()
            self.assertNotIn('x-api-key', t.lower(), f.name)
            self.assertNotIn('api.anthropic.com', t, f.name)
            self.assertNotRegex(t, r'sk-ant-[A-Za-z0-9]', f.name)
        t = (ADDON / 'bridge.gd').read_text()
        self.assertIn('127.0.0.1', t)
        self.assertIn('studio-token', t)
        self.assertIn('X-Amerika-App: " + APP', t)

    def test_no_godot3_apis_in_shipped_scripts(self):
        bad = re.compile(r'\b(KinematicBody|yield\(|\.instance\(\)|rand_range|OS\.get_ticks_msec|Spatial)\b')
        for f in ADDON.rglob('*.gd'):
            if f.name == 'system_prompt.gd':  # the prompt names the Godot 3 APIs it forbids
                continue
            self.assertIsNone(bad.search(f.read_text()), f.name)

    def test_never_executes_shell(self):
        for f in ADDON.rglob('*.gd'):
            t = f.read_text()
            self.assertNotIn('OS.execute("/bin/sh', t)
            self.assertNotIn('OS.execute("sh', t)
            self.assertNotIn('OS.shell_open', t)


class LauncherTests(unittest.TestCase):
    def test_launcher_new_project_dry_run_and_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'cfg'
            fake = Path(tmp) / 'godot'
            fake.write_text('#!/bin/sh\nexit 0\n')
            fake.chmod(0o755)
            env = dict(os.environ, PYTHONPATH=str(ENGINE), AMERIKA_ENGINE_CONFIG=str(cfg), AMERIKA_ENGINE_SHARE=str(ENGINE))
            r = subprocess.run([sys.executable, '-m', 'amerika_engine.launcher', '--godot', str(fake), '--new', 'Neon Test', '--dir', tmp,
                                '--dry-run'], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('--editor --path', r.stdout)
            proj = Path(tmp) / 'Neon-Test'
            self.assertTrue((proj / 'addons/amerika_engine/plugin.cfg').exists())
            self.assertIn('amerika_engine/plugin.cfg', (proj / 'project.godot').read_text())
            self.assertTrue((proj / 'splash.png').exists())
            self.assertTrue((proj / 'icon.svg').exists())
            tres = (cfg / 'godot/editor_settings-4.tres').read_text()
            self.assertIn('interface/theme/accent_color', tres)
            theme.seed(cfg)  # idempotent
            lst = subprocess.run([sys.executable, '-m', 'amerika_engine.launcher', '--list-templates'], capture_output=True, text=True, env=env)
            self.assertIn('platformer_2d', lst.stdout)
            ver = subprocess.run([sys.executable, '-m', 'amerika_engine.launcher', '--version'], capture_output=True, text=True, env=env)
            self.assertIn('not affiliated with or endorsed by the Godot Foundation', ver.stdout)

    def test_desktop_entry_and_notice(self):
        d = (ENGINE / 'applications/amerika-engine.desktop').read_text()
        self.assertIn('Name=Amerika Engine', d)
        self.assertIn('Exec=amerika-engine', d)
        self.assertIn('not affiliated with or endorsed', (ENGINE / 'NOTICE').read_text())
        self.assertIn('Permission is hereby granted', (ENGINE / 'GODOT-LICENSE.txt').read_text())
        self.assertIn('<svg', (ENGINE / 'icons/amerika-engine-project.svg').read_text())


class PackagingTests(unittest.TestCase):
    def test_package_contents(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)

        class Pkg:
            def __init__(s, name, version, desc, **kw):
                s.name, s.kw, s.root, s.scripts, s.desc = name, kw, tmp / name, {}, desc
                s.root.mkdir(parents=True)

            def path(s, p):
                return s.root / str(p).lstrip('/')

            def file(s, d, t, m=0o644):
                q = s.path(d)
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(t)

            def copy(s, src, d, m=None):
                q = s.path(d)
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, q)

            def copyright(s, t):
                s.file(f'/usr/share/doc/{s.name}/copyright', t)
        b = type('B', (), {})()
        b.Pkg, b.OS, b.ROOT, b.DE_VERSION = Pkg, ROOT / 'src/os', ROOT, '3.2.0-1'
        spec = importlib.util.spec_from_file_location('engine_builder', ROOT / 'tools/builders/engine.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pkg = mod.register(b)['amerika-engine']()
        root = pkg.root
        for rel in ('usr/bin/amerika-engine', 'usr/lib/python3/dist-packages/amerika_engine/launcher.py',
                    'usr/share/amerika-engine/addons/amerika_engine/plugin.cfg', 'usr/share/amerika-engine/addons/amerika_engine/recipe.schema.json',
                    'usr/share/amerika-engine/addons/amerika_engine/components/health.gd', 'usr/share/amerika-engine/templates/platformer_2d/amerika_recipe.json',
                    'usr/share/applications/amerika-engine.desktop', 'usr/share/doc/amerika-engine/NOTICE', 'usr/share/doc/amerika-engine/GODOT-LICENSE.txt',
                    'usr/share/doc/amerika-engine/copyright'):
            self.assertTrue((root / rel).exists(), rel)
        self.assertFalse(list(root.rglob('__pycache__')))
        self.assertIn('amerika-studio (>= 3.2.0-1)', pkg.kw['depends'])
        self.assertIn('godot (>= 4.4)', pkg.kw['depends'])
        self.assertEqual(getattr(mod, 'META_DEPENDS', []), [])
        self.assertNotIn('godot', [p.name for p in root.rglob('godot*') if p.is_file() and p.stat().st_size > 1_000_000])
        self.assertIn('Godot Engine', (root / 'usr/share/doc/amerika-engine/copyright').read_text())


# ---------------------------------------------------------------------------------------------- real Godot

@need_godot
class AssemblerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.projects = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def proj(self, tid):
        if tid not in self.projects:
            self.projects[tid] = make_project(self.tmp, tid)
        return self.projects[tid]

    def test_golden_platformer(self):
        p = self.proj('platformer_2d')
        files = ['amerika_game.json', 'entities/player.tscn', 'entities/coin.tscn', 'entities/blob.tscn', 'levels/level_1.tscn', 'ui/hud.tscn']
        if os.environ.get('AMERIKA_UPDATE_GOLDEN'):
            for f in files:
                (GOLDEN / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(p / f, GOLDEN / f)
        for f in files:
            self.assertTrue((GOLDEN / f).exists(), f'missing golden {f}')
            self.assertEqual((p / f).read_text(), (GOLDEN / f).read_text(), f)

    def test_assembly_is_deterministic_and_keeps_hand_edits(self):
        p = self.proj('arena_3d')
        before = {f: (p / f).read_text() for f in ('levels/arena.tscn', 'entities/player.tscn', 'amerika_game.json')}
        proj_before = (p / 'project.godot').read_text()
        project.assemble_project(p, GODOT)
        for f, t in before.items():
            self.assertEqual((p / f).read_text(), t, f)
        self.assertEqual((p / 'project.godot').read_text(), proj_before)
        edited = p / 'entities/chaser.tscn'
        edited.write_text(edited.read_text() + '\n; hand edit\n')
        r = project.assemble_project(p, GODOT)
        self.assertIn('res://entities/chaser.tscn', r['skipped'])
        self.assertIn('hand edit', edited.read_text())

    def test_project_settings_generated(self):
        t = (self.proj('platformer_2d') / 'project.godot').read_text()
        self.assertIn('AmerikaGame="*res://addons/amerika_engine/runtime/game.gd"', t)
        self.assertIn('run/main_scene="res://levels/level_1.tscn"', t)
        self.assertIn('[input]', t)
        self.assertIn('physical_keycode":32', t)  # jump = Space
        self.assertIn('amerika_engine/plugin.cfg', t)

    def test_gdscript_validator_matches_python(self):
        p = self.proj('platformer_2d')
        base = load_template('platformer_2d')
        cases = {}

        def case(name, mut):
            r = json.loads(json.dumps(base))
            mut(r)
            cases[name] = r
        case('genre', lambda r: r.pop('genre'))
        case('legend', lambda r: r['levels'][0]['legend'].update(c='nothing'))
        case('char', lambda r: r['levels'][0]['rows'].append('?'))
        case('comp', lambda r: r['entities']['coin']['components'].append({'type': 'fly'}))
        case('param', lambda r: r['entities']['coin']['components'][0].update(bad=1))
        case('ptype', lambda r: r['entities']['coin']['components'][0].update(value='x'))
        case('enum', lambda r: r['entities']['coin']['components'][0].update(kind='nope'))
        case('dims', lambda r: r['entities']['coin']['components'].append({'type': 'first_person_controller'}))
        case('noplayer', lambda r: r['entities'].pop('player'))
        case('valid', lambda r: None)
        for name, rec in cases.items():
            (p / 'cmp.json').write_text(json.dumps(rec))
            out = run_godot(p, '-s', 'res://addons/amerika_engine/cli.gd', '--', 'validate', 'cmp.json').stdout
            rep = json.loads(next(l for l in out.splitlines() if l.startswith('AMERIKA_REPORT '))[15:])
            gd = sorted({i['code'] for i in rep['issues'] if i['severity'] == 'error'})
            py = sorted({i['code'] for i in R.validate(rec) if i['severity'] == 'error'})
            self.assertEqual(gd, py, name)

    def test_every_template_runs_headless_without_errors(self):
        for t in sorted(TEMPLATES.iterdir()):
            p = self.proj(t.name)
            rep = p / 'report.json'
            r = run_godot(p, '--fixed-fps', '60', '--quit-after', '700', '--', '--amerika-agent', '--amerika-frames=300',
                          '--amerika-input=move_right@0.2-1.5,move_up@0.2-0.8,shoot@0.3-2.0,jump@0.6-0.7', f'--amerika-report={rep}')
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, f'{t.name}\n{out[-1500:]}')
            self.assertNotRegex(out, r'(?m)^(SCRIPT ERROR|ERROR):', f'{t.name}\n{out[-1500:]}')
            data = json.loads(rep.read_text())
            self.assertEqual(data['frames'], 300, t.name)

    def test_platformer_is_playable(self):
        p = self.proj('platformer_2d')
        rep = p / 'play.json'
        run_godot(p, '--fixed-fps', '60', '--quit-after', '900', '--', '--amerika-agent', '--amerika-frames=300',
                  '--amerika-input=move_right@0.2-1.8', f'--amerika-report={rep}')
        data = json.loads(rep.read_text())
        self.assertGreater(data['player'][0], 250)       # ran to the right
        self.assertGreaterEqual(data['score'], 20)       # collected coins
        self.assertEqual(data['state'], 'playing')

    def test_visual_novel_and_memory_logic(self):
        p = self.proj('visual_novel')
        (p / 'vn_test.gd').write_text('''extends SceneTree
func _initialize():
	var scene = load("res://scenes/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	var seen := []
	var guard := 0
	while not scene.finished and guard < 60:
		guard += 1
		seen.append(scene.current_id)
		scene.advance()
		scene.advance()
		await process_frame
		if scene.choices_visible:
			scene.choose(0)
	print("VN ", ",".join(seen), " finished=", scene.finished, " flag=", root.get_node("AmerikaGame").has_flag("answered"))
	quit()
''')
        out = run_godot(p, '-s', 'res://vn_test.gd').stdout
        self.assertIn('finished=true', out)
        self.assertIn('flag=true', out)
        self.assertIn('answer', out)
        m = self.proj('memory_puzzle')
        (m / 'mem_test.gd').write_text('''extends SceneTree
func _initialize():
	var scene = load("res://scenes/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	var by := {}
	for i in range(scene.cards.size()):
		var s = scene.cards[i]["symbol"]
		if not by.has(s): by[s] = []
		by[s].append(i)
	for s in by:
		scene.flip(by[s][0])
		scene.flip(by[s][1])
	print("MEM matched=", scene.matched, " state=", root.get_node("AmerikaGame").state, " moves=", scene.moves)
	quit()
''')
        out = run_godot(m, '-s', 'res://mem_test.gd').stdout
        self.assertIn('matched=8 state=won moves=8', out)


# ---------------------------------------------------------------------------------------------- editor + RPC

class FakeBridge:
    """Stands in for amerika-studio-bridge: checks the token and app header, plays back canned tool_use responses."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.token = 'test-token-FAKE'
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(n))
                ok = self.headers.get('Authorization') == f'Bearer {outer.token}' and self.headers.get('X-Amerika-App') == 'engine'
                outer.requests.append({'ok_auth': ok, 'body': body, 'path': self.path})
                if not ok:
                    return self._send(401, {'error': {'type': 'auth', 'message': 'bad token'}})
                step = outer.script.pop(0) if outer.script else {'text': 'done'}
                content = []
                if step.get('text'):
                    content.append({'type': 'text', 'text': step['text']})
                if step.get('tool'):
                    content.append({'type': 'tool_use', 'id': f'toolu_{len(outer.requests)}', 'name': step['tool'], 'input': step.get('input', {})})
                self._send(200, {'id': 'msg', 'type': 'message', 'role': 'assistant', 'model': body['model'], 'content': content,
                                 'stop_reason': 'tool_use' if step.get('tool') else 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1}})

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def tool_results(requests):
    out = []
    for rq in requests:
        m = rq['body']['messages'][-1]
        if m['role'] == 'user':
            for b in m['content']:
                if b.get('type') == 'tool_result':
                    out.append(b)
    return out


@need_godot
class ToolLoopTests(unittest.TestCase):
    def run_loop(self, tid, steps, prompt='make it', extra_env=None, wrapper=None, timeout=240):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        proj = make_project(tmp, tid, assemble=False)
        shutil.copy(FIX / 'loop_runner.gd', proj / 'loop_runner.gd')
        bridge = FakeBridge(steps)
        self.addCleanup(bridge.close)
        tokfile = Path(tmp) / 'token'
        tokfile.write_text(bridge.token + '\n')
        env = dict(os.environ, AMERIKA_STUDIO_URL=f'http://127.0.0.1:{bridge.port}', AMERIKA_STUDIO_TOKEN_FILE=str(tokfile),
                   AMERIKA_TEST_PROMPT=prompt, AMERIKA_ENGINE_TEMPLATES=str(TEMPLATES), AMERIKA_STUDIO_DIR=str(Path(tmp) / 'Studio'))
        env.update(extra_env or {})
        cmd = [GODOT, '--headless', '--path', str(proj), '-s', 'res://loop_runner.gd']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        line = next((l for l in r.stdout.splitlines() if l.startswith('LOOP_RESULT ')), None)
        self.assertIsNotNone(line, r.stdout[-1500:] + r.stderr[-800:])
        return proj, bridge, json.loads(line[len('LOOP_RESULT '):])

    def test_recipe_to_running_game_loop(self):
        steps = [
            {'text': 'Looking at the project.', 'tool': 'get_recipe', 'input': {}},
            {'tool': 'assemble_recipe', 'input': {'recipe': 'platformer_2d'}},
            {'tool': 'run_project', 'input': {'frames': 240, 'input': 'move_right@0.2-2.0'}},
            {'tool': 'create_script', 'input': {'path': 'scripts/bad.gd', 'code': 'extends Node\nfunc x(:\n'}},
            {'tool': 'read_file', 'input': {'path': '../../etc/passwd'}},
            {'text': 'Your platformer is ready: arrows to run, Space to jump.'},
        ]
        proj, bridge, res = self.run_loop('platformer_2d', steps)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['tool_calls'], ['get_recipe', 'assemble_recipe', 'run_project', 'create_script', 'read_file'])
        self.assertTrue(all(r['ok_auth'] for r in bridge.requests))
        first = bridge.requests[0]['body']
        self.assertIn('res://amerika_recipe.json', first['system'])
        self.assertIn('platformer_controller', first['system'])
        names = {t['name'] for t in first['tools']}
        for n in ('project_info', 'list_files', 'read_file', 'write_file', 'create_scene', 'describe_scene', 'add_node', 'set_property',
                  'attach_script', 'create_script', 'edit_script', 'get_recipe', 'set_recipe', 'assemble_recipe', 'import_model',
                  'run_project', 'stop_project', 'get_output_and_errors', 'game_screenshot', 'set_input_map', 'set_export_preset'):
            self.assertIn(n, names)
        results = tool_results(bridge.requests)
        self.assertEqual(len(results), 5)
        asm = json.loads(results[1]['content'])
        self.assertTrue(asm['ok'], asm)
        self.assertTrue((proj / 'levels/level_1.tscn').exists())
        run = json.loads(results[2]['content'])
        self.assertTrue(run['clean'], run)
        self.assertGreater(run['report']['player'][0], 150)
        bad = json.loads(results[3]['content'])
        self.assertFalse(bad['ok'])
        self.assertIn('does not compile', bad['error'])
        self.assertFalse((proj / 'scripts/bad.gd').exists())
        self.assertTrue(results[3]['is_error'])
        outside = json.loads(results[4]['content'])
        self.assertEqual(outside['code'], -32003)

    def test_tools_edit_scene_script_input_and_undo(self):
        steps = [
            {'tool': 'create_script', 'input': {'path': 'scripts/hello.gd', 'code': 'extends Node2D\n\nvar greeting: String = "hi"\n\nfunc _ready() -> void:\n\tprint(greeting)\n'}},
            {'tool': 'edit_script', 'input': {'path': 'scripts/hello.gd', 'edits': [{'old': '"hi"', 'new': '"hello"'}]}},
            {'tool': 'edit_script', 'input': {'path': 'scripts/hello.gd', 'edits': [{'old': 'greeting: String', 'new': 'greeting: Strin g'}]}},
            {'tool': 'create_scene', 'input': {'path': 'scenes/test.tscn', 'root_type': 'Node2D', 'nodes': [{'name': 'Label', 'type': 'Label', 'properties': {'text': 'hello', 'position': [10, 20]}}]}},
            {'tool': 'attach_script', 'input': {'scene': 'scenes/test.tscn', 'node': '.', 'script': 'scripts/hello.gd'}},
            {'tool': 'set_property', 'input': {'scene': 'scenes/test.tscn', 'node': 'Label', 'property': 'modulate', 'value': '#ff3d6e'}},
            {'tool': 'describe_scene', 'input': {'path': 'scenes/test.tscn'}},
            {'tool': 'set_input_map', 'input': {'actions': {'dash': ['Shift', 'Mouse:Right']}}},
            {'tool': 'set_export_preset', 'input': {'platform': 'linux', 'path': 'build/game.x86_64'}},
            {'tool': 'write_file', 'input': {'path': 'addons/amerika_engine/evil.gd', 'content': 'extends Node\n'}},
            {'tool': 'write_file', 'input': {'path': 'notes.exe', 'content': 'x'}},
            {'text': 'ok'},
        ]
        proj, bridge, res = self.run_loop('platformer_2d', steps)
        self.assertTrue(res['ok'], res)
        r = [json.loads(x['content']) for x in tool_results(bridge.requests)]
        self.assertTrue(r[0]['ok'] and r[1]['ok'], r[:2])
        self.assertIn('"hello"', (proj / 'scripts/hello.gd').read_text())
        self.assertFalse(r[2]['ok'])
        self.assertIn('greeting: String', (proj / 'scripts/hello.gd').read_text())  # untouched
        self.assertTrue(r[3]['ok'], r[3])
        self.assertTrue(r[4]['ok'], r[4])
        self.assertTrue(r[5]['ok'], r[5])
        tree = r[6]['tree']
        self.assertEqual(tree['script'], 'res://scripts/hello.gd')
        self.assertEqual(tree['children'][0]['name'], 'Label')
        self.assertIn('modulate', tree['children'][0]['properties'])
        self.assertTrue(r[7]['ok'], r[7])
        self.assertIn('dash={', (proj / 'project.godot').read_text())
        self.assertTrue(r[8]['ok'])
        self.assertIn('platform="Linux"', (proj / 'export_presets.cfg').read_text())
        self.assertEqual(r[9]['code'], -32003)
        self.assertFalse(r[10]['ok'])
        # one chat request = one undo checkpoint with every touched file
        hist = sorted((proj / '.amerika/history').iterdir())
        self.assertEqual(len(hist), 1)
        manifest = json.loads((hist[0] / 'manifest.json').read_text())
        paths = {f['path'] for f in manifest['files']}
        self.assertIn('res://scripts/hello.gd', paths)
        self.assertIn('res://scenes/test.tscn', paths)
        self.assertTrue((hist[0] / 'before').is_dir() and (hist[0] / 'after').is_dir())

    def test_undo_restores_files(self):
        steps = [{'tool': 'write_file', 'input': {'path': 'notes.md', 'content': 'v1\n'}}, {'text': 'wrote'}]
        proj, _b, res = self.run_loop('platformer_2d', steps)
        self.assertTrue(res['ok'])
        self.assertEqual((proj / 'notes.md').read_text(), 'v1\n')
        script = proj / 'undo.gd'
        script.write_text('extends SceneTree\nconst T := preload("res://addons/amerika_engine/tools.gd")\nfunc _initialize():\n\tvar t = T.new(self)\n'
                          '\tvar s = t.history.last_session()\n\tprint("UNDO ", JSON.stringify(t.history.restore(s["id"], false)))\n'
                          '\tprint("EXISTS ", FileAccess.file_exists("res://notes.md"))\n\tprint("REDO ", JSON.stringify(t.history.restore(s["id"], true)))\n'
                          '\tprint("EXISTS ", FileAccess.file_exists("res://notes.md"))\n\tquit()\n')
        out = run_godot(proj, '-s', 'res://undo.gd').stdout
        self.assertIn('EXISTS false', out)
        self.assertLess(out.index('EXISTS false'), out.rindex('EXISTS true'))

    def test_import_asset_is_confined_to_studio_folder(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        studio = Path(tmp) / 'Studio/Sprite/g'
        studio.mkdir(parents=True)
        try:
            from PIL import Image
            Image.new('RGBA', (16, 16), (255, 0, 0, 255)).save(studio / 'hero.png')
        except ImportError:
            (studio / 'hero.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='))
        outside = Path(tmp) / 'secret.png'
        outside.write_bytes((studio / 'hero.png').read_bytes())
        steps = [{'tool': 'import_model', 'input': {'source_path': str(studio / 'hero.png')}},
                 {'tool': 'import_model', 'input': {'source_path': str(outside)}},
                 {'tool': 'import_model', 'input': {'source_path': str(studio / 'hero.png'), 'dest': '../escape'}},
                 {'text': 'done'}]
        proj, bridge, res = self.run_loop('platformer_2d', steps, extra_env={'AMERIKA_STUDIO_DIR': str(Path(tmp) / 'Studio')})
        r = [json.loads(x['content']) for x in tool_results(bridge.requests)]
        self.assertTrue(r[0]['ok'], r[0])
        self.assertTrue((proj / 'sprites/hero.png').exists())
        self.assertTrue((proj / 'sprites/hero.png.import').exists(), 'import wait did not produce .import')
        self.assertFalse(r[1]['ok'])
        self.assertEqual(r[1]['code'], -32003)
        self.assertEqual(r[2]['code'], -32003)


@need_godot
class EditorEndpointTests(unittest.TestCase):
    """Starts the REAL editor headless with the plugin enabled and talks JSON-RPC to its control endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.rt = Path(cls.tmp) / 'run'
        cls.rt.mkdir(mode=0o700)
        cls.proj = make_project(cls.tmp, 'arena_3d')
        env = dict(os.environ, XDG_RUNTIME_DIR=str(cls.rt), XDG_CONFIG_HOME=str(Path(cls.tmp) / 'cfg'), AMERIKA_ENGINE_TEMPLATES=str(TEMPLATES))
        cls.proc = subprocess.Popen([GODOT, '--editor', '--headless', '--path', str(cls.proj)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        cls.desc_path = cls.rt / 'amerika/studio-engine.json'
        t0 = time.time()
        while time.time() - t0 < 90 and not cls.desc_path.exists():
            time.sleep(0.5)
        if not cls.desc_path.exists():
            cls.tearDownClass()
            raise unittest.SkipTest('editor did not start in time')
        cls.desc = json.loads(cls.desc_path.read_text())

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'proc', None):
            cls.proc.send_signal(signal.SIGTERM)  # exact PID
            try:
                cls.proc.wait(10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
        shutil.rmtree(cls.tmp, True)

    def rpc(self, method, params=None, token=None, raw=False):
        req = urllib.request.Request(self.desc['url'] + '/rpc', json.dumps({'jsonrpc': '2.0', 'id': 7, 'method': method, 'params': params or {}}).encode(),
                                     {'Authorization': 'Bearer ' + (token or self.desc['token']), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            e.close()
            if raw:
                return e.code
            raise

    def test_descriptor_is_private_and_loopback(self):
        self.assertEqual(oct(self.desc_path.stat().st_mode & 0o777), '0o600')
        self.assertEqual(self.desc['app'], 'engine')
        self.assertTrue(self.desc['url'].startswith('http://127.0.0.1:'))
        self.assertEqual(self.desc['pid'], self.proc.pid)

    def test_auth_and_ping(self):
        self.assertEqual(self.rpc('app.ping')['result'], {'app': 'engine', 'ok': True, 'ready': True, 'version': '3.1.1'})
        self.assertEqual(self.rpc('app.ping', token='wrong', raw=True), 401)
        self.assertEqual(self.rpc('engine.nope')['error']['code'], -32601)

    def test_tools_json_engine_tools_are_all_implemented(self):
        tj = ROOT / 'src/os/studio/tools.json'
        if not tj.exists():
            self.skipTest('tools.json not present')
        names = [t['name'] for t in json.loads(tj.read_text())['apps']['engine']['tools']]
        for n in names:
            if n == 'app.prompt':
                continue
            r = self.rpc('engine.' + n, {} if n not in ('files.read', 'scene.describe', 'import.model') else {'path': 'x', 'source_path': '/nonexistent'})
            if 'error' in r:
                self.assertNotEqual(r['error']['code'], -32601, n)
        r = self.rpc('app.prompt', {'message': 'hi'})  # no token file here: clean error, not a crash
        self.assertFalse(r['result']['ok'] if 'result' in r else False)

    def test_project_info_and_confinement(self):
        info = self.rpc('engine.project.info')['result']
        self.assertTrue(info['editor'])
        self.assertEqual(info['recipe']['genre'], 'third_person_3d')
        self.assertIn('AmerikaGame', info['autoloads'])
        for bad in ('../x.txt', '/etc/passwd', 'a/../../b', '.git/config', '.godot/x', 'res://../x'):
            r = self.rpc('engine.files.read', {'path': bad})
            self.assertEqual(r['error']['code'], -32003, bad)
        ok = self.rpc('engine.files.list', {'path': 'levels'})['result']
        self.assertIn('res://levels/arena.tscn', [e['path'] for e in ok['entries']])
        self.assertIn('error', self.rpc('engine.files.write', {'path': 'a.exe', 'content': 'x'}))

    def test_symlink_escape_is_refused(self):
        outside = Path(self.tmp) / 'outside'
        outside.mkdir(exist_ok=True)
        (outside / 'secret.txt').write_text('s')
        link = self.proj / 'linked'
        if not link.exists():
            link.symlink_to(outside)
        r = self.rpc('engine.files.read', {'path': 'linked/secret.txt'})
        self.assertEqual(r['error']['code'], -32003)

    def test_scene_script_recipe_and_run(self):
        d = self.rpc('engine.scene.describe', {'path': 'levels/arena.tscn'})['result']
        self.assertEqual(d['tree']['type'], 'Node3D')
        names = [c['name'] for c in d['tree']['children']]
        self.assertIn('Player', names)
        rec = self.rpc('engine.recipe.get')['result']
        self.assertTrue(rec['has_recipe'])
        self.assertTrue(any(t['id'] == 'platformer_2d' for t in rec['templates']))
        bad = load_template('arena_3d')
        bad['levels'][0]['legend']['o'] = 'ghost'
        r = self.rpc('engine.recipe.set', {'name': 'main', 'recipe': bad})
        self.assertEqual(r['error']['code'], -32602)
        good = load_template('arena_3d')
        good['rules'] = {'win': {'type': 'score', 'target': 30}, 'lose': {'type': 'health_zero'}}
        self.assertTrue(self.rpc('engine.recipe.set', {'name': 'main', 'recipe': good})['result']['ok'])
        asm = self.rpc('engine.recipe.assemble', {})['result']
        self.assertTrue(asm['ok'], asm)
        self.assertEqual(asm['scene_load_errors'], [])
        self.assertIn('"target": 30', (self.proj / 'amerika_game.json').read_text())
        run = self.rpc('engine.project.run', {'frames': 200, 'input': 'move_up@0.1-1.0'})['result']
        self.assertTrue(run['clean'], run)
        logs = self.rpc('engine.project.logs', {'lines': 20})['result']
        self.assertFalse(logs['running'])
        code = self.rpc('engine.script.create', {'path': 'scripts/s.gd', 'code': 'extends Node\nfunc _ready( -> void:\n\tpass\n'})
        self.assertIn('does not compile', code['error']['message'])
        h = self.rpc('engine.history.list')['result']['sessions']
        self.assertTrue(h)
        undone = self.rpc('engine.history.undo', {})['result']
        self.assertTrue(undone['ok'])

    def test_screenshot_without_display_is_a_clean_error(self):
        if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY'):
            self.skipTest('a display is available')
        r = self.rpc('engine.game.screenshot', {})
        self.assertEqual(r['error']['code'], -32004)


# ---------------------------------------------------------------------------------------------- rendering under the KWin rig

def rig_available():
    return (shutil.which('kwin_wayland') is not None and (ROOT.parent / 'tools/dbus-dl/root/usr/bin/dbus-run-session').exists()
            and (ROOT / 'tools/kwin-rig.sh').exists())


@need_godot
@unittest.skipUnless(rig_available(), 'KWin rig (kwin_wayland + dbus-run-session) not available: screenshots not verified')
class ScreenshotRigTests(unittest.TestCase):
    def test_game_screenshot_tool_renders_real_pixels(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        proj = make_project(tmp, 'platformer_2d')
        shutil.copy(FIX / 'loop_runner.gd', proj / 'loop_runner.gd')
        bridge = FakeBridge([{'tool': 'game_screenshot', 'input': {'frames': 90, 'input': 'move_right@0.1-1.0', 'width': 640}}, {'text': 'seen'}])
        self.addCleanup(bridge.close)
        tokfile = Path(tmp) / 'token'
        tokfile.write_text(bridge.token)
        out = Path(tmp) / 'out.txt'
        runner = Path(tmp) / 'run.sh'
        runner.write_text(f'#!/bin/sh\ncd {proj}\nAMERIKA_STUDIO_URL=http://127.0.0.1:{bridge.port} AMERIKA_STUDIO_TOKEN_FILE={tokfile} '
                          f'AMERIKA_TEST_PROMPT=shot timeout 150 {GODOT} --headless --path {proj} -s res://loop_runner.gd > {out} 2>&1\n')
        runner.chmod(0o755)
        env = dict(os.environ, WAYLAND_DISPLAY='', DISPLAY='')
        subprocess.run(['sh', str(ROOT / 'tools/kwin-rig.sh'), str(runner)], capture_output=True, text=True, timeout=240, env=env)
        text = out.read_text() if out.exists() else ''
        self.assertIn('LOOP_RESULT', text, text[-1500:])
        res = {}
        if tool_results(bridge.requests):
            c = tool_results(bridge.requests)[0]['content']
            res = json.loads(c[0]['text'] if isinstance(c, list) else c)
        shots = list((proj / '.amerika/shots').glob('*.png'))
        self.assertTrue(shots, f'no screenshot produced: {res}\n{text[-1200:]}')
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('PIL missing; screenshot exists but was not inspected')
        im = Image.open(shots[0]).convert('RGB')
        colors = im.getcolors(1 << 20)
        self.assertGreater(len(colors), 8, 'screenshot looks blank')
        self.assertTrue(res.get('ok'), res)
        self.assertIn('image', json.dumps(bridge.requests[1]['body']['messages'][-1]))
        keep = os.environ.get('AMERIKA_KEEP_SHOT')
        if keep:
            shutil.copy(shots[0], keep)


if __name__ == '__main__':
    unittest.main()
