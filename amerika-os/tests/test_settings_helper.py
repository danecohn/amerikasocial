"""Privilege and argument guards; every write and subprocess is a test fixture."""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
loader=importlib.machinery.SourceFileLoader('amerika_settings_helper',str(ROOT/'src/os/settings-helper/amerika-settings-helper'))
spec=importlib.util.spec_from_loader(loader.name,loader)
helper=importlib.util.module_from_spec(spec);loader.exec_module(helper)


class SettingsHelper(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        patch=mock.patch.object(helper,'ROOT',self.root);patch.start();self.addCleanup(patch.stop)
        for directory in ('etc/X11','etc/systemd/system','sys/class/power_supply/BAT0'):
            (self.root/directory).mkdir(parents=True)

    def test_environment_cannot_bypass_root_guard(self):
        with mock.patch.dict(os.environ,{'AMERIKA_SETTINGS_ROOT':str(self.root)}),\
             mock.patch.object(helper.os,'geteuid',return_value=1000),mock.patch.object(helper,'apt') as apt:
            self.assertNotEqual(helper.main(['helper','apt-upgrade']),0)
            apt.assert_not_called()

    def test_actions_reject_extra_arguments(self):
        with mock.patch.object(helper.os,'geteuid',return_value=0),mock.patch.object(helper,'run') as run,mock.patch.object(helper,'apt') as apt:
            for action in ('firewall-status','firewall-enable','firewall-disable','apt-update','apt-upgrade'):
                self.assertNotEqual(helper.main(['helper',action,'--evil']),0)
            run.assert_not_called();apt.assert_not_called()

    def test_battery_threshold_validation_precedes_writes(self):
        node=self.root/'sys/class/power_supply/BAT0/charge_control_end_threshold';node.write_text('80')
        with mock.patch.object(helper.os,'geteuid',return_value=0):
            for value in ('49','101','80;id','-1','80\n','0x50'):
                self.assertNotEqual(helper.main(['helper','battery-threshold',value]),0)
            self.assertEqual(node.read_text(),'80')
            self.assertEqual(helper.main(['helper','battery-threshold','85']),0)
            self.assertEqual(node.read_text(),'85\n')

    def test_upgrade_restores_default_manager_after_exception(self):
        file=self.root/'etc/X11/default-display-manager';file.write_text('/usr/bin/sddm\n')
        service=self.root/'etc/systemd/system/display-manager.service';service.symlink_to('/usr/lib/systemd/system/sddm.service')
        def apt(_argv):
            file.write_text('/usr/bin/gdm3\n');service.unlink();service.symlink_to('/usr/lib/systemd/system/gdm.service')
            raise RuntimeError('fake failed upgrade')
        with mock.patch.object(helper.os,'geteuid',return_value=0),mock.patch.object(helper.subprocess,'run'),mock.patch.object(helper,'apt',side_effect=apt):
            with self.assertRaises(RuntimeError):helper.main(['helper','apt-upgrade'])
        self.assertEqual(file.read_text(),'/usr/bin/sddm\n')
        self.assertEqual(os.readlink(service),'/usr/lib/systemd/system/sddm.service')

    def test_upgrade_refuses_removals(self):
        with mock.patch.object(helper.os,'geteuid',return_value=0),mock.patch.object(helper,'apt',return_value=0) as apt:
            self.assertEqual(helper.main(['helper','apt-upgrade']),0)
        argv=apt.call_args.args[0]
        self.assertIn('--no-remove',argv);self.assertEqual(argv[-1],'upgrade')
        self.assertTrue(any(arg.startswith('Dir::Etc::Preferences=') for arg in argv))

    def test_restore_preserves_absence_and_regular_unit_files(self):
        before=helper.dm_state()
        file=self.root/'etc/X11/default-display-manager';file.write_text('new\n')
        service=self.root/'etc/systemd/system/display-manager.service';service.write_text('[Unit]\n')
        helper.restore_display_manager(before)
        self.assertFalse(file.exists());self.assertFalse(service.exists())
        service.write_text('[Unit]\nDescription=Original\n');before=helper.dm_state()
        service.write_text('[Unit]\nDescription=Changed\n');helper.restore_display_manager(before)
        self.assertEqual(service.read_text(),'[Unit]\nDescription=Original\n')


    def test_upgrade_defers_display_manager_packages_and_keeps_admin_preferences(self):
        preferences=self.root/'etc/apt/preferences';preferences.parent.mkdir(exist_ok=True)
        preferences.write_text('Package: custom\nPin: version *\nPin-Priority: 200\n')
        def apt(argv):
            filename=next(arg.split('=',1)[1] for arg in argv if arg.startswith('Dir::Etc::Preferences='))
            text=Path(filename).read_text()
            self.assertIn('sddm lightdm gdm3',text);self.assertIn('Pin-Priority: -1',text)
            self.assertIn('Package: custom',text)
            self.assertEqual(helper.ENV['NEEDRESTART_MODE'],'l')
            return 0
        with mock.patch.object(helper,'apt',side_effect=apt):self.assertEqual(helper.upgrade_preserving_manager(),0)
        self.assertIn('Package: custom',preferences.read_text())
