"""amerika-sprite: the Sprite pixel-art editor (original code; HTML5 canvas app hosted by amerika-studio-webview)."""
import shutil


def register(b):
    def build():
        src = b.OS / 'sprite'
        p = b.Pkg('amerika-sprite', b.DE_VERSION,
                  'Sprite\nA pixel-art editor and animator with an AI sprite builder (original code; not Aseprite). '
                  'Layers, frames, tags, palettes, sprite sheets with Godot SpriteFrames export, GIF, and read-only .aseprite import.',
                  arch='all', title='AltStack Sprite', category='Graphics', section='graphics',
                  depends=f'amerika-studio (>= {b.DE_VERSION}), gir1.2-webkit-6.0')
        shutil.copytree(src / 'app', p.path('/usr/share/amerika-sprite/app'), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        p.copy(src / 'bin/amerika-sprite', '/usr/bin/amerika-sprite', 0o755)
        p.copy(src / 'applications/amerika-sprite.desktop', '/usr/share/applications/amerika-sprite.desktop')
        docs = b.ROOT / 'docs/studio/sprite.md'
        if docs.is_file():
            p.copy(docs, '/usr/share/doc/amerika-sprite/sprite.md')
        p.file('/usr/share/doc/amerika-sprite/NOTICE',
               'Sprite is original Amerika code (GPL-3.0-only). It is NOT Aseprite and is not affiliated with Aseprite or Igara Studio.\n'
               'No Aseprite source code was copied, ported or translated. Aseprite is only a feature reference. The .aseprite reader is '
               'import-only and was written from the public file format specification.\n')
        p.scripts['postinst'] = ('#!/bin/sh\nset -e\nif command -v gtk-update-icon-cache >/dev/null 2>&1; then\n'
                                 '  gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true\nfi\nexit 0\n')
        p.copyright('Copyright AltStack LLC, GPL-3.0-only.\nSee /usr/share/common-licenses/GPL-3.\n'
                    'Sprite is not Aseprite and is not affiliated with it.\n')
        return p
    return {'amerika-sprite': build}
