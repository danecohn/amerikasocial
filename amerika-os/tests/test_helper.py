"""Validation tests for the privileged helper. Run: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import os
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / 'src/software/amerika-software-helper'


def load():
    loader = importlib.machinery.SourceFileLoader('helper', str(HELPER))
    spec = importlib.util.spec_from_loader('helper', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Helper(unittest.TestCase):
    def setUp(self):
        self.h = load()
        self.h.catalog = lambda: {'amerika-hub', 'amerika-keyring-x', 'amerika-repo-keyring'}

    def test_rejects_unknown_and_malformed_names(self):
        for bad in ('--purge', '-y', 'amerika-hub; rm -rf /', '../x', 'Amerika-Hub', 'a', 'openssh-server', '', 'x' * 80):
            with self.assertRaises(SystemExit, msg=bad):
                self.h.checked([bad])

    def test_accepts_catalog_names(self):
        self.assertEqual(self.h.checked(['amerika-hub']), ['amerika-hub'])

    def test_limits_count(self):
        with self.assertRaises(SystemExit):
            self.h.checked([])
        with self.assertRaises(SystemExit):
            self.h.checked(['amerika-hub'] * 17)

    def test_apt_arguments_are_fixed_and_terminated(self):
        seen = []
        self.h.run = lambda argv: seen.append(argv) or 0
        self.h.guard_display_manager = lambda: None
        self.h.restore_display_manager = lambda before: None
        self.addCleanup(setattr, self.h.os, 'geteuid', self.h.os.geteuid)
        self.addCleanup(setattr, self.h.sys, 'argv', list(self.h.sys.argv))
        self.h.os.geteuid = lambda: 0
        self.h.sys.argv = ['helper', 'install', 'amerika-hub']
        with self.assertRaises(SystemExit):
            self.h.main()
        self.assertEqual(seen[0][-2:], ['--', 'amerika-hub'])
        self.assertEqual(seen[0][0], '/usr/bin/apt-get')

    def test_display_manager_is_restored(self):
        calls = []
        states = iter([('/usr/sbin/gdm3', '/lib/systemd/system/gdm.service'), ('/usr/sbin/greetd', '/lib/systemd/system/greetd.service')])
        self.h.dm_state = lambda: next(states)
        self.addCleanup(setattr, self.h.subprocess, 'run', self.h.subprocess.run)  # don't leak the fake into other tests
        self.h.subprocess.run = lambda *a, **k: calls.append(a)
        before = self.h.guard_display_manager()
        self.assertEqual(before[0], '/usr/sbin/gdm3')
        self.assertIn('/usr/bin/debconf-set-selections', calls[0][0])
        written = {}
        import builtins, io
        real_open, real_lexists, real_symlink = builtins.open, self.h.os.path.lexists, self.h.os.symlink
        self.h.os.path.lexists = lambda p: False
        self.h.os.symlink = lambda target, link: written.setdefault('link', (target, link))
        class Sink(io.StringIO):
            def close(self): written['dm'] = self.getvalue(); super().close()
        builtins.open = lambda p, mode='r', **k: Sink() if 'w' in mode else real_open(p, mode, **k)
        try:
            self.h.restore_display_manager(before)
        finally:
            builtins.open = real_open
            self.h.os.path.lexists, self.h.os.symlink = real_lexists, real_symlink
        self.assertEqual(written['dm'].strip(), '/usr/sbin/gdm3')
        self.assertEqual(written['link'][0], '/lib/systemd/system/gdm.service')

    def test_protected_package_cannot_be_removed(self):
        self.addCleanup(setattr, self.h.os, 'geteuid', self.h.os.geteuid)
        self.addCleanup(setattr, self.h.sys, 'argv', list(self.h.sys.argv))
        self.h.os.geteuid = lambda: 0
        self.h.sys.argv = ['helper', 'remove', 'amerika-repo-keyring']
        with self.assertRaises(SystemExit):
            self.h.main()

    def test_requires_root_and_known_action(self):
        self.h.os.geteuid = lambda: 1000
        self.h.sys.argv = ['helper', 'install', 'amerika-hub']
        with self.assertRaises(SystemExit):
            self.h.main()
        self.addCleanup(setattr, self.h.os, 'geteuid', self.h.os.geteuid)
        self.addCleanup(setattr, self.h.sys, 'argv', list(self.h.sys.argv))
        self.h.os.geteuid = lambda: 0
        self.h.sys.argv = ['helper', 'shell', 'amerika-hub']
        with self.assertRaises(SystemExit):
            self.h.main()


if __name__ == '__main__':
    unittest.main()
