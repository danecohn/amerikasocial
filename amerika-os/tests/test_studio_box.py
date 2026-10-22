"""AmerikaBox: Node tests against BeepBox's real synth (skipped if the dev Node is missing), WAV checks read with Python's
wave module, packaging and contract checks. The WebKit rig test lives in src/os/box/test/rig/ (run via tests/rig/studio-rig.sh)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

_REAL_RUN = subprocess.run   # other test modules may monkeypatch subprocess.run and leak it; keep the real one
ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT / 'src/os/box'
NODE = next((str(p) for p in (ROOT.parent / 'tools/node/bin/node', Path(shutil.which('node') or '/nonexistent')) if p.exists()), None)


class NodeSuite(unittest.TestCase):
    out = None

    @classmethod
    def setUpClass(cls):
        if not NODE:
            raise unittest.SkipTest('node is not available (expected ../tools/node/bin/node); the AmerikaBox Node tests were NOT run')
        subprocess.run = _REAL_RUN
        cls.out = tempfile.mkdtemp(prefix='box-test-')
        env = dict(os.environ, BOX_TEST_OUT=cls.out)
        cls.proc = subprocess.run([NODE, '--test', str(BOX / 'test/tools.test.js')], capture_output=True, text=True, env=env, timeout=600)

    @classmethod
    def tearDownClass(cls):
        if cls.out:
            shutil.rmtree(cls.out, ignore_errors=True)

    def test_node_suite_passes(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout[-3000:] + self.proc.stderr[-1000:])
        self.assertRegex(self.proc.stdout, r'fail 0')

    def test_exported_wav_is_real_audio_with_the_right_length(self):
        meta = json.loads((Path(self.out) / 'boss.json').read_text())
        with wave.open(str(Path(self.out) / 'boss.wav')) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (2, 2, 48000))
            frames = w.getnframes()
            data = w.readframes(frames)
        self.assertLessEqual(abs(frames - meta['expectedFrames']), 2)
        self.assertAlmostEqual(frames / 48000, 8 * 4 * 60 / 150, delta=0.01)       # 8 bars of 4 beats at 150 bpm
        samples = memoryview(data).cast('h')
        self.assertGreater(max(abs(s) for s in samples), 1500, 'export is silent')
        per_bar = frames // 8
        for bar in range(8):                                                       # every bar carries sound
            chunk = samples[bar * per_bar * 2:(bar + 1) * per_bar * 2]
            self.assertGreater(max(abs(s) for s in chunk), 300, f'bar {bar + 1} is silent')


class Packaging(unittest.TestCase):
    def test_lock_matches_vendored_build_and_patches(self):
        lock = json.loads((BOX / 'beepbox.lock.json').read_text())
        self.assertRegex(lock['commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(lock['tarball_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(lock['license'], 'MIT')
        for rel, digest in lock['built'].items():
            self.assertEqual(hashlib.sha256((BOX / rel).read_bytes()).hexdigest(), digest, rel)
        self.assertEqual(sorted(p.name for p in (BOX / 'patches').glob('*.patch')), lock['patches'])
        self.assertFalse(list((BOX / 'app').rglob('node_modules')))
        self.assertFalse(list((BOX / 'app').rglob('*.map')))

    def test_credit_and_licences_present(self):
        self.assertIn('John Nesky', (BOX / 'LICENSE-BeepBox.md').read_text())
        notice = (BOX / 'NOTICE').read_text()
        self.assertIn('John Nesky', notice)
        self.assertIn('not affiliated', notice)
        about = (BOX / 'app/amerika/about.js').read_text()
        dialog = (BOX / 'app/amerika/app.js').read_text()
        self.assertIn('MIT License', about)
        self.assertIn('John Nesky', dialog)
        self.assertIn('not affiliated', dialog)

    def test_builder_declares_dependencies_and_ships_notices(self):
        text = (ROOT / 'tools/builders/box.py').read_text()
        self.assertIn("arch='all'", text)
        self.assertIn('amerika-studio (>=', text)
        self.assertIn('gir1.2-webkit-6.0', text)
        self.assertIn("recommends='ffmpeg'", text)
        for needle in ('LICENSE-BeepBox.md', 'NOTICE', 'John Nesky'):
            self.assertIn(needle, text)

    def test_desktop_entry_and_launcher(self):
        d = (BOX / 'applications/amerika-box.desktop').read_text()
        self.assertIn('Name=AmerikaBox', d)
        self.assertIn('Exec=amerika-box', d)
        self.assertIn('Icon=amerika-box', d)
        launcher = (BOX / 'bin/amerika-box').read_text()
        self.assertIn('amerika-studio-webview --app box', launcher)
        self.assertTrue(os.access(BOX / 'bin/amerika-box', os.X_OK))
        subprocess.run(['sh', '-n', str(BOX / 'bin/amerika-box')], check=True)

    def test_every_box_tool_in_tools_json_has_an_rpc_handler(self):
        tools = json.loads((ROOT / 'src/os/studio/tools.json').read_text())['apps']['box']['tools']
        rpc = (BOX / 'app/amerika/rpc.js').read_text()
        for t in tools:
            self.assertIn('"%s"' % t['name'], rpc, t['name'])

    def test_no_api_key_material_in_the_app(self):
        for p in (BOX / 'app/amerika').glob('*.js'):
            self.assertNotRegex(p.read_text(), r'sk-ant-|x-api-key|anthropic-version', p.name)


class OggHelper(unittest.TestCase):
    def setUp(self):
        subprocess.run = _REAL_RUN
        self.tmp = Path(tempfile.mkdtemp(prefix='box-ogg-'))
        (self.tmp / 'exports/.jobs').mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self):
        import importlib.machinery
        import importlib.util
        os.environ['AMERIKA_BOX_PROJECT'] = str(self.tmp)
        loader = importlib.machinery.SourceFileLoader('box_ogg', str(BOX / 'bin/amerika-box-ogg'))
        spec = importlib.util.spec_from_loader('box_ogg', loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod

    def test_confinement(self):
        m = self.load()
        for bad in ('/etc/passwd', '../x', 'a/../../x', '~/x', ''):
            with self.assertRaises(ValueError):
                m.confined(bad)
        self.assertEqual(m.confined('exports/a.wav'), (self.tmp / 'exports/a.wav').resolve())

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg not installed')
    def test_job_converts_wav_to_ogg_with_loop_tags(self):
        m = self.load()
        wav = self.tmp / 'exports/t.wav'
        with wave.open(str(wav), 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b'\x10\x20' * 2 * 44100)
        job = self.tmp / 'exports/.jobs/j1.job.json'
        job.write_text(json.dumps({'wav': 'exports/t.wav', 'ogg': 'exports/t.ogg', 'loop_start': 1000, 'loop_length': 40000}))
        m.handle(job)
        res = json.loads((self.tmp / 'exports/.jobs/j1.result.json').read_text())
        if not res['ok'] and 'libvorbis' in res.get('error', '') + 'x' and 'Unknown encoder' in res.get('error', ''):
            self.skipTest('ffmpeg without libvorbis')
        self.assertTrue(res['ok'], res)
        self.assertGreater((self.tmp / 'exports/t.ogg').stat().st_size, 100)
        job2 = self.tmp / 'exports/.jobs/j2.job.json'
        job2.write_text(json.dumps({'wav': '/etc/passwd', 'ogg': 'exports/x.ogg'}))
        m.handle(job2)
        self.assertFalse(json.loads((self.tmp / 'exports/.jobs/j2.result.json').read_text())['ok'])


if __name__ == '__main__':
    unittest.main()
