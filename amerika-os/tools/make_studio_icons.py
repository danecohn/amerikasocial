#!/usr/bin/env python3
"""Generates the Amerika Studio icons (hub + the four apps) in the Amerika OS "horizon cartridge" style.

Output: src/os/studio/icons/hicolor/scalable/apps/amerika-{studio,render,engine,sprite,box}.svg and
        src/os/studio/icons/hicolor/symbolic/apps/amerika-studio-symbolic.svg
Reuses the drawing helpers of tools/make_icons.py so the tiles match the rest of the icon theme.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_icons as mi  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / 'src/os/studio/icons/hicolor'

GLYPHS = {
    # Hub: four tiles around a spark
    'amerika-studio': ('crimson', '<rect x="72" y="58" width="48" height="40" rx="8"/><rect x="136" y="58" width="48" height="40" rx="8"/>'
                       '<rect x="72" y="112" width="48" height="40" rx="8"/><rect x="136" y="112" width="48" height="40" rx="8"/>'),
    # Render: wireframe cube
    'amerika-render': ('cyan', '<path d="M128,52 L184,80 V140 L128,168 L72,140 V80 Z"/><path d="M72,80 L128,108 L184,80 M128,108 V168"/>'
                       '<path d="M100,66 L156,94" opacity=".55"/>'),
    # Engine: game controller
    'amerika-engine': ('violet', '<path d="M82,80 H174 A22,22 0 0 1 196,102 L202,134 A16,16 0 0 1 172,142 L162,128 H94 L84,142 A16,16 0 0 1 54,134 L60,102 A22,22 0 0 1 82,80 Z"/>'
                       '<path d="M92,96 V116 M82,106 H102"/><circle cx="160" cy="98" r="4"/><circle cx="176" cy="112" r="4"/>'),
    # Sprite: pixel heart
    'amerika-sprite': ('phosphor', '<path d="M92,60 H116 V76 H132 V60 H156 V76 H172 V108 H156 V124 H140 V140 H124 V156 H108 V140 H92 V124 H76 V108 H76 V76 H92 Z" transform="translate(-4,-6) scale(1)"/>'
                       '<path d="M94,86 H106" opacity=".7"/>'),
    # Box: note with sound waves
    'amerika-box': ('amber', '<path d="M104,128 V66 L168,54 V116"/><ellipse cx="90" cy="130" rx="16" ry="12"/><ellipse cx="154" cy="118" rx="16" ry="12"/>'
                    '<path d="M176,76 A22,22 0 0 1 176,100" opacity=".7"/>'),
}
SYMB = ('<rect x="2.5" y="2.5" width="4.5" height="4.5" rx=".8"/><rect x="9" y="2.5" width="4.5" height="4.5" rx=".8"/>'
        '<rect x="2.5" y="9" width="4.5" height="4.5" rx=".8"/><path d="M11.2,8.8 L12,11 L14.2,11.8 L12,12.6 L11.2,14.8 L10.4,12.6 L8.2,11.8 L10.4,11 Z"/>')


def main():
    apps = OUT / 'scalable/apps'
    sym = OUT / 'symbolic/apps'
    apps.mkdir(parents=True, exist_ok=True)
    sym.mkdir(parents=True, exist_ok=True)
    for name, (way, body) in GLYPHS.items():
        (apps / f'{name}.svg').write_text(mi.icon_svg(name, way, body))
    (sym / 'amerika-studio-symbolic.svg').write_text(mi.symbolic(SYMB))
    print(f'wrote {len(GLYPHS)} app icons and 1 symbolic icon to {OUT}')


if __name__ == '__main__':
    main()
