#!/usr/bin/env python3
"""Mirror the COSMIC desktop packages from the Pop!_OS release repository.

Ubuntu 26.10 does not ship COSMIC, and its APT (sqv) rejects the Pop!_OS archive key because the key's
self-signature uses SHA-1. So APT cannot use that repository directly. This tool performs the verification
itself instead:

  1. InRelease must verify with GnuPG against the pinned System76 key (fingerprint below, which pop-os/iso
     also publishes).
  2. The Packages index must match the SHA-256 listed in the signed InRelease.
  3. Every .deb must match the SHA-256 (and size) in that Packages index.

The unmodified .deb files are stored in vendor/cosmic with a manifest. They are then re-hosted in the
Amerika repository, which is signed with the Amerika key.
"""
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BASE = 'https://apt.pop-os.org/release'
SUITE = 'resolute'
ARCH = 'arm64'
PINNED = '63C46DF0140D738961429F4E204DD8AEC33A7AFF'
ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / 'vendor/cosmic'

# Packages that Ubuntu 26.10 lacks and that the COSMIC session needs (apt-get -s install cosmic-session
# against Ubuntu 26.10 plus the Pop!_OS index selected exactly these from the Pop!_OS repository).
WANTED = ['adw-gtk3', 'appstream-data-pop', 'appstream-data-pop-icons', 'cosmic-app-library', 'cosmic-applets',
          'cosmic-bg', 'cosmic-comp', 'cosmic-edit', 'cosmic-files', 'cosmic-greeter', 'cosmic-greeter-daemon',
          'cosmic-icons', 'cosmic-idle', 'cosmic-launcher', 'cosmic-monitor', 'cosmic-notifications', 'cosmic-osd',
          'cosmic-osk', 'cosmic-panel', 'cosmic-player', 'cosmic-randr', 'cosmic-screenshot', 'cosmic-session',
          'cosmic-settings', 'cosmic-settings-daemon', 'cosmic-store', 'cosmic-term', 'cosmic-viewer',
          'cosmic-wallpapers', 'cosmic-workspaces', 'pop-fonts', 'pop-launcher', 'pop-sound-theme',
          'xdg-desktop-portal-cosmic']


def get(path):
    with urllib.request.urlopen(f'{BASE}/{path}', timeout=120) as r:
        return r.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    tmp = Path(tempfile.mkdtemp())
    env = dict(os.environ, GNUPGHOME=str(tmp / 'gnupg'))
    (tmp / 'gnupg').mkdir(mode=0o700)
    # The key comes from the pop-keyring package; trust is anchored on the pinned fingerprint, not on the download.
    packages_text = None
    inrelease = get(f'dists/{SUITE}/InRelease')
    pkgs_index_for_keyring = gzip.decompress(get(f'dists/{SUITE}/main/binary-{ARCH}/Packages.gz')).decode()
    m = re.search(r'^Package: pop-keyring\n(?:.*\n)*?Filename: (.+)$', pkgs_index_for_keyring, re.M)
    keydeb = tmp / 'pop-keyring.deb'
    keydeb.write_bytes(get(m.group(1)))
    subprocess.run(['dpkg-deb', '-x', str(keydeb), str(tmp / 'k')], check=True)
    key = tmp / 'k/usr/share/keyrings/pop-archive-keyring.gpg'
    fprs = subprocess.run(['gpg', '--show-keys', '--with-colons', str(key)], capture_output=True, text=True,
                          env=env).stdout
    if PINNED not in re.findall(r'^fpr:+([0-9A-F]{40}):', fprs, re.M):
        sys.exit('The Pop!_OS keyring does not contain the pinned signing key.')
    subprocess.run(['gpg', '--batch', '--import', str(key)], capture_output=True, env=env, check=True)
    (tmp / 'InRelease').write_bytes(inrelease)
    v = subprocess.run(['gpg', '--batch', '--status-fd', '1', '--verify', str(tmp / 'InRelease')],
                       capture_output=True, text=True, env=env)
    if f'VALIDSIG {PINNED}' not in v.stdout:
        sys.exit('InRelease signature is not valid for the pinned key:\n' + v.stdout + v.stderr)
    release = inrelease.decode()
    section = release.split('SHA256:')[1]
    want_hash = re.search(rf'^ ([0-9a-f]{{64}}) +\d+ main/binary-{ARCH}/Packages$', section, re.M).group(1)
    index = get(f'dists/{SUITE}/main/binary-{ARCH}/Packages')
    if sha256(index) != want_hash:
        sys.exit('Packages index does not match the signed InRelease.')
    stanzas = {}
    for block in index.decode().split('\n\n'):
        n = re.search(r'^Package: (.+)$', block, re.M)
        if n:
            stanzas[n.group(1)] = block
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    VENDOR.mkdir(parents=True)
    manifest = {'source': f'{BASE} {SUITE} {ARCH}', 'signing_key': PINNED, 'release_date':
                re.search(r'^Date: (.+)$', release, re.M).group(1), 'packages': {}}
    for name in WANTED:
        block = stanzas[name]
        field = lambda k: re.search(rf'^{k}: (.+)$', block, re.M).group(1)
        filename, size, digest = field('Filename'), int(field('Size')), field('SHA256')
        data = get(filename)
        if len(data) != size or sha256(data) != digest:
            sys.exit(f'{name}: downloaded file does not match the signed index.')
        out = VENDOR / Path(filename).name
        out.write_bytes(data)
        upstream = re.search(r'~([0-9a-f]{7,})$', field('Version'))
        manifest['packages'][out.name] = {'package': name, 'version': field('Version'), 'size': size,
                                          'sha256': digest, 'upstream_commit': upstream.group(1) if upstream else None,
                                          'homepage': (re.search(r'^Homepage: (.+)$', block, re.M) or [None, None])[1]}
        print('verified', out.name)
    (VENDOR / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
