#!/usr/bin/env python3
"""Build the Amerika OS Debian packages and the signed APT repository.

    build.py [--only name,name] [--sign-only]

Inputs: ./src and the verified application archives (see APP_ARCHIVES).
Outputs: ./dist/packages/*.deb and ./dist/apt (the repository tree that Amerika
Social serves at https://www.amerika.social/apt).

The repository signing key lives in $AMERIKA_SIGNING_HOME (default
~/.local/share/amerika-os-signing), never inside this tree. Create it once with
`build.py --init-key`.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
DIST = ROOT / 'dist'
STAGE = DIST / 'stage'
PKG_DIR = DIST / 'packages'
APT_DIR = DIST / 'apt'
OUTPUTS = Path(os.environ.get('AMERIKA_OUTPUTS', ROOT.parent.parent / 'outputs'))
SIGN_HOME = Path(os.environ.get('AMERIKA_SIGNING_HOME', Path.home() / '.local/share/amerika-os-signing'))
KEY_NAME = 'Amerika OS Archive Signing Key'
ARCH = 'arm64'
SUITE = 'stable'
DE_VERSION = '3.0.2'
MAINTAINER = 'Amerika LLC <noreply@amerika.social>'
HOMEPAGE = 'https://www.amerika.social/downloads/os'
SYSTEM_SHELL = Path('/usr/share/plasma/shells/org.kde.plasma.desktop')
OS = SRC / 'os'
BG_DIR = '/usr/share/backgrounds/amerika'
THEME_OUT = OUTPUTS / 'Amerika-OS-theme'
BASE_URL = 'https://www.amerika.social/apt'

APP_ARCHIVES = {
    'social': ('AmerikaSocial-Linux-ARM64.tar.gz', None),
    'venture': ('AmerikaVenture-linux-arm64.tar.gz', 'AmerikaVenture-linux-arm64.tar.gz.sha256'),
    'office': ('AmerikaOffice-linux-arm64.tar.gz', 'AmerikaOffice-linux-arm64.tar.gz.sha256'),
}


def sh(*args, **kw):
    kw.setdefault('check', True)
    return subprocess.run([str(a) for a in args], **kw)


def write(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def copy(src, dst, mode=None):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if mode is not None:
        dst.chmod(mode)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


class Pkg:
    def __init__(self, name, version, description, arch='all', depends='', title=None, category='System',
                 section='x11', homepage=HOMEPAGE, extra=None, recommends='', provides='', conflicts=''):
        self.name, self.version, self.arch = name, version, arch
        self.description, self.depends, self.title, self.category = description, depends, title, category
        self.section, self.homepage, self.extra = section, homepage, extra or {}
        self.recommends, self.provides, self.conflicts = recommends, provides, conflicts
        self.root = STAGE / name
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self.scripts = {}

    def path(self, p):
        return self.root / str(p).lstrip('/')

    def file(self, dest, text, mode=0o644):
        write(self.path(dest), text, mode)

    def copy(self, src, dest, mode=None):
        copy(src, self.path(dest), mode)

    def copyright(self, text):
        self.file(f'/usr/share/doc/{self.name}/copyright', text)

    def build(self):
        size = sum(f.stat().st_size for f in self.root.rglob('*') if f.is_file()) // 1024
        lines = [f'Package: {self.name}', f'Version: {self.version}', f'Architecture: {self.arch}',
                 f'Maintainer: {MAINTAINER}', f'Installed-Size: {size}', f'Section: {self.section}',
                 'Priority: optional', f'Homepage: {self.homepage}']
        for key, val in (('Depends', self.depends), ('Recommends', self.recommends), ('Provides', self.provides),
                         ('Conflicts', self.conflicts)):
            if val:
                lines.append(f'{key}: {val}')
        if self.title:
            lines.append(f'Amerika-Title: {self.title}')
        lines.append(f'Amerika-Category: {self.category}')
        for k, v in self.extra.items():
            lines.append(f'{k}: {v}')
        desc = self.description.strip().split('\n')
        lines.append('Description: ' + desc[0])
        for extra in desc[1:]:
            lines.append(' ' + (extra.strip() or '.'))
        write(self.root / 'DEBIAN/control', '\n'.join(lines) + '\n')
        for name, text in self.scripts.items():
            write(self.root / 'DEBIAN' / name, text, 0o755)
        # md5sums for dpkg --verify
        sums = []
        for f in sorted(self.root.rglob('*')):
            if f.is_file() and not f.is_symlink() and 'DEBIAN' not in f.relative_to(self.root).parts:
                h = hashlib.md5(f.read_bytes()).hexdigest()
                sums.append(f'{h}  {f.relative_to(self.root)}')
        write(self.root / 'DEBIAN/md5sums', '\n'.join(sums) + '\n')
        PKG_DIR.mkdir(parents=True, exist_ok=True)
        out = PKG_DIR / f'{self.name}_{self.version}_{self.arch}.deb'
        out.unlink(missing_ok=True)
        zopt = ['-Zzstd', '-z10'] if size > 20000 else ['-Zxz', '-z6']
        sh('dpkg-deb', '--root-owner-group', *zopt, '--build', self.root, out, stdout=subprocess.DEVNULL)
        return out


def shlib_depends(root):
    """Debian packages providing the shared libraries that ELF files under root need."""
    needed, bundled = set(), set()
    elfs = []
    for f in root.rglob('*'):
        if f.is_file() and not f.is_symlink():
            bundled.add(f.name)
            with open(f, 'rb') as h:
                if h.read(4) == b'\x7fELF':
                    elfs.append(f)
    for f in elfs:
        out = sh('readelf', '-d', f, capture_output=True, text=True, check=False).stdout
        needed.update(re.findall(r'\(NEEDED\)\s+Shared library: \[(.+?)\]', out))
    needed -= bundled
    pkgs = set()
    libdirs = ['/usr/lib/aarch64-linux-gnu', '/lib/aarch64-linux-gnu', '/usr/lib', '/lib']
    for lib in sorted(needed):
        for d in libdirs:
            p = Path(d) / lib
            if p.exists():
                real = os.path.realpath(p)
                r = sh('dpkg', '-S', real, capture_output=True, text=True, check=False)
                if r.returncode != 0:
                    r = sh('dpkg', '-S', str(p), capture_output=True, text=True, check=False)
                if r.returncode == 0:
                    pkgs.add(r.stdout.split(':')[0].strip())
                    break
    return sorted(pkgs)


def app_archive(key):
    name, sidecar = APP_ARCHIVES[key]
    path = OUTPUTS / name
    if sidecar:
        want = (OUTPUTS / sidecar).read_text().split()[0]
        if sha256(path) != want:
            sys.exit(f'{name} does not match its published SHA-256.')
    return path


def extract(archive, dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(archive) as t:
        t.extractall(dest, filter='tar')
    entries = [p for p in dest.iterdir()]
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else dest


def icon_svg(name):
    p = OS / 'icons/AmerikaOS/scalable/apps' / f'{name}.svg'
    return p if p.exists() else None


def desktop_file(pkg, text, name):
    pkg.file(f'/usr/share/applications/{name}.desktop', text)


# --------------------------------------------------------------------------- packages

def build_keyring():
    p = Pkg('amerika-repo-keyring', DE_VERSION, 'Amerika OS package repository signing key and APT source\n'
            'Installs the signing key and the APT source for https://www.amerika.social/apt.',
            title='Amerika Repository', category='System', section='misc')
    key = APT_DIR / 'amerika-archive-keyring.gpg'
    if not key.exists():
        sys.exit('Run --init-key and --sign-only first so the public key exists.')
    p.copy(key, '/usr/share/keyrings/amerika-archive-keyring.gpg')
    p.file('/etc/apt/sources.list.d/amerika.sources',
           f'Types: deb\nURIs: {BASE_URL}\nSuites: {SUITE}\nComponents: main\nArchitectures: {ARCH}\n'
           'Signed-By: /usr/share/keyrings/amerika-archive-keyring.gpg\n')
    p.file('/etc/apt/apt.conf.d/50amerika-social',
           '// The edge proxy in front of www.amerika.social rejects pipelined HTTP requests, which APT uses by default.\n'
           'Acquire::http::www.amerika.social::Pipeline-Depth "0";\n'
           'Acquire::https::www.amerika.social::Pipeline-Depth "0";\n')
    p.copyright('Amerika OS repository key and APT source.\nCopyright Amerika LLC. Licensed GPL-3.0-only.\n'
                'See /usr/share/common-licenses/GPL-3.\n')
    return p


def build_icons():
    p = Pkg('amerika-icon-theme', DE_VERSION, 'Amerika OS icon theme\nRetro-futurist neon cartridge app icons and panel icons.',
            depends='adwaita-icon-theme', title='Amerika Icons', category='Appearance', section='gnome')
    shutil.copytree(OS / 'icons/AmerikaOS', p.path('/usr/share/icons/AmerikaOS'))
    p.scripts['postinst'] = ('#!/bin/sh\nset -e\nif [ "$1" = configure ] && command -v gtk-update-icon-cache >/dev/null;'
                             ' then gtk-update-icon-cache -q -f /usr/share/icons/AmerikaOS || true; fi\nexit 0\n')
    p.copyright('Icon theme generated for Amerika OS by Amerika LLC (tools/make_icons.py); GPL-3.0-only.\n'
                'The icons named claude-desktop and chatgpt are generic stand-ins in the Amerika style; they are not\n'
                'the logos of Anthropic or OpenAI, whose applications keep their own window icons.\n')
    return p


def build_theme():
    p = Pkg('amerika-theme', DE_VERSION, 'Amerika OS theme\nRetro-futurist wallpapers and the Amerika Retro colour scheme.',
            title='Amerika Theme', category='Appearance')
    for name in ('horizon', 'grid', 'dusk'):
        p.copy(OS / f'wallpapers/{name}.png', f'{BG_DIR}/{name}.png')
    p.copy(OS / 'color-schemes/AmerikaRetro.colors', '/usr/share/color-schemes/AmerikaRetro.colors')
    p.copyright('Amerika OS theme, Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


def build_shell():
    deps = ['python3 (>= 3.11)', 'python3-gi', 'gir1.2-gtk-4.0', 'gir1.2-gtk4layershell-1.0', 'libgtk4-layer-shell0',
            'gir1.2-polkit-1.0', 'gir1.2-nm-1.0', 'kwin-wayland', 'kglobalacceld', 'polkit-kde-agent-1',
            'libkscreen-bin', 'libkf6config-bin', 'libkscreenlocker6', 'plasma-desktop-data', 'wireplumber', 'pipewire-pulse', 'network-manager', 'power-profiles-daemon',
            'upower', 'systemd', 'xdg-desktop-portal-gtk', 'fonts-inter', 'fonts-jetbrains-mono', 'librsvg2-common',
            f'amerika-icon-theme (>= {DE_VERSION})', f'amerika-theme (>= {DE_VERSION})']
    p = Pkg('amerika-desktop-shell', DE_VERSION,
            'Amerika Shell and Settings\nAmerika OS\'s own desktop shell (top bar, dock, launcher, notifications), its settings app, and the '
            'system-control server\nthat lets the Claude and ChatGPT apps operate the computer under your supervision.',
            depends=', '.join(deps), recommends='nautilus, ptyxis, gnome-text-editor', title='Amerika Shell')
    pkg_dir = '/usr/lib/python3/dist-packages/amerika'
    shutil.copytree(OS / 'amerika', p.path(pkg_dir), ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'bridge'))
    p.copy(OS / 'amerika/bridge/bridge.js', '/usr/share/amerika-os/bridge/bridge.js')
    for name in ('amerika-shell', 'amerika-settings', 'amerika-mcp', 'amerika-first-run'):
        p.copy(OS / 'bin' / name, f'/usr/bin/{name}', 0o755)
    p.copy(OS / 'applications/org.amerika.Shell.desktop', '/usr/share/applications/org.amerika.Shell.desktop')
    p.copyright('Amerika Shell, Copyright Amerika LLC, GPL-3.0-only.\nUses GTK 4, gtk4-layer-shell and KWin (as the compositor) '
                'under their own licenses.\n')
    return p


def build_session():
    p = Pkg('amerika-session', DE_VERSION, 'Amerika OS login session\nAdds "Amerika OS" to the login screen. KWin runs as the compositor; '
            'everything else is Amerika\'s own shell.\nOther sessions are not changed.',
            depends=f'amerika-desktop-shell (>= {DE_VERSION}), kwin-wayland', title='Amerika Session')
    p.copy(OS / 'session/amerika-session', '/usr/bin/amerika-session', 0o755)
    p.copy(OS / 'session/session-start', '/usr/libexec/amerika/session-start', 0o755)
    p.copy(OS / 'session/amerika-restore-meta', '/usr/libexec/amerika/amerika-restore-meta', 0o755)
    p.copy(OS / 'session/amerika-xkb-override', '/usr/libexec/amerika/amerika-xkb-override', 0o755)
    p.copy(OS / 'session/50-amerika-restore-meta.sh', '/etc/xdg/plasma-workspace/env/50-amerika-restore-meta.sh')
    p.copy(OS / 'session/amerika.desktop', '/usr/share/wayland-sessions/amerika.desktop')
    p.copyright('Amerika OS session files, Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


def build_apps():
    p = Pkg('amerika-apps', DE_VERSION, 'Amerika core apps\nAmerika Files, Terminal, Text and Settings launchers. Files, Terminal and Text are '
            'Amerika-branded launchers\nfor GNOME Files (Nautilus), Ptyxis and GNOME Text Editor, which stay installed and unmodified.',
            depends=f'nautilus, ptyxis, gnome-text-editor, amerika-desktop-shell (>= {DE_VERSION}), amerika-icon-theme (>= {DE_VERSION})',
            title='Amerika Core Apps')
    for name in ('amerika-files', 'amerika-terminal', 'amerika-text', 'amerika-settings'):
        p.copy(OS / f'applications/{name}.desktop', f'/usr/share/applications/{name}.desktop')
    p.copyright('Launchers, Copyright Amerika LLC, GPL-3.0-only.\nNautilus, Ptyxis and GNOME Text Editor are separate GNOME packages with '
                'their own licenses (GPL-3.0-or-later).\n')
    return p


def build_software():
    p = Pkg('amerika-software', DE_VERSION, 'Amerika Software\nGraphical manager for the Amerika package repository: '
            'install, update and remove Amerika apps.', depends='python3-pyqt6, python3-apt, pkexec, apt, amerika-repo-keyring, '
            'amerika-icon-theme', title='Amerika Software')
    p.copy(SRC / 'software/amerika-software', '/usr/bin/amerika-software', 0o755)
    p.copy(SRC / 'software/amerika-software-helper', '/usr/libexec/amerika-software-helper', 0o755)
    p.copy(SRC / 'software/org.amerika.software.policy', '/usr/share/polkit-1/actions/org.amerika.software.policy')
    p.copy(SRC / 'software/amerika-software.desktop', '/usr/share/applications/amerika-software.desktop')
    p.copyright('Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


def build_social():
    root = extract(app_archive('social'), STAGE / '_payload-social')
    p = Pkg('amerika-social', '1.0.0-1', 'Amerika Social native app\nThe native desktop client for Amerika Social.',
            arch=ARCH, title='Amerika Social', category='Social')
    shutil.copytree(root, p.path('/opt/amerika/social'), symlinks=True, ignore=shutil.ignore_patterns(
        'install-linux.sh', 'amerika-social.desktop'))
    p.path('/opt/amerika/social/AmerikaSocial').chmod(0o755)
    p.file('/usr/bin/amerika-social', '#!/bin/sh\nexec /opt/amerika/social/AmerikaSocial "$@"\n', 0o755)
    p.depends = ', '.join(shlib_depends(p.root / 'opt/amerika/social') or ['libc6'])
    desktop_file(p, '[Desktop Entry]\nName=Amerika Social\nComment=Why Can\'t We Be Friends?\nType=Application\n'
                 'Exec=/usr/bin/amerika-social\nIcon=amerika-social\nTerminal=false\n'
                 'Categories=Network;InstantMessaging;\nStartupWMClass=AmerikaSocial\n', 'amerika-social')
    if icon_svg('amerika-social'):
        p.copy(icon_svg('amerika-social'), '/usr/share/icons/hicolor/scalable/apps/amerika-social.svg')
    p.copyright('Amerika Social desktop, Copyright Amerika LLC, GPL-3.0-only.\n'
                'Source: https://github.com/danecohn/AmerikaLinux\n'
                'The bundle in /opt/amerika/social/_internal contains Python, Qt/PySide6 and other third-party\n'
                'components under their own licenses; see THIRD-PARTY-NOTICES in that directory when present.\n')
    return p


def build_venture():
    root = extract(app_archive('venture'), STAGE / '_payload-venture')
    p = Pkg('amerika-venture', '158.0.1-amerika1', 'Amerika Venture browser\nAmerika LLC browser distribution based on '
            'Mozilla Firefox 158.0.1 with Amerika branding. Updates arrive\nthrough this repository.',
            arch=ARCH, title='Amerika Venture', category='Internet',
            provides='www-browser', homepage='https://www.amerika.social/downloads/venture')
    shutil.copytree(root, p.path('/opt/amerika/venture'), symlinks=True, ignore=shutil.ignore_patterns('install-linux.sh'))
    for exe in ('AmerikaVenture', 'firefox', 'firefox-bin', 'glxtest', 'vaapitest', 'pingsender', 'crashhelper'):
        f = p.path(f'/opt/amerika/venture/{exe}')
        if f.exists() and not f.is_symlink():
            f.chmod(0o755)
    p.file('/usr/bin/amerika-venture', '#!/bin/sh\nexec /opt/amerika/venture/AmerikaVenture "$@"\n', 0o755)
    p.depends = ', '.join(shlib_depends(p.root / 'opt/amerika/venture') or ['libc6'])
    desktop_file(p, '[Desktop Entry]\nType=Application\nName=Amerika Venture\nGenericName=Web Browser\n'
                 'Comment=Amerika LLC browser based on Firefox\nExec=/usr/bin/amerika-venture %u\nIcon=amerika-venture\n'
                 'Terminal=false\nCategories=Network;WebBrowser;\nMimeType=text/html;x-scheme-handler/http;'
                 'x-scheme-handler/https;\nStartupNotify=true\nStartupWMClass=AmerikaVenture\n', 'amerika-venture')
    if icon_svg('amerika-venture'):
        p.copy(icon_svg('amerika-venture'), '/usr/share/icons/hicolor/scalable/apps/amerika-venture.svg')
    p.scripts['postinst'] = ('#!/bin/sh\nset -e\nif [ "$1" = configure ]; then\n'
                             ' update-alternatives --install /usr/bin/x-www-browser x-www-browser '
                             '/usr/bin/amerika-venture 40 || true\nfi\nexit 0\n')
    p.scripts['prerm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ]; then\n'
                          ' update-alternatives --remove x-www-browser /usr/bin/amerika-venture || true\nfi\nexit 0\n')
    p.copyright('Amerika Venture is a distribution of Mozilla Firefox 158.0.1 with Amerika branding, start page\n'
                'and settings. Firefox is copyright Mozilla and contributors under the Mozilla Public License 2.0\n'
                '(see /opt/amerika/venture/AMERIKA-LICENSE.txt). Modifications and source provenance:\n'
                'https://github.com/danecohn/AmerikaVenture and /opt/amerika/venture/AMERIKA-SOURCE.json.\n'
                'This is not a full rebuild of Gecko. Mozilla automatic app updates are disabled; updates come from\n'
                'this repository. Packages are unsigned by Mozilla and macOS-style notarization does not apply.\n')
    return p


def build_office():
    root = extract(app_archive('office'), STAGE / '_payload-office')
    p = Pkg('amerika-office', '0.1.0-1', 'Amerika Office desktop\nDesktop app for the hosted Amerika Office portal '
            '(documents, spreadsheets and presentations).\nIt connects to the hosted portal and is not an offline '
            'office suite. The editor is ONLYOFFICE Community Edition.',
            arch=ARCH, title='Amerika Office', category='Office',
            homepage='https://www.amerika.social/downloads/office')
    shutil.copytree(root, p.path('/opt/amerika/office'), symlinks=True, ignore=shutil.ignore_patterns('install-linux.sh'))
    p.path('/opt/amerika/office/amerika-office').chmod(0o755)
    p.path('/opt/amerika/office/chrome_crashpad_handler').chmod(0o755)
    p.path('/opt/amerika/office/chrome-sandbox').chmod(0o4755)
    p.file('/usr/bin/amerika-office', '#!/bin/sh\nexec /opt/amerika/office/amerika-office "$@"\n', 0o755)
    p.depends = ', '.join(shlib_depends(p.root / 'opt/amerika/office') or ['libc6'])
    desktop_file(p, '[Desktop Entry]\nType=Application\nName=Amerika Office\nComment=Amerika LLC collaborative office\n'
                 'Exec=/usr/bin/amerika-office %U\nIcon=amerika-office\nTerminal=false\nCategories=Office;\n'
                 'StartupWMClass=amerika-office\n', 'amerika-office')
    if icon_svg('amerika-office'):
        p.copy(icon_svg('amerika-office'), '/usr/share/icons/hicolor/scalable/apps/amerika-office.svg')
    p.copyright('Amerika Office desktop, Copyright Amerika LLC. Source: https://github.com/danecohn/AmerikaOffice\n'
                'Built on Electron (MIT, /opt/amerika/office/LICENSE.electron.txt) and Chromium\n'
                '(/opt/amerika/office/LICENSES.chromium.html). The hosted editor is ONLYOFFICE Community Edition\n'
                '(AGPL-3.0); its branding and notices are intentionally retained.\n')
    return p


def build_meta():
    ours = ('amerika-session', 'amerika-desktop-shell', 'amerika-theme', 'amerika-icon-theme', 'amerika-apps', 'amerika-software',
            'amerika-repo-keyring')
    p = Pkg('amerika-desktop', DE_VERSION, 'Amerika OS desktop environment\nAmerika OS: its own shell on the KWin compositor, with the Claude and '
            'ChatGPT apps at the centre.\nInstalls the session, shell, settings, theme, apps and the Amerika Software manager.',
            depends=', '.join(f'{n} (>= {DE_VERSION})' for n in ours) + ', amerika-social, amerika-venture, amerika-office',
            arch=ARCH, title='Amerika OS Desktop', section='metapackages')
    p.copyright('Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


BUILDERS = {
    'amerika-repo-keyring': build_keyring, 'amerika-icon-theme': build_icons, 'amerika-theme': build_theme,
    'amerika-desktop-shell': build_shell, 'amerika-session': build_session, 'amerika-apps': build_apps,
    'amerika-software': build_software, 'amerika-social': build_social, 'amerika-venture': build_venture,
    'amerika-office': build_office, 'amerika-desktop': build_meta,
}

# --------------------------------------------------------------------------- repository


def gpg(*args, **kw):
    env = dict(os.environ, GNUPGHOME=str(SIGN_HOME))
    return sh('gpg', '--batch', '--yes', '--no-tty', *args, env=env, **kw)


def init_key():
    if (SIGN_HOME / 'private-keys-v1.d').exists() and gpg('--list-secret-keys', KEY_NAME, capture_output=True,
                                                          check=False).returncode == 0:
        print('Signing key already exists.')
        return
    SIGN_HOME.mkdir(parents=True, exist_ok=True)
    SIGN_HOME.chmod(0o700)
    gpg('--passphrase', '', '--pinentry-mode', 'loopback', '--quick-generate-key', KEY_NAME, 'ed25519', 'sign', '5y')
    print('Created signing key in', SIGN_HOME)


def deb_fields(deb):
    return sh('dpkg-deb', '-f', deb, capture_output=True, text=True).stdout.strip()


def make_repo(debs):
    if APT_DIR.exists():
        shutil.rmtree(APT_DIR)
    entries = []
    for deb in sorted(debs):
        fields = deb_fields(deb)
        name = re.search(r'^Package: (.+)$', fields, re.M).group(1)
        letter = name[0]
        rel = f'pool/main/{letter}/{name}/{deb.name}'
        dest = APT_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(deb, dest)
        entries.append(f'{fields}\nFilename: {rel}\nSize: {dest.stat().st_size}\nSHA256: {sha256(dest)}\n')
    pkgdir = APT_DIR / f'dists/{SUITE}/main/binary-{ARCH}'
    pkgdir.mkdir(parents=True)
    text = '\n'.join(entries).encode()
    (pkgdir / 'Packages').write_bytes(text)
    (pkgdir / 'Packages.gz').write_bytes(gzip.compress(text, 9, mtime=0))
    (pkgdir / 'Packages.xz').write_bytes(lzma.compress(text))
    rel_files = {}
    for f in sorted((APT_DIR / f'dists/{SUITE}').rglob('*')):
        if f.is_file():
            rel_files[str(f.relative_to(APT_DIR / f'dists/{SUITE}'))] = f
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S UTC')
    lines = ['Origin: Amerika', 'Label: Amerika OS', f'Suite: {SUITE}', f'Codename: {SUITE}', f'Date: {now}',
             f'Architectures: {ARCH}', 'Components: main', 'Description: Amerika OS packages', 'SHA256:']
    for rel, f in rel_files.items():
        lines.append(f' {sha256(f)} {f.stat().st_size:>16} {rel}')
    release = APT_DIR / f'dists/{SUITE}/Release'
    release.write_text('\n'.join(lines) + '\n')
    gpg('--local-user', KEY_NAME, '--armor', '--detach-sign', '--output', str(release) + '.gpg', str(release))
    gpg('--local-user', KEY_NAME, '--clearsign', '--output', str(release.parent / 'InRelease'), str(release))
    gpg('--export', '--output', str(APT_DIR / 'amerika-archive-keyring.gpg'), KEY_NAME)
    gpg('--armor', '--export', '--output', str(APT_DIR / 'amerika-archive-keyring.asc'), KEY_NAME)
    fp = gpg('--with-colons', '--fingerprint', KEY_NAME, capture_output=True, text=True).stdout
    fingerprint = re.search(r'^fpr:+([0-9A-F]{40}):', fp, re.M).group(1)
    manifest = {'suite': SUITE, 'architecture': ARCH, 'fingerprint': fingerprint,
                'generated': now, 'packages': {}}
    for deb in sorted(APT_DIR.glob('pool/main/*/*/*.deb')):
        manifest['packages'][deb.name] = {'path': str(deb.relative_to(APT_DIR)), 'size': deb.stat().st_size,
                                          'sha256': sha256(deb)}
    (APT_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Repository written to', APT_DIR, 'key', fingerprint)


def main():
    os.umask(0o022)
    ap = argparse.ArgumentParser()
    ap.add_argument('--init-key', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--sign-only', action='store_true', help='regenerate the repository from dist/packages')
    args = ap.parse_args()
    if args.init_key:
        init_key()
        return
    init_key()
    if not args.sign_only:
        names = args.only.split(',') if args.only else list(BUILDERS)
        if (APT_DIR / 'amerika-archive-keyring.gpg').exists() is False:
            gpg('--export', '--output', str(APT_DIR / 'amerika-archive-keyring.gpg'), KEY_NAME) if APT_DIR.mkdir(
                parents=True, exist_ok=True) is None else None
        for name in names:
            deb = BUILDERS[name]().build()
            print('built', deb.name, deb.stat().st_size)
    make_repo(sorted(PKG_DIR.glob('*.deb')))


if __name__ == '__main__':
    main()
