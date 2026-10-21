"""Flavour package invariants, seed parsing and non-mutating ISO plan."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]


def module(path):
    spec=importlib.util.spec_from_file_location('flavor_'+path.stem,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


class Flavor(unittest.TestCase):
    def test_no_private_keys_in_flavour(self):
        for file in (ROOT/'flavor').rglob('*'):
            if file.is_file():
                data=file.read_bytes()
                self.assertNotIn(b'BEGIN PGP PRIVATE KEY',data,str(file))
                self.assertNotIn(b'BEGIN OPENSSH PRIVATE KEY',data,str(file))

    def test_seed_packages_are_valid_and_minimal_excludes_wrappers(self):
        builder=module(ROOT/'tools/builders/flavor.py')
        minimal=builder.read_seed(ROOT/'flavor/seeds/desktop-minimal')
        self.assertIn('amerika-session',minimal['Depends'])
        self.assertNotIn('amerika-office',minimal['Depends'])
        for seed in (ROOT/'flavor/seeds').iterdir():
            if seed.name!='STRUCTURE':builder.read_seed(seed)

    def test_defaults_do_not_switch_boot_or_login(self):
        source=(ROOT/'tools/builders/flavor.py').read_text()
        for forbidden in ('update-initramfs','grub-install','systemctl enable','amerika-login enable'):
            self.assertNotIn(forbidden,source)
        self.assertIn('Enabled: no',(ROOT/'flavor/updates/amerika-testing.sources').read_text())

    def test_iso_plan_requires_signed_repository_and_does_not_write(self):
        iso=module(ROOT/'tools/build-iso.py')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);repo=base/'repo';out=base/'out';repo.mkdir()
            with self.assertRaises(ValueError):iso.plan(repo,out)
            (repo/'dists/stable').mkdir(parents=True)
            (repo/'dists/stable/InRelease').write_text('fake fixture')
            (repo/'amerika-archive-keyring.gpg').write_bytes(b'public fake fixture')
            (repo/'manifest.json').write_text(json.dumps({'fingerprint':'FAKE'}))
            plan=iso.plan(repo,out)
            self.assertEqual(plan['architecture'],'arm64');self.assertFalse(out.exists())
            self.assertIn('--apt-secure',plan['commands'][0]);self.assertNotIn('trusted=yes',json.dumps(plan))
