#!/usr/bin/env python3
"""Generates the AmerikaTesla icon theme: smoked-glass squircle app icons with one luminous accent-coloured glyph each (Tesla touch-screen
meets macOS). Reuses the glyph geometry of tools/make_icons.py and tools/make_studio_icons.py so every app keeps its identity.
Output: src/os/icons/AmerikaTesla/{index.theme,scalable/apps/*.svg} and a contact sheet with --preview PATH."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_icons as mi  # noqa: E402
import make_studio_icons as ms  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'src/os/icons/AmerikaTesla'

# colourway -> (top, bottom): saturated but matte, no glow
TONES = {
    'crimson': ('#ff6a6f', '#d92b33'), 'cyan': ('#52c7ff', '#2169e6'), 'violet': ('#9486ff', '#5340d9'),
    'amber': ('#ffbe4d', '#f2801a'), 'phosphor': ('#4fd98f', '#15955c'), 'magenta': ('#ff74dc', '#c63ab8'),
    'silver': ('#b5bfce', '#626c7c'), 'orange': ('#ffa159', '#e45c1d'), 'graphite': ('#4a4e59', '#22252b'),
}
# a few apps read better in another tone than the retro set used
TONE_OVERRIDE = {'amerika-settings': 'graphite', 'amerika-terminal': 'graphite', 'amerika-display': 'graphite', 'amerika-files': 'cyan',
                 'amerika-text': 'amber', 'amerika-render': 'orange', 'amerika-sprite': 'magenta', 'amerika-box': 'crimson',
                 'amerika-engine': 'violet', 'amerika-studio': 'graphite', 'amerika-home': 'cyan', 'amerika-software': 'cyan'}


def svg(name, way, body, width=9.5):
    """Smoked-glass tile (graphite, hairline edge, soft top sheen) with one luminous accent-coloured glyph."""
    way = TONE_OVERRIDE.get(name, way)
    if way == 'graphite':
        way = 'silver'
    top, bot = TONES.get(way, TONES['silver'])
    uid = name.replace('-', '').replace('.', '')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256"><defs>'
            f'<linearGradient id="t{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2d3038"/><stop offset="1" stop-color="#101216"/></linearGradient>'
            f'<linearGradient id="h{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="e{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".34"/><stop offset=".4" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#fff" stop-opacity=".12"/></linearGradient>'
            f'<linearGradient id="a{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient>'
            f'<radialGradient id="r{uid}" cx=".5" cy=".55" r=".55"><stop offset="0" stop-color="{top}" stop-opacity=".22"/><stop offset="1" stop-color="{top}" stop-opacity="0"/></radialGradient>'
            f'<filter id="s{uid}" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#000" flood-opacity=".45"/></filter>'
            f'<filter id="b{uid}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="7"/></filter></defs>'
            f'<rect x="12" y="10" width="232" height="232" rx="64" fill="url(#t{uid})" filter="url(#s{uid})"/>'
            f'<rect x="12" y="10" width="232" height="232" rx="64" fill="url(#r{uid})"/>'
            f'<rect x="12" y="10" width="232" height="116" rx="64" fill="url(#h{uid})"/>'
            f'<rect x="13" y="11" width="230" height="230" rx="63" fill="none" stroke="url(#e{uid})" stroke-width="1.6"/>'
            f'<g transform="translate(128,130) scale(1.1) translate(-128,-110)" fill="none" stroke-linecap="round" stroke-linejoin="round">'
            f'<g stroke="{top}" stroke-width="{width + 7}" opacity=".30" filter="url(#b{uid})">{body}</g>'
            f'<g stroke="url(#a{uid})" stroke-width="{width}">{body}</g></g></svg>\n')


INDEX = '''[Icon Theme]
Name=Amerika Tesla
Comment=Amerika OS matte app icons
Inherits=AmerikaOS,Adwaita,hicolor
Directories=scalable/apps

[scalable/apps]
Size=256
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications
'''


def all_glyphs():
    g = dict(mi.GLYPHS)
    g.update(ms.GLYPHS)
    g['amerika-agent'] = ('violet', mi.sparkle(122, 110, 56) + mi.sparkle(178, 64, 16, .3) + mi.sparkle(76, 160, 12, .3))
    g['amerika-phone'] = ('cyan', '<rect x="94" y="52" width="68" height="116" rx="14"/><path d="M118,70 H138"/><path d="M110,112 L123,126 L148,98"/>')
    g['amerika-gamedev'] = ('phosphor', '<rect x="84" y="64" width="88" height="88" rx="12"/><path d="M104,64 V50 M128,64 V50 M152,64 V50 M104,152 V166 M128,152 V166 M152,152 V166 M84,92 H70 M84,128 H70 M172,92 H186 M172,128 H186"/><path d="M118,92 L146,108 L118,124 Z"/>')
    g['amerika-claude-skills'] = ('amber', '<path d="M92,76 H116 A14,14 0 1 1 140,76 H164 V100 A14,14 0 1 0 164,124 V148 H92 Z"/>' + mi.sparkle(190, 66, 14, .3))
    return g


def main():
    apps = OUT / 'scalable/apps'
    apps.mkdir(parents=True, exist_ok=True)
    glyphs = all_glyphs()
    ai = ROOT / 'assets/ai-icons'  # an AI-generated PNG replaces the SVG of the same name (see tools/ingest_ai_icons.py)
    have = lambda n: (ai / f'{n}.png').exists()
    for name, (way, body) in glyphs.items():
        target = apps / f'{name}.svg'
        if have(name):
            target.unlink(missing_ok=True)
        else:
            target.write_text(svg(name, way, body))
    for alias, tname in dict(mi.ALIASES, **{'amerika-hub': 'amerika-home'}).items():
        target = apps / f'{alias}.svg'
        if have(tname):
            target.unlink(missing_ok=True)
        else:
            target.write_text(svg(tname, *glyphs[tname]))
    (OUT / 'index.theme').write_text(INDEX)
    print(f'wrote {len(glyphs)} icons + {len(mi.ALIASES)} aliases to {OUT}')
    if '--preview' in sys.argv:
        preview(Path(sys.argv[sys.argv.index('--preview') + 1]), list(glyphs))


def preview(path, names):
    import io
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf
    from PIL import Image
    cell, cols = 170, 6
    rows = math.ceil(len(names) / cols)
    sheet = Image.new('RGBA', (cols * cell + 20, rows * cell + 20), (12, 13, 16, 255))
    for i, n in enumerate(names):
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(OUT / f'scalable/apps/{n}.svg'), cell - 20, cell - 20)
        im = Image.open(io.BytesIO(pb.save_to_bufferv('png', [], [])[1])).convert('RGBA')
        sheet.alpha_composite(im, (10 + (i % cols) * cell, 10 + (i // cols) * cell))
    sheet.convert('RGB').save(path)
    print('preview ->', path)


if __name__ == '__main__':
    main()
