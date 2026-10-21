import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HELPER = os.path.join(os.path.dirname(__file__), '..', 'src/os/boot/amerika-boot-helper')


class BootHelper(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.bin = os.path.join(self.d, 'bin')
        os.mkdir(self.bin)
        self.theme = os.path.join(self.d, 'amerika.plymouth')
        open(self.theme, 'w').close()
        self.link = os.path.join(self.d, 'link')
        open(self.link, 'w').write('/stock/bgrt.plymouth')
        self.log = os.path.join(self.d, 'log')
        fake = f'''#!/bin/sh
echo "$(basename $0) $@" >> {self.log}
case "$(basename $0)" in
  update-alternatives)
    case "$1" in
      --query) echo "Value: $(cat {self.link})";;
      --set) printf %s "$3" > {self.link};;
      --auto) printf %s /stock/bgrt.plymouth > {self.link};;
    esac;;
  update-initramfs) [ -f {self.d}/fail ] && exit 1; exit 0;;
  which) exit 0;;
esac
'''
        for n in ('update-alternatives', 'update-initramfs', 'which'):
            p = os.path.join(self.bin, n)
            open(p, 'w').write(fake)
            os.chmod(p, 0o755)
        self.env = dict(os.environ, PATH=self.bin + ':' + os.environ['PATH'], AMERIKA_BOOT_TEST='1', AMERIKA_BOOT_THEME=self.theme,
                        AMERIKA_BOOT_STATE=os.path.join(self.d, 'state'))

    def run_h(self, *a):
        return subprocess.run([sys.executable, HELPER, *a], capture_output=True, text=True, env=self.env)

    def test_enable_disable_roundtrip(self):
        self.assertFalse(json.loads(self.run_h('status').stdout)['amerika_active'])
        self.assertEqual(self.run_h('enable').returncode, 0)
        self.assertTrue(json.loads(self.run_h('status').stdout)['amerika_active'])
        self.assertEqual(self.run_h('disable').returncode, 0)
        self.assertEqual(open(self.link).read(), '/stock/bgrt.plymouth')

    def test_failed_initramfs_rolls_back(self):
        open(os.path.join(self.d, 'fail'), 'w').close()
        r = self.run_h('enable')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(open(self.link).read(), '/stock/bgrt.plymouth')

    def test_unknown_action(self):
        self.assertNotEqual(self.run_h('bogus').returncode, 0)


if __name__ == '__main__':
    unittest.main()
