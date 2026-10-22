"""amerika-engine: Godot (distro package, not bundled) + the amerika_engine editor plugin, launcher, templates and notices."""
import shutil

IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '*.uid')


def register(b):
    def build():
        src = b.OS / 'engine'
        p = b.Pkg('amerika-engine', b.DE_VERSION,
                  'Amerika Engine, powered by Godot\nGodot 4 with an AI game assembler: a chat dock, a game recipe that '
                  'generates scenes, scripts and settings, tested behaviour components, starter templates and a control endpoint for '
                  'Amerika Agent. Godot itself comes from the distro package. Godot is a trademark of the Godot Foundation; '
                  'Amerika Engine is not affiliated with or endorsed by it.',
                  arch='all', title='Amerika Engine', category='Development', section='devel',
                  depends=f'amerika-studio (>= {b.DE_VERSION}), godot (>= 4.4), python3',
                  recommends='godot-templates, vulkan-tools, python3-pil')
        shutil.copytree(src / 'amerika_engine', p.path('/usr/lib/python3/dist-packages/amerika_engine'), ignore=IGNORE)
        p.copy(src / 'bin/amerika-engine', '/usr/bin/amerika-engine', 0o755)
        shutil.copytree(src / 'addons', p.path('/usr/share/amerika-engine/addons'), ignore=IGNORE)
        shutil.copytree(src / 'templates', p.path('/usr/share/amerika-engine/templates'), ignore=IGNORE)
        for f in sorted((src / 'icons').glob('*.svg')):
            p.copy(f, '/usr/share/amerika-engine/icons/' + f.name)
        p.copy(src / 'applications/amerika-engine.desktop', '/usr/share/applications/amerika-engine.desktop')
        docs = b.ROOT / 'docs/studio/engine.md'
        if docs.exists():
            p.copy(docs, '/usr/share/doc/amerika-engine/engine.md')
        p.copy(src / 'NOTICE', '/usr/share/doc/amerika-engine/NOTICE')
        p.copy(src / 'GODOT-LICENSE.txt', '/usr/share/doc/amerika-engine/GODOT-LICENSE.txt')
        p.scripts['postinst'] = '#!/bin/sh\nset -e\n# Nothing is started or configured here; settings are seeded per user on first launch.\nexit 0\n'
        p.copyright('Amerika integration (plugin, launcher, templates): Copyright Amerika LLC, GPL-3.0-only.\n'
                    'See /usr/share/common-licenses/GPL-3.\n\n'
                    'Godot Engine: Copyright (c) 2014-present Godot Engine contributors, Copyright (c) 2007-2014 Juan Linietsky, '
                    'Ariel Manzur. MIT licence, full text in /usr/share/doc/amerika-engine/GODOT-LICENSE.txt and in the godot package.\n'
                    '"Godot" is a trademark of the Godot Foundation; Amerika Engine is not affiliated with or endorsed by it.\n')
        return p
    return {'amerika-engine': build}
