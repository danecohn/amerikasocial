"""Amerika Sprite: runs the Node logic tests, verifies exported files with PIL, checks packaging and licensing text."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPRITE = ROOT / 'src/os/sprite'
NODE = next((str(p) for p in (ROOT.parent / 'tools/node/bin/node', Path(shutil.which('node') or '/nonexistent')) if p.is_file()), None)


@unittest.skipUnless(NODE, 'node is not available (dev Node at ../tools/node/bin/node)')
class SpriteNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix='sprite-out-'))
        env = dict(os.environ, SPRITE_TEST_OUT=str(cls.out))
        child = subprocess.Popen([NODE, '--test', *sorted(str(p) for p in (SPRITE / 'test').glob('*.test.js'))],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=SPRITE)
        cls.stdout, cls.stderr = child.communicate(timeout=300)
        cls.returncode = child.returncode

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_node_suite_passes(self):
        self.assertEqual(self.returncode, 0, self.stdout[-3000:] + self.stderr[-1000:])

    def test_exports_decode_with_pil(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('PIL missing')
        out = self.out
        sheet = Image.open(out / 'sheet_h.png')
        meta = json.loads((out / 'sheet_h.json').read_text())
        self.assertEqual(sheet.size, (meta['meta']['size']['w'], meta['meta']['size']['h']))
        self.assertEqual(sheet.mode, 'RGBA')
        f = meta['frames'][2]['frame']
        self.assertEqual(sheet.getpixel((f['x'] + 2, f['y'] + 1)), (175, 20, 200, 255))
        gif = Image.open(out / 'hero_walk.gif')
        self.assertEqual(gif.n_frames, 3)
        self.assertEqual(gif.size, (16, 16))
        durations = []
        for i in range(gif.n_frames):
            gif.seek(i)
            durations.append(gif.info['duration'])
        self.assertEqual(durations, [100, 100, 150])
        self.assertEqual(gif.info.get('loop'), 0)
        gif.seek(0)
        self.assertEqual(gif.convert('RGBA').getpixel((5, 5))[3], 255)
        self.assertEqual(gif.convert('RGBA').getpixel((0, 0))[3], 0)
        apng = Image.open(out / 'hero.apng')
        self.assertEqual(apng.n_frames, 4)
        png = Image.open(out / 'frame2.png')
        self.assertEqual(png.size, (32, 32))
        x2 = Image.open(out / 'hero_x2.png')
        self.assertEqual(x2.size, (32, 8))
        tres = (out / 'hero.tres').read_text()
        self.assertTrue(tres.startswith('[gd_resource type="SpriteFrames"'))


class SpritePackagingTests(unittest.TestCase):
    def test_files_and_licensing_text(self):
        for rel in ('app/index.html', 'app/style.css', 'app/icon.svg', 'bin/amerika-sprite', 'applications/amerika-sprite.desktop', 'icons/amerika-sprite.svg'):
            self.assertTrue((SPRITE / rel).is_file(), rel)
        self.assertTrue(os.access(SPRITE / 'bin/amerika-sprite', os.X_OK))
        launcher = (SPRITE / 'bin/amerika-sprite').read_text()
        self.assertIn('amerika-studio-webview --app sprite', launcher)
        desktop = (SPRITE / 'applications/amerika-sprite.desktop').read_text()
        self.assertIn('Name=Amerika Sprite', desktop)
        self.assertIn('Icon=amerika-sprite', desktop)
        doc = (ROOT / 'docs/studio/sprite.md').read_text()
        self.assertIn('not Aseprite', doc)
        self.assertIn('import only', doc)

    def test_page_has_no_network_references_and_no_keys(self):
        import re
        for p in (SPRITE / 'app').rglob('*'):
            if p.suffix in ('.js', '.html', '.css'):
                t = p.read_text()
                self.assertFalse(re.search(r'src=["\']https?:|url\(https?:|fetch\(["\']https?:|@import', t), p.name)
                self.assertNotIn('sk-ant', t, p.name)
                self.assertNotIn('x-api-key', t.lower(), p.name)
        html = (SPRITE / 'app/index.html').read_text()
        self.assertNotIn('cdn', html.lower())

    def test_no_aseprite_writer(self):
        src = (SPRITE / 'app/js/aseprite.js').read_text()
        self.assertNotIn('write', src.lower().replace('written from', '').replace('no .aseprite writer', ''))

    def test_builder_registers_package(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('sprite_builder', ROOT / 'tools/builders/sprite.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(list(mod.register(object()).keys()), ['amerika-sprite'])
        text = (ROOT / 'tools/builders/sprite.py').read_text()
        self.assertIn('amerika-studio (>=', text)
        self.assertIn('gir1.2-webkit-6.0', text)
        self.assertIn("arch='all'", text)


if __name__ == '__main__':
    unittest.main()
