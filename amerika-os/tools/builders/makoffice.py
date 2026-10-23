"""mak-office: Mak Office, an AltStack LLC product, packaged from the Euro-Office Desktop Editors (AGPL-3.0, arm64).

The upstream binaries are used UNMODIFIED and keep their licence and notices; we add our own launcher entries, icon and a
source offer. amerika-office becomes a transitional package that pulls mak-office in."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

LOCK = 'euro-office.lock.json'


def register(b):
    def fetch(lock):
        cache = Path(os.environ.get('AMERIKA_MAKOFFICE_CACHE', b.ROOT.parent / 'makos-cache')) / 'eo.deb'
        cache.parent.mkdir(parents=True, exist_ok=True)

        def ok():
            if not cache.exists():
                return False
            h = hashlib.sha256()
            with open(cache, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
            return h.hexdigest() == lock['sha256']
        if not ok():
            urllib.request.urlretrieve(lock['url'], cache)
            if not ok():
                cache.unlink(missing_ok=True)
                raise RuntimeError('the downloaded Euro-Office package does not match the pinned SHA-256')
        return cache

    def mak_office():
        src = b.OS / 'makoffice'
        lock = json.loads((src / LOCK).read_text())
        deb = fetch(lock)
        p = b.Pkg('mak-office', '0.3.0-1',
                  'Mak Office, an AltStack LLC product\nDocument, spreadsheet, presentation and PDF editors that work offline. Built on the '
                  'Euro-Office Desktop Editors (AGPL-3.0); the upstream program is included unmodified with its licence and notices.',
                  arch='arm64', title='Mak Office', category='Office',
                  depends='x11-common, libasound2t64 | libasound2, curl | wget, desktop-file-utils, gstreamer1.0-libav, gstreamer1.0-plugins-ugly, '
                          'libxss1, libatk1.0-0t64 | libatk1.0-0, libgtk-3-0t64 | libgtk-3-0, libcairo2, libstdc++6, libxkbcommon-x11-0, libnotify4, '
                          'fonts-dejavu-core, fonts-liberation, fonts-crosextra-carlito, xdg-utils',
                  recommends='fonts-takao-gothic', provides='euro-office-euro-office',
                  conflicts='euro-office-euro-office, euro-office-euro-office-enterprise',
                  homepage='https://github.com/Euro-Office/DesktopEditors')
        p.zopt = ['-Zxz', '-z6']  # the upstream package is xz too: about 320 MB instead of 500 MB with zstd
        p.extra['Replaces'] = 'amerika-office (<< 0.3.0)'
        p.extra['Breaks'] = 'amerika-office (<< 0.3.0)'
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['dpkg-deb', '-x', str(deb), tmp], check=True)
            top = Path(tmp)
            for rel in ('opt/euro-office', 'usr/bin', 'usr/share/icons', 'usr/share/doc', 'usr/share/licenses'):
                if (top / rel).exists():
                    shutil.copytree(top / rel, p.path('/' + rel), symlinks=True, dirs_exist_ok=True)
            upstream = (top / 'usr/share/applications/euro-office-euro-office.desktop').read_text()
        entry = re.sub(r'^Name=.*$', 'Name=Mak Office', upstream, count=1, flags=re.M)
        entry = re.sub(r'^Comment=.*$', 'Comment=Documents, spreadsheets, presentations and PDFs (an AltStack LLC product)', entry, count=1, flags=re.M)
        entry = entry.replace('Icon=euro-office-euro-office', 'Icon=amerika-office')  # the Amerika/MakOS icon themes ship this name
        entry = entry.replace('Exec=/usr/bin/euro-office-euro-office', 'Exec=/usr/bin/euro-office-euro-office')
        p.file('/usr/share/applications/mak-office.desktop', entry)
        icon = b.icon_svg('amerika-office')
        if icon:
            p.copy(icon, '/usr/share/icons/hicolor/scalable/apps/amerika-office.svg')  # fallback outside the Amerika icon themes
        p.file('/usr/share/doc/mak-office/SOURCE.md',
               'Mak Office is an AltStack LLC product built on the Euro-Office Desktop Editors (AGPL-3.0).\n\n'
               f"Upstream release: {lock['name']} {lock['version']} ({lock['tag']}), arm64.\n"
               f"Package pinned by SHA-256 {lock['sha256']}\n\n"
               'The program in /opt/euro-office is the upstream build, unmodified. Corresponding source (AGPL-3.0 section 6):\n'
               + ''.join(f'  {u} (tag {lock["tag"]})\n' for u in lock['source'])
               + '\nAltStack LLC packaging sources: https://github.com/danecohn/amerikasocial (amerika-os/tools/builders/makoffice.py).\n'
               'Upstream licence texts: /opt/euro-office/euro-office/LICENSE.txt and /usr/share/licenses.\n'
               'Mak Office is not affiliated with or endorsed by the Euro-Office project, Ascensio System SIA or ONLYOFFICE.\n')
        p.copyright('Mak Office packaging, launcher entries and icon: Copyright AltStack LLC, GPL-3.0-only.\n'
                    'The editors (Euro-Office Desktop Editors) are AGPL-3.0-only; their copyright and licence notices are kept unchanged in\n'
                    '/opt/euro-office/euro-office/LICENSE.txt and /usr/share/licenses. See SOURCE.md for the corresponding source.\n')
        return p

    def amerika_office():
        p = b.Pkg('amerika-office', '0.3.0-1',
                  'Transitional package: Amerika Office is now Mak Office\nInstalls mak-office. This package can be removed afterwards.',
                  arch='all', depends='mak-office (>= 0.3.0-1)', section='oldlibs')
        p.copyright('Copyright AltStack LLC, GPL-3.0-only.\n')
        return p

    return {'mak-office': mak_office, 'amerika-office': amerika_office}  # overrides the old hosted-portal wrapper of the same name
