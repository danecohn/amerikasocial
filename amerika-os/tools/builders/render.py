"""amerika-render: Blender (upstream, GPL) + the amerika_render add-on, launcher, theme, splash, icon. Arch all.

Blender itself is a dependency, not bundled: Ubuntu's `blender` package stays untouched and keeps getting updates.
"""
import io
import zipfile
from pathlib import Path

NAME = 'amerika-render'
SHARE = '/usr/share/amerika-render'


def register(b):
    src = b.OS / 'render'

    def build():
        p = b.Pkg(NAME, b.DE_VERSION,
                  'Amerika Render: Blender with an AI modelling assistant\n'
                  'Talk to Blender: describe a model and the assistant builds, looks at and refines it with real Blender tools, '
                  'then exports game-ready .glb files to your Amerika Studio project. Powered by Blender (GPL-3.0-or-later); '
                  'Blender is a trademark of the Blender Foundation and Amerika Render is not affiliated with or endorsed by it.',
                  arch='all', title='Amerika Render', category='Graphics', section='graphics',
                  depends=f'amerika-studio (>= {b.DE_VERSION}), blender (>= 5.0), python3, python3-numpy')
        addon = src / 'amerika_render'
        files = sorted(f for f in addon.iterdir() if f.is_file() and f.suffix in ('.py', '.toml'))
        for f in files:
            p.copy(f, f'{SHARE}/scripts/addons/amerika_render/{f.name}', 0o644)
        # Blender 4.2+ extension zip (Install from Disk), same files at the archive root.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.writestr(zipfile.ZipInfo(f.name, (2026, 10, 21, 0, 0, 0)), f.read_bytes())
        zpath = p.path(f'{SHARE}/extension/amerika_render-{b.DE_VERSION}.zip')
        zpath.parent.mkdir(parents=True, exist_ok=True)
        zpath.write_bytes(buf.getvalue())
        zpath.chmod(0o644)
        p.copy(src / 'startup/amerika_startup.py', f'{SHARE}/startup/amerika_startup.py', 0o644)
        p.copy(src / 'theme/amerika.xml', f'{SHARE}/theme/amerika.xml', 0o644)
        p.copy(src / 'data/splash.png', f'{SHARE}/splash.png', 0o644)
        p.copy(src / 'data/startup.blend', f'{SHARE}/startup.blend', 0o644)
        p.copy(src / 'NOTICE', f'{SHARE}/NOTICE', 0o644)
        p.copy(src / 'bin/amerika-render', '/usr/bin/amerika-render', 0o755)
        p.copy(src / 'applications/amerika-render.desktop', '/usr/share/applications/amerika-render.desktop', 0o644)
        p.copy(src / 'NOTICE', f'/usr/share/doc/{NAME}/NOTICE', 0o644)
        docs = b.ROOT / 'docs/studio/render.md'
        if docs.exists():
            p.copy(docs, f'/usr/share/doc/{NAME}/README.md', 0o644)
        p.scripts['postinst'] = ('#!/bin/sh\nset -e\nif [ "$1" = configure ]; then\n'
                                 '  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true\n'
                                 '  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications 2>/dev/null || true\n'
                                 'fi\nexit 0\n')
        p.scripts['postrm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ] || [ "$1" = purge ]; then\n'
                               '  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true\n'
                               'fi\nexit 0\n')
        p.copyright('Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n'
                    'Upstream-Name: Amerika Render\n\n'
                    'Files: *\nCopyright: 2026 Amerika LLC\nLicense: GPL-3.0-or-later\n'
                    ' On Debian and Ubuntu systems the full text of the GNU General Public License version 3 is in\n'
                    ' /usr/share/common-licenses/GPL-3.\n\n'
                    'Notice: Amerika Render is powered by Blender (GPL-3.0-or-later). Blender is a trademark of the\n'
                    ' Blender Foundation; Amerika Render is not affiliated with or endorsed by the Blender Foundation.\n'
                    ' This package does not contain Blender; it depends on the unmodified Ubuntu "blender" package\n'
                    ' (see /usr/share/doc/blender/copyright and https://projects.blender.org/blender/blender).\n')
        return p

    return {NAME: build}
