"""amerika-studio: the shared layer of the Developer Edition (keys, bridge, MCP server, hub, web shell, icons).

Build only; nothing is enabled or started at install time. The bridge unit is started on demand by `amerika-studio ensure`
(the hub and the apps call it), so installing the package changes no running service and no user configuration.
"""
import shutil

STUDIO_BINS = ('amerika-studio', 'amerika-studio-bridge', 'amerika-studio-mcp', 'amerika-studio-hub', 'amerika-studio-keys',
               'amerika-studio-webview', 'amerika-studio-approve')


def register(b):
    def build():
        src = b.OS / 'studio'
        p = b.Pkg('amerika-studio', b.DE_VERSION,
                  'Amerika Studio\nThe shared layer of the Amerika OS Developer Edition: one Anthropic key manager (login keyring), '
                  'a loopback bridge so Studio apps never see the key, the Studio hub, a WebKitGTK shell for Amerika Sprite and AmerikaBox, '
                  'and an MCP server that lets Amerika Agent drive Amerika Render, Engine, Sprite and Box.',
                  arch='all', title='Amerika Studio', category='Development', section='devel',
                  depends='python3, python3-gi, gir1.2-gtk-4.0, gir1.2-webkit-6.0, libsecret-tools, '
                          f'amerika-desktop-shell (>= {b.DE_VERSION}), amerika-icon-theme',
                  recommends='gnome-keyring, amerika-agent')
        shutil.copytree(src / 'amerika_studio', p.path('/usr/lib/python3/dist-packages/amerika_studio'),
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in STUDIO_BINS:
            p.copy(src / 'bin' / name, '/usr/bin/' + name, 0o755)
        p.copy(src / 'tools.json', '/usr/share/amerika-studio/tools.json')
        for f in sorted((src / 'web').iterdir()):
            p.copy(f, '/usr/share/amerika-studio/web/' + f.name)
        p.copy(src / 'systemd/amerika-studio-bridge.service', '/usr/lib/systemd/user/amerika-studio-bridge.service')
        for f in sorted((src / 'applications').glob('*.desktop')):
            p.copy(f, '/usr/share/applications/' + f.name)
        for f in sorted((src / 'icons/hicolor').rglob('*.svg')):
            p.copy(f, '/usr/share/icons/hicolor/' + str(f.relative_to(src / 'icons/hicolor')))
        docs = b.ROOT / 'docs/studio'
        for f in sorted(docs.glob('*.md')):
            p.copy(f, '/usr/share/doc/amerika-studio/' + f.name)
        p.file('/usr/share/doc/amerika-studio/NOTICE',
               'Amerika Studio is original Amerika code (GPL-3.0-only).\n'
               'Amerika Render is Blender (GPL-3.0-or-later) with an Amerika add-on; "Blender" is a trademark of the Blender Foundation.\n'
               'Amerika Engine is Godot (MIT) with an Amerika editor plugin.\n'
               'AmerikaBox is a fork of BeepBox (MIT, https://github.com/johnnesky/beepbox).\n'
               'Amerika Sprite is original code; it is not derived from Aseprite.\n'
               'Each app package ships the notices of what it is built on.\n')
        p.scripts['postinst'] = ('#!/bin/sh\nset -e\n# No service is enabled or started here and no per-user setting is changed.\n'
                                 'if command -v gtk-update-icon-cache >/dev/null 2>&1; then\n'
                                 '  gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true\nfi\nexit 0\n')
        p.scripts['prerm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ] || [ "$1" = purge ]; then\n'
                              '  if command -v deb-systemd-invoke >/dev/null 2>&1; then\n'
                              '    deb-systemd-invoke --user stop amerika-studio-bridge.service || true\n'
                              '  fi\nfi\nexit 0\n')
        p.copyright('Copyright Amerika LLC, GPL-3.0-only.\nSee /usr/share/common-licenses/GPL-3.\n'
                    'Blender, Godot and BeepBox keep their own licences; see /usr/share/doc/amerika-studio/NOTICE.\n')
        return p
    return {'amerika-studio': build}
