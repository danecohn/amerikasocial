"""Amerika Render: tool validation, AST safety, tool loop, control endpoint, and REAL headless Blender runs.

Blender is found via $AMERIKA_TEST_BLENDER, `blender` on PATH, or ../tools/blender-test/blender (rootless extraction of the
Ubuntu arm64 package). Without it the Blender tests are skipped with a clear message. No real API calls: a fake bridge answers.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / 'src/os/render'
sys.path.insert(0, str(RENDER))
from amerika_render import agent, config, control, prompt, safety, schema, session as sess, toolspecs  # noqa: E402


def find_blender():
    cands = [os.environ.get('AMERIKA_TEST_BLENDER'), shutil.which('blender'), str(ROOT.parent / 'tools/blender-test/blender')]
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


BLENDER = find_blender()


class Validation(unittest.TestCase):
    def test_every_tool_has_schema_and_unique_name(self):
        names = [s['name'] for s in toolspecs.SPECS]
        self.assertEqual(len(names), len(set(names)))
        for name in ('scene_info', 'create_primitive', 'transform_object', 'add_modifier', 'edit_mesh', 'create_mesh_from_data', 'set_material',
                     'assign_collection', 'set_origin', 'uv_unwrap', 'import_file', 'export_file', 'set_camera', 'set_light', 'set_world',
                     'viewport_screenshot', 'render_preview', 'delete_object', 'undo', 'run_python'):
            self.assertIn(name, names)
        for s in toolspecs.SPECS:
            self.assertEqual(s['input_schema']['type'], 'object')
            self.assertGreater(len(s['description']), 60, s['name'])
        self.assertEqual(toolspecs.BY_NAME['run_python']['risk'], 'critical')

    def test_validation(self):
        sch = toolspecs.BY_NAME['create_primitive']['input_schema']
        out = schema.validate({'type': 'cube', 'name': 'Box', 'size': 2}, sch)
        self.assertFalse(out['smooth'])
        for bad in ({'type': 'blob', 'name': 'x'}, {'type': 'cube'}, {'type': 'cube', 'name': 'x', 'size': -1},
                    {'type': 'cube', 'name': 'x', 'location': [1, 2]}, {'type': 'cube', 'name': 'x', 'bogus': 1},
                    {'type': 'cube', 'name': 'x', 'size': True}):
            with self.assertRaises(schema.ValidationError, msg=bad):
                schema.validate(bad, sch)

    def test_confinement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            self.assertEqual(config.confine('a/b.glb', root), root / 'a/b.glb')
            for bad in ('../x.glb', '/etc/passwd', 'a/../../x', ''):
                with self.assertRaises(config.PathError):
                    config.confine(bad, root)
            (root / 'link').symlink_to('/tmp')
            with self.assertRaises(config.PathError):
                config.confine('link/x.glb', root)

    def test_bridge_only_loopback(self):
        with unittest.mock.patch.dict(os.environ, {'AMERIKA_STUDIO_BRIDGE': 'https://api.anthropic.com'}):
            with self.assertRaises(RuntimeError):
                config.bridge_url()


class Safety(unittest.TestCase):
    def rejects(self, code):
        self.assertTrue(safety.check(code), code)

    def test_rejects_dangerous(self):
        for code in ('import os', 'import subprocess', 'import socket', 'import ctypes', 'from os import system', 'import sys',
                     'import os.path', 'from bpy import utils', 'open("/etc/passwd")', 'eval("1")', 'exec("1")', '__import__("os")',
                     'compile("1","x","exec")', 'getattr(bpy, "ops")', 'x = bpy.app.handlers', 'bpy.ops.wm.quit_blender()',
                     'bpy.ops.script.python_file_run()', 'bpy.utils.script_path_user()', 'bpy.path.abspath("//")',
                     "().__class__.__bases__[0].__subclasses__()", 'random._os.system("id")', 'math.__dict__',
                     'f = lambda: 0\nf.__globals__', 'bpy.ops.export_scene.gltf()', 'bpy.data.texts.new("x")',
                     'bpy.data.images.load("/etc/passwd")', 'bpy.data.libraries.load("x")', 'import importlib', 'import builtins',
                     'class A: pass', 'globals()', 'vars(bpy)', 'while True:\n    import os', 'from . import x', 'import numpy',
                     '"{0.__class__}".format(1)', 'bpy.context.preferences.filepaths', 'bpy.data.images["x"].save()', 'type(bpy)'):
            self.rejects(code)

    def test_accepts_normal(self):
        ok = ('import bpy, bmesh, math\nfrom mathutils import Vector\nbm = bmesh.new()\nbmesh.ops.create_cube(bm, size=1)\nprint(len(bm.verts))\n'
              'for o in bpy.data.objects:\n    o.location.z += 1\nbpy.data.objects.remove(bpy.data.objects[0])\n')
        self.assertEqual(safety.check(ok), [])

    def test_runtime_hook_and_timeout(self):
        with self.assertRaises(safety.UnsafeCode):
            safety.run('import os', {})
        out = safety.run('import math\nprint(round(math.pi, 2))', {})
        self.assertEqual(out['stdout'].strip(), '3.14')
        with self.assertRaises(safety.Timeout):
            safety.run('while True:\n    pass', {}, timeout=0.3)
        with self.assertRaises(safety.UnsafeCode):
            safety.run('print(open)', {})

    def test_size_limit(self):
        self.assertTrue(safety.check('x=1\n' * 60000))


class FakeBridge:
    """Loopback fake of the Amerika Studio bridge. `script(request_body, n)` returns the response dict."""

    def __init__(self, script):
        self.script, self.requests, self.headers = script, [], []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.requests.append(body)
                outer.headers.append(dict(self.headers))
                resp = outer.script(body, len(outer.requests))
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def tool_use(i, _tool, **inp):
    return {'type': 'tool_use', 'id': f'tu{i}', 'name': _tool, 'input': inp}


def reply(*blocks, stop='tool_use'):
    return {'content': list(blocks), 'stop_reason': stop, 'usage': {'input_tokens': 5, 'output_tokens': 5}}


class Loop(unittest.TestCase):
    """The tool loop with a fake executor: no Blender needed."""

    def test_loop_images_pruning_and_errors(self):
        def script(body, n):
            if n == 1:
                return reply({'type': 'text', 'text': 'plan'}, tool_use(1, 'viewport_screenshot'), tool_use(2, 'create_primitive', type='cube'))
            return reply({'type': 'text', 'text': 'done'}, stop='end_turn')
        fb = FakeBridge(script)
        self.addCleanup(fb.close)
        png = b'\x89PNG fake'

        def execu(name, inp):
            if name == 'viewport_screenshot':
                return {'ok': True, 'result': {'view': 'x'}, 'images': [png]}
            return {'ok': False, 'error': 'invalid input: missing name', 'images': []}
        events = []
        loop = agent.Loop(agent.Bridge(fb.url, token='sk-ant-test-FAKE-bridge-token'), execu, on_event=lambda k, **kw: events.append(k))
        res = loop.run('make a cube')
        self.assertEqual(res['text'], 'done')
        self.assertEqual([c['ok'] for c in res['tool_calls']], [True, False])
        second = fb.requests[1]['messages'][-1]['content']
        self.assertEqual(second[0]['content'][1]['type'], 'image')
        self.assertTrue(second[1]['is_error'])
        self.assertEqual(fb.headers[0].get('X-Amerika-App'), 'render')
        self.assertTrue(fb.headers[0]['Authorization'].startswith('Bearer '))
        self.assertIn('tools', fb.requests[0])
        self.assertNotIn('x-api-key', {k.lower() for k in fb.headers[0]})
        msgs = [{'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': str(i), 'content': [{'type': 'image', 'source': {}}]}]} for i in range(7)]
        agent.prune_images(msgs, 4)
        self.assertEqual(sum(1 for m in msgs if m['content'][0]['content'][0]['type'] == 'image'), 4)

    def test_cancel_and_bridge_error(self):
        loop = agent.Loop(agent.Bridge('http://127.0.0.1:9', token='t', timeout=2), lambda n, i: {'ok': True, 'result': {}}, cancel=threading.Event())
        res = loop.run('hi')
        self.assertIn('cannot reach', res['error'])
        loop.cancel.set()
        self.assertTrue(loop.run('again')['stopped'])

    def test_review_gate(self):
        s = sess.Session()
        calls = []
        s.main.submit = lambda fn, **kw: calls.append(1) or {'ok': True, 'result': {}, 'images': []}
        t = threading.Thread(target=lambda: calls.append(('res', s.executor('run_python', {'code': 'x=1'}))))
        t.start()
        for _ in range(100):
            if s.pending:
                break
            threading.Event().wait(0.02)
        self.assertEqual(s.pending['name'], 'run_python')
        s.decide(False)
        t.join(5)
        self.assertFalse(calls[-1][1]['ok'])
        self.assertEqual(calls[-1][1]['code'], -32001)
        self.assertEqual(len([c for c in calls if c == 1]), 0)


@unittest.skipUnless(BLENDER, 'Blender not available: set AMERIKA_TEST_BLENDER or extract Ubuntu blender to ../tools/blender-test (see docs/studio/render.md)')
class RealBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='amerika-render-test-'))
        cls.runtime = cls.tmp / 'run'
        (cls.runtime / 'amerika').mkdir(parents=True, mode=0o700)
        (cls.runtime / 'amerika/studio-token').write_text('test-token-FAKE')
        cls.project = cls.tmp / 'project'
        cls.project.mkdir()
        tree_png_holder = {}

        def script(body, n):
            last = body['messages'][-1]
            if n == 1:
                return reply({'type': 'text', 'text': 'Plan: trunk + three cones, flat colours.'}, tool_use(1, 'scene_info'))
            if n == 2:
                parts = [tool_use(2, 'create_primitive', type='cylinder', name='Tree_Trunk', radius=0.18, radius2=0.12, depth=1.2, location=[0, 0, 0.6], segments=8)]
                for k, (r, z) in enumerate(((1.0, 1.6), (0.75, 2.3), (0.5, 2.9))):
                    parts.append(tool_use(3 + k, 'create_primitive', type='cone', name=f'Tree_Foliage_{k}', radius=r, depth=1.1, location=[0, 0, z], segments=8))
                parts += [tool_use(6, 'set_material', objects=['Tree_Trunk'], material='Bark', base_color='#6b4226', roughness=0.9),
                          tool_use(7, 'set_material', objects=['Tree_Foliage_0', 'Tree_Foliage_1', 'Tree_Foliage_2'], material='Leaves', base_color='#2f8f3a', roughness=0.8),
                          tool_use(8, 'assign_collection', objects=['Tree_Trunk', 'Tree_Foliage_0', 'Tree_Foliage_1', 'Tree_Foliage_2'], collection='Pine_Tree'),
                          tool_use(9, 'set_origin', name='Tree_Trunk', mode='bottom_center'),
                          tool_use(10, 'set_light', name='Sun', type='SUN', energy=4, rotation_deg=[50, 0, 30]),
                          tool_use(11, 'set_world', sky_gradient={'horizon': '#ffe2b0', 'zenith': '#6a9ad8'}, strength=1),
                          tool_use(12, 'viewport_screenshot', view='perspective', width=480, height=360)]
                return reply({'type': 'text', 'text': 'Building.'}, *parts)
            if n == 3:
                # the screenshot must have come back as an IMAGE block
                results = last['content']
                shot = [r for r in results if r['tool_use_id'] == 'tu12'][0]
                cls_ = [b['type'] for b in shot['content']]
                assert 'image' in cls_, cls_
                return reply({'type': 'text', 'text': 'Looks good; check and render.'}, tool_use(13, 'check_game_ready'),
                             tool_use(14, 'render_preview', engine='auto', width=640, height=480, samples=8, save_to='renders/tree.png'),
                             tool_use(15, 'export_file', path='models/pine_tree.glb', format='glb'),
                             tool_use(16, 'export_file', path='../escape.glb', format='glb'),
                             tool_use(17, 'run_python', code='import os\nos.system("id")'),
                             tool_use(18, 'run_python', code='print(len(bpy.data.objects))'))
            if last['content'] == 'say hi':
                return reply({'type': 'text', 'text': 'Control prompt answered.'}, stop='end_turn')
            return reply({'type': 'text', 'text': 'Made a low-poly pine tree (4 parts).'}, stop='end_turn')
        cls.fake = FakeBridge(script)
        driver = cls.tmp / 'driver.py'
        driver.write_text(DRIVER)
        env = dict(os.environ, XDG_RUNTIME_DIR=str(cls.runtime), AMERIKA_STUDIO_BRIDGE=cls.fake.url, AMERIKA_RENDER_PROJECT=str(cls.project),
                   BLENDER_USER_RESOURCES=str(cls.tmp / 'res'), AMERIKA_TEST_RENDER_SRC=str(RENDER), AMERIKA_TEST_REPORT=str(cls.tmp / 'report.json'),
                   XDG_STATE_HOME=str(cls.tmp / 'state'), HOME=str(cls.tmp / 'home'))
        (cls.tmp / 'home').mkdir()
        # keep a Blender located by wrapper working with our HOME
        proc = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', str(driver)], env=env, capture_output=True, text=True, timeout=400)
        cls.log = proc.stdout[-4000:] + proc.stderr[-2000:]
        rep = cls.tmp / 'report.json'
        cls.report = json.loads(rep.read_text()) if rep.exists() else None

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()
        keep = os.environ.get('AMERIKA_TEST_KEEP')
        if keep and (cls.project / 'renders/tree.png').exists():
            shutil.copy(cls.project / 'renders/tree.png', keep)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_report_exists(self):
        self.assertIsNotNone(self.report, self.log)
        self.assertNotIn('driver_error', self.report, self.report.get('driver_error'))

    def test_low_poly_tree_built(self):
        r = self.report
        self.assertEqual(r['result']['text'], 'Made a low-poly pine tree (4 parts).')
        stats = r['stats']
        self.assertEqual(sorted(o for o in stats['objects'] if o.startswith('Tree_')), ['Tree_Foliage_0', 'Tree_Foliage_1', 'Tree_Foliage_2', 'Tree_Trunk'])
        self.assertGreater(stats['triangles'], 40)
        self.assertLess(stats['triangles'], 500)
        self.assertEqual(stats['collection'], ['Pine_Tree'] * 4)
        self.assertGreaterEqual(stats['materials'], 2)
        self.assertAlmostEqual(stats['trunk_bottom_z'], 0.0, places=3)

    def test_tool_outcomes(self):
        by = {c['name']: [] for c in self.report['result']['tool_calls']}
        for c in self.report['result']['tool_calls']:
            by[c['name']].append(c['ok'])
        self.assertTrue(all(by['create_primitive']))
        self.assertEqual(by['export_file'], [True, False])     # outside the project is refused
        self.assertEqual(by['run_python'], [False, True])      # `import os` rejected, plain bpy code runs

    def test_files(self):
        r = self.report
        self.assertTrue(r['glb_bytes'] > 1000)
        self.assertEqual(r['glb_magic'], 'glTF')
        self.assertTrue(r['png_ok'], r)
        self.assertFalse((self.tmp / 'escape.glb').exists())
        self.assertTrue(r['checkpoint_exists'])
        self.assertEqual(r['png_size'], [640, 480])
        self.assertGreater(r['png_colors'], 50)                # a real picture, not a flat fill

    def test_bridge_headers_and_no_key(self):
        h = self.fake.headers[0]
        self.assertEqual(h.get('X-Amerika-App'), 'render')
        self.assertEqual(h.get('Authorization'), 'Bearer test-token-FAKE')
        blob = json.dumps(self.fake.requests)
        self.assertNotIn('sk-ant', blob)

    def test_control_endpoint(self):
        c = self.report['control']
        self.assertTrue(c['ping']['ok'])
        self.assertGreaterEqual(c['info']['totals']['meshes'], 4)
        self.assertEqual(c['shot']['images'][0]['mime'], 'image/png')
        self.assertTrue(c['export']['path'].endswith('ctl.glb'))
        self.assertEqual(c['outside']['error']['code'], -32003)
        self.assertEqual(c['badmethod']['error']['code'], -32601)
        self.assertEqual(c['badparams']['error']['code'], -32602)
        self.assertEqual(c['unauth'], 401)
        self.assertEqual(c['prompt']['text'], 'Control prompt answered.')
        self.assertEqual(c['descriptor_mode'], '600')
        self.assertTrue(c['descriptor_removed'])
        self.assertEqual(c['python']['stdout'].strip(), 'hi')

    def test_undo_checkpoint_roundtrip(self):
        self.assertTrue(self.report['undo']['checkpoint_restored_scene_empty_of_tree'])

    def test_game_ready_audit_runs(self):
        self.assertIn('problems', self.report['audit'])


DRIVER = r'''
import json, os, sys, threading, time, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, os.environ['AMERIKA_TEST_RENDER_SRC'])
import bpy
report = {}
try:
    from amerika_render import config, control, session as sm, tools
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    proj = config.project_dir()
    s = sm.Session(project_dir=str(proj))
    s.review_run_python = False
    assert s.start('make a low poly pine tree')
    assert s.wait(300, pump=True), 'assistant did not finish'
    report['result'] = s.last_result
    sc = bpy.context.scene
    objs = [o for o in sc.objects if o.type == 'MESH']
    tris = 0
    for o in objs:
        o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
    trunk = bpy.data.objects['Tree_Trunk']
    from amerika_render.tools import world_bbox
    report['stats'] = {'objects': [o.name for o in sc.objects], 'triangles': tris,
                       'collection': [bpy.data.objects[n].users_collection[0].name for n in ('Tree_Trunk', 'Tree_Foliage_0', 'Tree_Foliage_1', 'Tree_Foliage_2')],
                       'materials': len([m for m in bpy.data.materials if m.users]), 'trunk_bottom_z': world_bbox(trunk)[0].z}
    glb = proj / 'models/pine_tree.glb'
    report['glb_bytes'] = glb.stat().st_size if glb.exists() else 0
    report['glb_magic'] = glb.read_bytes()[:4].decode() if glb.exists() else ''
    png = proj / 'renders/tree.png'
    try:
        from PIL import Image
        im = Image.open(png)
        report['png_ok'] = True; report['png_size'] = list(im.size)
        report['png_colors'] = len(im.convert('RGB').getcolors(1 << 20) or [])
    except ImportError:
        data = png.read_bytes()
        report['png_ok'] = data[:8] == b'\x89PNG\r\n\x1a\n'
        report['png_size'] = [int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')]
        report['png_colors'] = 999
    first_ckpt = tools.CHECKPOINT['path']
    report['checkpoint_exists'] = bool(tools.CHECKPOINT['path'] and Path(tools.CHECKPOINT['path']).exists())
    report['audit'] = tools.call('check_game_ready', {})['result']

    # ---- control endpoint, driven from a thread while the main thread pumps
    srv = control.Server(s, token='ctl-token-FAKE')
    desc = Path(os.environ['XDG_RUNTIME_DIR']) / 'amerika/studio-render.json'
    srv.start(desc)
    out = {}
    def rpc(method, params=None, token='ctl-token-FAKE'):
        req = urllib.request.Request(srv.url + '/rpc', data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode(),
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=120).read())
    def client():
        try:
            out['ping'] = rpc('render.app.ping')['result']
            out['info'] = rpc('render.scene.info')['result']
            out['shot'] = rpc('render.viewport.screenshot', {'width': 256, 'height': 192, 'view': 'front'})['result']
            out['export'] = rpc('render.export', {'format': 'glb', 'path': 'models/ctl.glb'})['result']
            out['outside'] = rpc('render.export', {'format': 'glb', 'path': '../../x.glb'})
            out['badmethod'] = rpc('render.nope')
            out['badparams'] = rpc('render.scene.run_python', {})
            out['python'] = rpc('render.scene.run_python', {'code': 'print("hi")'})['result']
            try:
                rpc('render.app.ping', token='wrong')
            except urllib.error.HTTPError as e:
                out['unauth'] = e.code
            out['descriptor_mode'] = oct(desc.stat().st_mode & 0o777)[2:]
            d = json.loads(desc.read_text()); assert d['token'] == 'ctl-token-FAKE' and d['app'] == 'render'
            out['prompt'] = rpc('render.app.prompt', {'message': 'say hi', 'timeout_s': 60})['result']
        except Exception as e:
            out['client_error'] = repr(e)
        out['done'] = True
    t = threading.Thread(target=client, daemon=True); t.start()
    s.main.pump_until(lambda: out.get('done'), 300)
    srv.stop()
    out['descriptor_removed'] = not desc.exists()
    report['control'] = out

    # ---- checkpoint round trip: restore the request-start checkpoint (taken before the tree existed)
    tools.restore_checkpoint(first_ckpt)
    report['undo'] = {'checkpoint_restored_scene_empty_of_tree':  not [o for o in bpy.data.objects if o.name.startswith('Tree_')]}
except Exception:
    import traceback
    report['driver_error'] = traceback.format_exc()
Path(os.environ['AMERIKA_TEST_REPORT']).write_text(json.dumps(report, default=str))
'''


if __name__ == '__main__':
    unittest.main()
