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
DE_VERSION = '2.0.0'
MAINTAINER = 'Amerika LLC <noreply@amerika.social>'
HOMEPAGE = 'https://www.amerika.social/downloads/os'
SYSTEM_SHELL = Path('/usr/share/plasma/shells/org.kde.plasma.desktop')
VENDOR = ROOT / 'vendor/cosmic'
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
    p = THEME_OUT / 'icons/scalable/apps' / f'{name}.svg'
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
    p.copyright('Amerika OS repository key and APT source.\nCopyright Amerika LLC. Licensed GPL-3.0-only.\n'
                'See /usr/share/common-licenses/GPL-3.\n')
    return p


def build_icons():
    p = Pkg('amerika-icon-theme', DE_VERSION, 'Amerika OS icon theme\nCharcoal and crimson icons for Amerika OS.',
            depends='cosmic-icons', title='Amerika Icons', category='Appearance', section='gnome')
    dest = p.path('/usr/share/icons/AmerikaOS')
    shutil.copytree(THEME_OUT / 'icons', dest, ignore=shutil.ignore_patterns('icon-theme.cache'))
    idx = dest / 'index.theme'
    t = idx.read_text()
    t = re.sub(r'^Inherits=.*$', 'Inherits=Cosmic,Adwaita,hicolor', t, flags=re.M)
    t = re.sub(r'^Comment=.*$', 'Comment=Amerika OS icon theme', t, flags=re.M)
    idx.write_text(t)
    for alias, source in (('amerika-ai', 'chatgpt'), ('amerika-software', 'plasmadiscover')):
        for ext in ('svg', 'png'):
            s = dest / 'scalable/apps' / f'{source}.{ext}'
            if s.exists():
                shutil.copy2(s, dest / 'scalable/apps' / f'{alias}.{ext}')
    p.scripts['postinst'] = ('#!/bin/sh\nset -e\nif [ "$1" = configure ] && command -v gtk-update-icon-cache >/dev/null;'
                             ' then gtk-update-icon-cache -q -f /usr/share/icons/AmerikaOS || true; fi\nexit 0\n')
    p.copyright('Icon theme generated for Amerika OS by Amerika LLC; GPL-3.0-only.\n'
                'Some icons are recolored derivatives of the Breeze/KDE icon set (LGPL-3.0-or-later). The theme\n'
                'inherits from the COSMIC icon theme (cosmic-icons) at run time.\n')
    return p


def vendor_root(*names):
    """Extract the named vendored COSMIC packages into a scratch root and return it."""
    root = STAGE / '_cosmic-defaults'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for n in names:
        deb = next(VENDOR.glob(f'{n}_*.deb'), None)
        if deb is None:
            sys.exit(f'vendor/cosmic has no {n} package; run tools/fetch-cosmic.py first.')
        sh('dpkg-deb', '-x', deb, root)
    return root


def recolor(text, mapping):
    for old, new in mapping.items():
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


# Dark v2 default hex colours -> Amerika dark chrome-and-crimson. The alpha suffix of each colour is kept.
DARK_MAP = {
    '#63D0DF': '#FF4D79', '#63BAC6': '#E64470', '#3C737A': '#8F2A46', '#326870': '#73213A',
    '#1B1B1B': '#0D0D13', '#262626': '#14141B', '#2E2E2E': '#1C1C26', '#363636': '#22222E',
    '#3B3B3B': '#262633', '#434343': '#2E2E3C', '#4A4A4A': '#343446', '#4F4F4F': '#3A3A4C',
    '#515151': '#3E3E50', '#585858': '#3C3C4E', '#444444': '#343446', '#343434': '#26263A',
    '#272727': '#181821', '#161616': '#0D0D13', '#414141': '#2E2E3C',
}


def cosmic_theme(dest):
    """Seed tree for the Amerika COSMIC theme, derived from the stock Dark theme files."""
    root = vendor_root('cosmic-settings')
    src = root / 'usr/share/cosmic'
    out = Path(dest)
    for rel in ('com.system76.CosmicTheme.Dark/v2', 'com.system76.CosmicTheme.Dark/v1'):
        if not (src / rel).exists():
            continue
        for f in sorted((src / rel).iterdir()):
            if f.name in ('palette', 'name', 'is_dark'):
                text = f.read_text()
            else:
                text = recolor(f.read_text(), DARK_MAP)
            if f.name == 'name':
                text = '"amerika-dark"'
            write(out / rel / f.name, text)
    # builder values so that COSMIC Settings regenerates the same look when the theme is edited
    b = out / 'com.system76.CosmicTheme.Dark.Builder'
    write(b / 'v2/accent', 'Some((\n    red: 1.0,\n    green: 0.3019608,\n    blue: 0.4745098,\n))')
    write(b / 'v2/bg_color', 'Some((\n    red: 0.05098039,\n    green: 0.05098039,\n    blue: 0.07450981,\n    alpha: 1.0,\n))')
    write(out / 'com.system76.CosmicTheme.Mode/v1/is_dark', 'true')
    write(out / 'com.system76.CosmicTheme.Mode/v1/auto_switch', 'false')
    write(out / 'com.system76.CosmicTk/v1/icon_theme', '"AmerikaOS"')


def build_theme():
    p = Pkg('amerika-theme', DE_VERSION, 'Amerika OS dark retro-futurist theme\nCOSMIC theme (chrome and crimson), horizon '
            'wallpaper and defaults applied once per user by the Amerika session.',
            depends='cosmic-settings, cosmic-bg, amerika-icon-theme', title='Amerika Theme', category='Appearance',
            extra={}, conflicts='')
    cosmic_theme(p.path('/usr/share/amerika-os/cosmic'))
    p.copy(SRC / 'theme/wallpaper-3840x2160.png', f'{BG_DIR}/amerika-horizon-3840x2160.png')
    p.copy(SRC / 'theme/wallpaper-2560x1600.png', f'{BG_DIR}/amerika-horizon-2560x1600.png')
    p.copyright('Amerika OS theme, Copyright Amerika LLC, GPL-3.0-only. The colour values are derived from the COSMIC\n'
                'Dark theme defaults (cosmic-settings, GPL-3.0-only, System76).\n')
    return p


def cosmic_layout(dest):
    """Seed tree for the Amerika top bar and floating dock, derived from the stock COSMIC panel defaults."""
    root = vendor_root('cosmic-panel', 'cosmic-applets', 'cosmic-bg')
    src = root / 'usr/share/cosmic'
    out = Path(dest)
    panel = src / 'com.system76.CosmicPanel.Panel/v1'
    dock = src / 'com.system76.CosmicPanel.Dock/v1'
    for f in panel.iterdir():
        text = f.read_text()
        if f.name == 'opacity':
            text = '0.88'
        elif f.name == 'plugins_center':
            text = 'None'
        elif f.name == 'plugins_wings':
            text = ('Some((["com.system76.CosmicPanelLauncherButton", "com.system76.CosmicPanelWorkspacesButton", '
                    '"com.system76.CosmicPanelAppButton"],["com.system76.CosmicAppletInputSources", '
                    '"com.system76.CosmicAppletA11y", "com.system76.CosmicAppletStatusArea", '
                    '"com.system76.CosmicAppletTiling", "com.system76.CosmicAppletAudio", '
                    '"com.system76.CosmicAppletBluetooth", "com.system76.CosmicAppletNetwork", '
                    '"com.system76.CosmicAppletBattery", "com.system76.CosmicAppletNotifications", '
                    '"com.system76.CosmicAppletTime", "com.system76.CosmicAppletPower"]))')
        write(out / 'com.system76.CosmicPanel.Panel/v1' / f.name, text)
    for f in dock.iterdir():
        text = f.read_text()
        if f.name == 'plugins_center':
            text = '\n'.join(['Some(["com.system76.CosmicAppList", "com.system76.CosmicAppletMinimize"])'])
        elif f.name == 'margin':
            text = '8'
        elif f.name == 'padding':
            text = '6'
        elif f.name == 'opacity':
            text = '0.92'
        elif f.name == 'size':
            text = 'M'
        write(out / 'com.system76.CosmicPanel.Dock/v1' / f.name, text)
    write(out / 'com.system76.CosmicPanel/v1/entries', '["Panel","Dock"]')
    write(out / 'com.system76.CosmicAppList/v1/favorites',
          '[\n    "amerika-social",\n    "amerika-ai",\n    "amerika-venture",\n    "amerika-files",\n    "amerika-terminal",\n'
          '    "amerika-office",\n    "amerika-software",\n]\n')
    write(out / 'com.system76.CosmicAppList/v1/filter_top_levels', 'None')
    bg = (src / 'com.system76.CosmicBackground/v1/all').read_text()
    bg = re.sub(r'source: Path\("[^"]*"\)', f'source: Path("{BG_DIR}/amerika-horizon-3840x2160.png")', bg)
    bg = re.sub(r'filter_by_theme: #?\w+', 'filter_by_theme: false', bg)
    write(out / 'com.system76.CosmicBackground/v1/all', bg)
    write(out / 'com.system76.CosmicBackground/v1/same-on-all', 'true')


def build_shell():
    p = Pkg('amerika-desktop-shell', DE_VERSION, 'Amerika OS desktop layout\nThe Amerika top bar and floating dock for the '
            'COSMIC desktop, seeded into the user configuration by the Amerika session.',
            depends='cosmic-panel, cosmic-applets, cosmic-bg, cosmic-comp, amerika-theme, amerika-icon-theme',
            title='Amerika Desktop Layout')
    cosmic_layout(p.path('/usr/share/amerika-os/cosmic'))
    p.copyright('Amerika OS layout defaults, Copyright Amerika LLC, GPL-3.0-only. Derived from the COSMIC panel defaults\n'
                '(cosmic-panel, cosmic-applets: GPL-3.0-only, System76).\n')
    return p


def build_session():
    p = Pkg('amerika-session', DE_VERSION, 'Amerika OS login session\nAdds an "Amerika OS" entry to the login screen. '
            'It starts the stock COSMIC session with the Amerika layout and theme.\nThe COSMIC and Plasma sessions are '
            'not changed.', depends='amerika-desktop-shell, amerika-theme, cosmic-session',
            title='Amerika Session', conflicts='')
    p.copy(SRC / 'session/amerika-session', '/usr/bin/amerika-session', 0o755)
    p.copy(SRC / 'session/amerika-cosmic-seed', '/usr/bin/amerika-cosmic-seed', 0o755)
    p.copy(SRC / 'session/amerika.desktop', '/usr/share/wayland-sessions/amerika.desktop')
    p.copyright('Amerika OS session files, Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


def build_plasma():
    """Legacy Amerika OS 1.x desktop on KDE Plasma: session, shell package and KDE theme."""
    version = subprocess.run(['dpkg-query', '-W', '-f', '${Version}', 'plasma-desktop-data'], capture_output=True,
                             text=True).stdout
    m = re.match(r'(\d+):(\d+)\.(\d+)', version)
    epoch, major, minor = m.group(1), int(m.group(2)), int(m.group(3))
    dep = f'plasma-desktop-data (>= {epoch}:{major}.{minor}), plasma-desktop-data (<< {epoch}:{major}.{minor + 1}~)'
    p = Pkg('amerika-plasma', DE_VERSION, 'Amerika OS on KDE Plasma (legacy)\nThe Amerika OS 1.x desktop: an Amerika '
            'session, shell package and theme on KDE Plasma and KWin.\nThe main Amerika OS desktop is now based on '
            'COSMIC; install this package only if you want the Plasma variant.',
            depends=f'plasma-desktop, {dep}, plasma-workspace, kwin-wayland, libkf6config-bin, konsole, '
                    'amerika-icon-theme', title='Amerika OS (Plasma, legacy)',
            extra={}, provides='', conflicts='')
    p.extra['Replaces'] = 'amerika-desktop-shell (<< 2.0.0), amerika-theme (<< 2.0.0), amerika-session (<< 2.0.0)'
    p.copy(SRC / 'plasma/theme/AmerikaDark.colors', '/usr/share/color-schemes/AmerikaDark.colors')
    p.copy(SRC / 'plasma/theme/konsole/Amerika.profile', '/usr/share/konsole/Amerika.profile')
    p.copy(SRC / 'plasma/theme/konsole/AmerikaDark.colorscheme', '/usr/share/konsole/AmerikaDark.colorscheme')
    shutil.copytree(SRC / 'plasma/theme/look-and-feel', p.path('/usr/share/plasma/look-and-feel'))
    wall = '/usr/share/wallpapers/Amerika'
    p.copy(SRC / 'theme/wallpaper-2560x1600.png', f'{wall}/contents/images/2560x1600.png')
    p.copy(SRC / 'theme/wallpaper-3840x2160.png', f'{wall}/contents/images/3840x2160.png')
    p.file(f'{wall}/metadata.json', json.dumps({
        'KPackageStructure': 'Wallpaper/Images',
        'KPlugin': {'Authors': [{'Name': 'Amerika LLC'}], 'Id': 'Amerika', 'License': 'GPL-3.0', 'Name': 'Amerika'}},
        indent=2) + '\n')
    meta = json.loads((SYSTEM_SHELL / 'metadata.json').read_text())

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if not re.search(r'\[.*\]$', k)}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o

    meta = strip(meta)
    meta['KPlugin'].update({'Id': 'org.amerika.shell', 'Name': 'Amerika OS', 'Description': 'Amerika OS desktop shell',
                            'Authors': [{'Name': 'Amerika LLC'}, {'Name': 'KDE contributors'}],
                            'License': 'GPL-3.0+', 'Website': 'https://www.amerika.social', 'Icon': 'amerika-hub'})
    base = '/usr/share/plasma/shells/org.amerika.shell'
    p.file(f'{base}/metadata.json', json.dumps(meta, indent=2) + '\n')
    layout = (SRC / 'plasma/shell/layout-templates/org.amerika.topbar/contents/layout.js').read_text() + '\n' + \
        (SRC / 'plasma/shell/layout-templates/org.amerika.dock/contents/layout.js').read_text() + '\n' + \
        (SRC / 'plasma/shell/main.js').read_text()
    p.file(f'{base}/contents/main.js', layout)
    p.file(f'{base}/contents/layout.js', layout)
    p.copy(SYSTEM_SHELL / 'contents/defaults', f'{base}/contents/defaults')
    for item in sorted((SYSTEM_SHELL / 'contents').iterdir()):
        if item.name not in ('main.js', 'defaults'):
            p.path(f'{base}/contents/{item.name}').symlink_to(item)
    p.copy(SRC / 'plasma/amerika-plasma-session', '/usr/bin/amerika-plasma-session', 0o755)
    p.copy(SRC / 'plasma/amerika-plasma-first-run', '/usr/bin/amerika-plasma-first-run', 0o755)
    p.copy(SRC / 'plasma/amerika-plasma.desktop', '/usr/share/wayland-sessions/amerika-plasma.desktop')
    p.copy(SRC / 'plasma/50-amerika-plasma.sh', '/etc/xdg/plasma-workspace/env/50-amerika-plasma.sh')
    p.copy(SRC / 'plasma/amerika-plasma-first-run.desktop', '/etc/xdg/autostart/amerika-plasma-first-run.desktop')
    p.copyright('Amerika OS (Plasma) files, Copyright Amerika LLC, GPL-3.0-only.\n\nThe shell views are the unmodified KDE '
                'Plasma files from plasma-desktop-data, linked from /usr/share/plasma/shells/org.kde.plasma.desktop '
                '(GPL-2.0-or-later / LGPL-2.0-or-later, KDE contributors).\n')
    return p


def build_hub():
    p = Pkg('amerika-hub', DE_VERSION, 'Amerika Hub\nThe Amerika OS start screen for Social, AI, browsing, files and '
            'terminal.', depends='python3-pyqt6, libgtk-3-bin, amerika-icon-theme', title='Amerika Hub')
    p.copy(SRC / 'hub/amerika-hub', '/usr/bin/amerika-hub', 0o755)
    desktop_file(p, '[Desktop Entry]\nType=Application\nName=Amerika Hub\nComment=Your Amerika OS start screen\n'
                 'Exec=/usr/bin/amerika-hub\nIcon=amerika-hub\nTerminal=false\nCategories=Utility;\n', 'amerika-hub')
    if icon_svg('amerika-hub'):
        p.copy(icon_svg('amerika-hub'), '/usr/share/icons/hicolor/scalable/apps/amerika-hub.svg')
    p.copyright('Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


def build_apps():
    p = Pkg('amerika-apps', DE_VERSION, 'Amerika core apps\nAmerika Files, Terminal, Text, Settings and AI launchers. '
            'Files, Terminal, Text and Settings are branded launchers\nfor COSMIC Files, Terminal, Edit and Settings, '
            'which remain installed and unmodified.',
            depends='cosmic-files, cosmic-term, cosmic-edit, cosmic-settings, amerika-theme, amerika-icon-theme',
            recommends='amerika-venture', title='Amerika Core Apps')
    for name in ('amerika-files', 'amerika-terminal', 'amerika-text', 'amerika-settings', 'amerika-ai'):
        p.copy(SRC / f'apps/{name}.desktop', f'/usr/share/applications/{name}.desktop')
    p.copy(SRC / 'apps/amerika-ai', '/usr/bin/amerika-ai', 0o755)
    p.copy(SRC / 'apps/ai-url', '/etc/amerika/ai-url')
    p.file('/usr/share/doc/amerika-apps/README.Debian',
           'Amerika Files, Terminal, Text and Settings launch COSMIC Files, Terminal, Edit and Settings.\n'
           'Those programs are copyright System76 and contributors (GPL-3.0-only).\n'
           'Amerika AI opens the URL in /etc/amerika/ai-url (default https://chatgpt.com) in Amerika Venture.\n'
           'It is a web shortcut; no AI service is bundled.\n')
    p.copyright('Launchers, Copyright Amerika LLC, GPL-3.0-only.\nCOSMIC Files, Terminal, Edit and Settings are '
                'separate packages (System76) with their own licenses.\n')
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


def prepare_app(key, name, dest_dir):
    root = extract(app_archive(key), STAGE / f'_payload-{key}')
    target = Path(dest_dir)
    return root, target


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
    p = Pkg('amerika-desktop', DE_VERSION, 'Amerika OS desktop environment\nInstalls the Amerika desktop session, layout, '
            'theme, apps (Social, AI, Venture, Office, Files, Terminal)\nand the Amerika Software manager. Built on the '
            'COSMIC desktop.', depends='amerika-session, amerika-desktop-shell, amerika-theme, '
            'amerika-icon-theme, amerika-hub, amerika-apps, amerika-software, amerika-repo-keyring, amerika-social, '
            'amerika-venture, amerika-office, cosmic-session, cosmic-greeter', arch=ARCH, title='Amerika OS Desktop',
            section='metapackages')
    p.copyright('Copyright Amerika LLC, GPL-3.0-only.\n')
    return p


BUILDERS = {
    'amerika-repo-keyring': build_keyring, 'amerika-icon-theme': build_icons, 'amerika-theme': build_theme,
    'amerika-desktop-shell': build_shell, 'amerika-session': build_session, 'amerika-plasma': build_plasma, 'amerika-hub': build_hub,
    'amerika-apps': build_apps, 'amerika-software': build_software, 'amerika-social': build_social,
    'amerika-venture': build_venture, 'amerika-office': build_office, 'amerika-desktop': build_meta,
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
    # Unmodified COSMIC packages mirrored from the Pop!_OS repository (verified by tools/fetch-cosmic.py).
    vendor = json.loads((VENDOR / 'manifest.json').read_text()) if (VENDOR / 'manifest.json').exists() else None
    for deb in sorted(VENDOR.glob('*.deb')) if vendor else []:
        info = vendor['packages'][deb.name]
        if sha256(deb) != info['sha256']:
            sys.exit(f'{deb.name} no longer matches vendor/cosmic/manifest.json')
        fields = deb_fields(deb)
        name = info['package']
        rel = f'pool/main/{name[0]}/{name}/{deb.name}'
        dest = APT_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(deb, dest)
        entries.append(f'{fields}\nAmerika-Category: COSMIC (System76)\nFilename: {rel}\nSize: {dest.stat().st_size}\n'
                       f'SHA256: {sha256(dest)}\n')
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
