"""amerika-developer: opt-in meta package for the Developer Edition. Deliberately defines NO META_DEPENDS, so
amerika-desktop does not pull it in."""


def register(b):
    def build():
        p = b.Pkg('amerika-developer', b.DE_VERSION,
                  'AltStack Desktop Developer Edition\nTurns this computer into an agentic game-making machine: Amerika Studio, '
                  'Amerika Render (Blender), Amerika Engine (Godot), Amerika Sprite and AmerikaBox. Install it to opt in.',
                  arch='all', title='Amerika Developer Edition', category='Development', section='metapackages',
                  depends=', '.join(f'{n} (>= {b.DE_VERSION})' for n in
                                    ('amerika-studio', 'amerika-render', 'amerika-engine', 'amerika-sprite', 'amerika-box', 'amerika-gamedev')),
                  recommends='git, ffmpeg, vulkan-tools, mesa-utils-bin, audacity, gimp, inkscape')
        p.file('/usr/share/doc/amerika-developer/README',
               'AltStack Desktop Developer Edition (meta package).\nOpen "Amerika Studio" from the launcher to set up your Anthropic key.\n'
               'Documentation: /usr/share/doc/amerika-studio/README.md\n')
        p.copyright('Copyright AltStack LLC, GPL-3.0-only.\nMeta package; see the packages it depends on for their licences.\n')
        return p
    return {'amerika-developer': build}
