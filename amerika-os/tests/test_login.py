"""Tests for the login screen switch, using a fake root directory and a recording command runner."""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HELPER = Path(__file__).resolve().parent.parent / 'src/os/login/amerika-login-helper'


def load(root):
    os.environ['AMERIKA_LOGIN_ROOT'] = str(root)
    loader = importlib.machinery.SourceFileLoader('login_helper', str(HELPER))
    spec = importlib.util.spec_from_loader('login_helper', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class LoginSwitch(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        for rel, text in (('etc/X11/default-display-manager', '/usr/sbin/gdm3\n'), ('usr/share/sddm/themes/amerika/Main.qml', 'Item {}'),
                          ('usr/bin/sddm', '')):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        link = self.root / 'etc/systemd/system/display-manager.service'
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to('/lib/systemd/system/gdm3.service')
        self.mod = load(self.root)
        self.calls = []

        def runner(argv):
            self.calls.append(argv)
            if argv[:3] == ['systemctl', 'enable', '--force']:  # emulate: replace the display-manager link
                link.unlink()
                link.symlink_to('/lib/systemd/system/' + argv[3])
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        self.login = self.mod.Login(runner)

    def test_enable_switches_remembers_and_leaves_the_session_alone(self):
        status = self.login.enable()
        self.assertTrue(status['amerika_active'])
        self.assertEqual((self.root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/bin/sddm')
        self.assertIn('Current=amerika', (self.root / 'etc/sddm.conf.d/50-amerika.conf').read_text())
        self.assertIn('OnFailure=amerika-login-fallback.service', (self.root / 'etc/systemd/system/sddm.service.d/amerika-fallback.conf').read_text())
        self.assertEqual(json.loads((self.root / 'var/lib/amerika-os/login/previous.json').read_text()), {'default': '/usr/sbin/gdm3', 'unit': 'gdm3.service'})
        for call in self.calls:  # nothing is stopped, started or restarted
            self.assertNotIn(call[1], ('stop', 'start', 'restart', 'isolate', 'reboot'))

    def test_enable_twice_keeps_the_real_previous_manager(self):
        self.login.enable()
        self.login.enable()
        self.assertEqual(json.loads((self.root / 'var/lib/amerika-os/login/previous.json').read_text())['unit'], 'gdm3.service')

    def test_disable_restores_everything(self):
        self.login.enable()
        status = self.login.disable()
        self.assertFalse(status['amerika_active'])
        self.assertEqual((self.root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/sbin/gdm3')
        self.assertEqual(os.readlink(self.root / 'etc/systemd/system/display-manager.service'), '/lib/systemd/system/gdm3.service')
        self.assertFalse((self.root / 'etc/sddm.conf.d/50-amerika.conf').exists())
        self.assertFalse((self.root / 'etc/systemd/system/sddm.service.d/amerika-fallback.conf').exists())

    def test_fallback_goes_back_and_starts_the_previous_manager(self):
        self.login.enable()
        self.calls.clear()
        self.login.fallback()
        self.assertIn(['systemctl', 'start', '--no-block', 'gdm3.service'], self.calls)
        self.assertEqual((self.root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/sbin/gdm3')

    def test_enable_refuses_without_the_theme_or_sddm(self):
        (self.root / 'usr/share/sddm/themes/amerika/Main.qml').unlink()
        with self.assertRaises(SystemExit):
            self.login.enable()
        self.assertEqual((self.root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/sbin/gdm3')

    def test_failed_enable_rolls_back(self):
        def failing(argv):
            return SimpleNamespace(returncode=1 if argv[:3] == ['systemctl', 'enable', '--force'] and argv[3] == 'sddm.service' else 0, stdout='', stderr='boom')
        self.login = self.mod.Login(failing)
        with self.assertRaises(SystemExit):
            self.login.enable()
        self.assertEqual((self.root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/sbin/gdm3')
        self.assertFalse((self.root / 'etc/sddm.conf.d/50-amerika.conf').exists())

    def test_only_known_actions(self):
        self.assertEqual(self.mod.main(['x', 'rm -rf /']), 2)
        self.assertEqual(self.mod.main(['x']), 2)


if __name__ == '__main__':
    unittest.main()
