import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src/os/hw'))
from amerika_hw import report, tune

TUNING = os.path.join(os.path.dirname(__file__), '..', 'src/os/hw/tuning')


def wr(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w').write(text)


class FakeSys(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.sys = os.path.join(self.d, 'sys')
        for i in range(2):
            p = f'{self.sys}/devices/system/cpu/cpufreq/policy{i}'
            wr(p + '/scaling_governor', 'schedutil\n')
            wr(p + '/scaling_available_governors', 'performance schedutil powersave\n')
        g = f'{self.sys}/class/devfreq/3d00000.gpu'
        wr(g + '/governor', 'simple_ondemand\n')
        wr(g + '/available_governors', 'simple_ondemand performance\n')
        wr(g + '/min_freq', '300000000\n')
        wr(g + '/max_freq', '1250000000\n')
        wr(g + '/cur_freq', '550000000\n')
        self.state = os.path.join(self.d, 'state')

    def val(self, rel):
        return open(os.path.join(self.sys, rel)).read().strip()


class PerfTests(FakeSys):
    def test_game_then_balanced_restores_everything(self):
        tune.perf('game', self.sys, self.state)
        self.assertEqual(self.val('devices/system/cpu/cpufreq/policy0/scaling_governor'), 'performance')
        self.assertEqual(self.val('class/devfreq/3d00000.gpu/governor'), 'performance')
        tune.perf('game', self.sys, self.state)  # twice must not overwrite the saved originals
        tune.perf('balanced', self.sys, self.state)
        self.assertEqual(self.val('devices/system/cpu/cpufreq/policy1/scaling_governor'), 'schedutil')
        self.assertEqual(self.val('class/devfreq/3d00000.gpu/governor'), 'simple_ondemand')
        self.assertEqual(self.val('class/devfreq/3d00000.gpu/min_freq'), '300000000')

    def test_gpu_without_performance_governor_pins_min_clock(self):
        wr(f'{self.sys}/class/devfreq/3d00000.gpu/available_governors', 'simple_ondemand\n')
        tune.perf('game', self.sys, self.state)
        self.assertEqual(self.val('class/devfreq/3d00000.gpu/min_freq'), '1250000000')
        tune.perf('balanced', self.sys, self.state)
        self.assertEqual(self.val('class/devfreq/3d00000.gpu/min_freq'), '300000000')

    def test_bad_mode(self):
        with self.assertRaises(ValueError):
            tune.perf('turbo', self.sys, self.state)

    def test_gpu_report(self):
        g = report.gpu(self.sys)
        self.assertEqual(g['devfreq']['max_mhz'], 1250)
        self.assertEqual(g['devfreq']['governor'], 'simple_ondemand')


class TuneFilesTests(unittest.TestCase):
    def test_apply_revert_roundtrip(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        files = {n: os.path.join(d, 'etc', n) for n in os.listdir(TUNING)}
        done = tune.apply(TUNING, files, run=False)
        self.assertEqual(len(done), len(files))
        self.assertEqual(len(tune.revert(files, run=False)), len(files))
        self.assertFalse(any(os.path.exists(f) for f in files.values()))

    def test_all_tuning_targets_have_a_source_file(self):
        self.assertEqual(set(tune.FILES), set(os.listdir(TUNING)))

    def test_sysctl_file_is_well_formed(self):
        for line in open(os.path.join(TUNING, '60-amerika-gamedev.conf')):
            line = line.strip()
            if line and not line.startswith('#'):
                key, _, val = line.partition('=')
                self.assertRegex(key.strip(), r'^[a-z_.\-]+$')
                self.assertRegex(val.strip(), r'^\d+$')


class NpuTests(unittest.TestCase):
    def test_honest_about_graphics(self):
        n = report.npu()
        self.assertIn('usable_for_inference', n)
        if n['device_nodes'] and not n['usable_for_inference']:
            self.assertIn('cannot speed up graphics', n['note'])


class ReportTests(unittest.TestCase):
    def test_build_has_every_section_and_text(self):
        r = report.build()
        for k in ('cpu', 'memory', 'gpu', 'npu', 'thermal', 'power', 'storage', 'limits', 'tools', 'advice'):
            self.assertIn(k, r)
        json.dumps(r)
        self.assertIn('CPU', report.text(r))

    def test_advice_rules(self):
        r = {'memory': {'total_mb': 16000}, 'limits': {'inotify_watches': 65536}, 'gpu': {'hardware_accelerated': False, 'devfreq': None},
             'tools': {'gcc': False}}
        tips = ' '.join(report.advice(r))
        for word in ('RAM', 'File-watch', 'software Vulkan', 'C compiler'):
            self.assertIn(word, tips)


if __name__ == '__main__':
    unittest.main()
