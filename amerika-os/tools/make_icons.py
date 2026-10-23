#!/usr/bin/env python3
"""Generates the AltStack Desktop icon theme: retro-futurist "horizon cartridge" app icons and symbolic panel icons.

Every app icon is a chrome-rimmed glass tile with a neon-lit glyph, a perspective grid and a setting sun, in its
own colourway. Output: src/os/icons/AmerikaOS/{index.theme,scalable/apps/*.svg,scalable/status/*.svg}
and a contact sheet (dist/icons-preview.png) rendered through gdk-pixbuf.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'src/os/icons/AmerikaOS'

# ---------------------------------------------------------------- colourways (sky top, sky bottom, neon, hot core, sun)
WAYS = {
    'crimson': ('#2a0f24', '#0d0714', '#ff2e63', '#ffd1dc', '#ff7a45'),
    'cyan':    ('#0c2233', '#070b17', '#19e3ff', '#d6fbff', '#ff3d9a'),
    'violet':  ('#1d1240', '#0a0718', '#9b6bff', '#e8dcff', '#ff4f8b'),
    'amber':   ('#2d1a0c', '#0e0810', '#ffb02e', '#fff0cf', '#ff3d6e'),
    'phosphor': ('#082414', '#040a0a', '#39ff88', '#dcffe9', '#19e3ff'),
    'magenta': ('#2a0c30', '#0c0716', '#ff3df0', '#ffd6fb', '#ffb02e'),
    'silver':  ('#1a2030', '#080a12', '#9fd0ff', '#f2f8ff', '#ff3d6e'),
    'orange':  ('#2e130c', '#0e0710', '#ff7a2e', '#ffe2cf', '#ff2e63'),
}


def defs(uid, way):
    sky_top, sky_bot, neon, core, sun = WAYS[way]
    return f'''<defs>
  <linearGradient id="rim{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fbfbff"/><stop offset=".45" stop-color="#7c7c98"/><stop offset=".55" stop-color="#cfcfe4"/><stop offset="1" stop-color="#55556e"/></linearGradient>
  <linearGradient id="sky{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{sky_top}"/><stop offset="1" stop-color="{sky_bot}"/></linearGradient>
  <linearGradient id="sun{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{core}"/><stop offset=".5" stop-color="{sun}"/><stop offset="1" stop-color="{neon}"/></linearGradient>
  <radialGradient id="halo{uid}" cx=".5" cy=".62" r=".6"><stop offset="0" stop-color="{neon}" stop-opacity=".55"/><stop offset="1" stop-color="{neon}" stop-opacity="0"/></radialGradient>
  <linearGradient id="gloss{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".30"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="floor{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{neon}" stop-opacity=".30"/><stop offset="1" stop-color="{sky_bot}" stop-opacity="0"/></linearGradient>
  <clipPath id="clip{uid}"><rect x="14" y="14" width="228" height="228" rx="50"/></clipPath>
  <filter id="glow{uid}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="7"/></filter>
  <filter id="soft{uid}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="2.2"/></filter>
</defs>'''


def scene(uid, way, sun=True):
    """Background: sky, halo, half sun with cut stripes, horizon, perspective grid."""
    _, _, neon, _, _ = WAYS[way]
    hz = 168
    lines = []
    for i in range(-6, 7):  # converging verticals
        x2 = 128 + i * 46
        lines.append(f'<line x1="128" y1="{hz}" x2="{x2}" y2="256" stroke="{neon}" stroke-opacity=".38" stroke-width="1.4"/>')
    for k in range(1, 6):  # receding horizontals
        y = hz + (k / 5) ** 1.9 * (256 - hz)
        lines.append(f'<line x1="14" y1="{y:.1f}" x2="242" y2="{y:.1f}" stroke="{neon}" stroke-opacity="{.18 + .05 * k:.2f}" stroke-width="1.3"/>')
    s = f'<g clip-path="url(#clip{uid})"><rect x="14" y="14" width="228" height="228" fill="url(#sky{uid})"/>'
    s += f'<rect x="14" y="14" width="228" height="228" fill="url(#halo{uid})"/>'
    if sun:
        s += f'<clipPath id="above{uid}"><rect x="14" y="14" width="228" height="{hz - 14}"/></clipPath><g clip-path="url(#above{uid})">'
        s += f'<circle cx="128" cy="{hz}" r="62" fill="url(#sun{uid})" opacity=".9"/>'
        for i in range(5):
            y = hz - 50 + i * 10
            s += f'<rect x="60" y="{y}" width="136" height="{1.6 + i * 1.5:.1f}" fill="{WAYS[way][1]}"/>'
        s += '</g>'
    s += f'<rect x="14" y="{hz}" width="228" height="90" fill="url(#floor{uid})"/>'
    s += ''.join(lines)
    s += f'<line x1="14" y1="{hz}" x2="242" y2="{hz}" stroke="{neon}" stroke-width="2" stroke-opacity=".9"/>'
    s += f'<ellipse cx="96" cy="34" rx="104" ry="52" fill="url(#gloss{uid})" transform="rotate(-18 96 34)"/>'
    s += '</g>'
    return s


def frame(uid):
    return (f'<rect x="5" y="5" width="246" height="246" rx="58" fill="none" stroke="url(#rim{uid})" stroke-width="6"/>'
            f'<rect x="11" y="11" width="234" height="234" rx="53" fill="none" stroke="#000" stroke-opacity=".55" stroke-width="2"/>'
            f'<rect x="8" y="8" width="240" height="240" rx="56" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1"/>')


def neon_shape(uid, way, body, width=9):
    """Glyph drawn three times: wide blurred neon, crisp neon, hot core."""
    _, _, neon, core, _ = WAYS[way]
    return (f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">'
            f'<g filter="url(#glow{uid})" stroke="{neon}" stroke-width="{width + 8}" opacity=".95">{body}</g>'
            f'<g stroke="{neon}" stroke-width="{width}">{body}</g>'
            f'<g stroke="{core}" stroke-width="{width * 0.38:.1f}">{body}</g></g>')


def icon_svg(name, way, body, width=9, sun=True):
    uid = name.replace('-', '')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">'
            f'{defs(uid, way)}<rect x="14" y="14" width="228" height="228" rx="50" fill="#05040a"/>'
            f'{scene(uid, way, sun)}{neon_shape(uid, way, body, width)}{frame(uid)}</svg>\n')


# ---------------------------------------------------------------- glyph bodies (centre 128,112 area)
def poly(points, close=True):
    d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in points)
    return f'<path d="{d}{"Z" if close else ""}"/>'


def gear(cx, cy, r_out, r_in, teeth=8, hole=18):
    pts = []
    for i in range(teeth * 4):
        a = i * math.pi * 2 / (teeth * 4)
        phase = i % 4
        r = r_out if phase in (1, 2) else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts) + f'<circle cx="{cx}" cy="{cy}" r="{hole}"/>'


def sparkle(cx, cy, r, inner=.28):
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rad = r if i % 2 == 0 else r * inner
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return poly(pts)


GLYPHS = {
    # Social: a triangle of linked nodes inside an orbit ring
    'amerika-social': ('crimson', '<circle cx="128" cy="108" r="58" opacity=".55"/>'
                       '<path d="M128,76 L92,134 L164,134 Z"/><circle cx="128" cy="76" r="11"/><circle cx="92" cy="134" r="11"/><circle cx="164" cy="134" r="11"/>'),
    # Venture: globe with meridians and a tilted orbit
    'amerika-venture': ('cyan', '<circle cx="128" cy="108" r="50"/><ellipse cx="128" cy="108" rx="21" ry="50"/>'
                        '<path d="M80,92 H176 M80,126 H176"/><ellipse cx="128" cy="108" rx="74" ry="22" transform="rotate(-22 128 108)" opacity=".7"/>'),
    # Office: stacked page, folded corner, chart bars
    'amerika-office': ('violet', '<path d="M92,52 H146 L172,78 V160 H92 Z"/><path d="M146,52 V78 H172"/>'
                       '<path d="M108,142 V124 M128,142 V106 M148,142 V116"/>'),
    # Files: folder with tab
    'amerika-files': ('amber', '<path d="M70,70 H112 L124,86 H186 V152 H70 Z"/><path d="M70,100 H186" opacity=".7"/>'),
    # Terminal: CRT screen with prompt
    'amerika-terminal': ('phosphor', '<rect x="66" y="64" width="124" height="92" rx="14"/><path d="M92,92 L112,108 L92,124"/><path d="M124,126 H154"/>'),
    # Text: pencil over lines
    'amerika-text': ('magenta', '<path d="M76,78 H150 M76,102 H130 M76,126 H112"/><path d="M178,70 L196,88 L150,148 L128,152 L132,130 Z"/><path d="M168,80 L186,98" opacity=".7"/>'),
    # Settings: gear
    'amerika-settings': ('silver', gear(128, 108, 54, 40, 8, 17)),
    # Software: cartridge/box with arrow
    'amerika-software': ('orange', '<path d="M128,56 L180,82 V138 L128,164 L76,138 V82 Z"/><path d="M76,82 L128,108 L180,82 M128,108 V164"/>'),
    # Home / Hub: sunburst
    'amerika-home': ('crimson', '<path d="M76,142 A52,52 0 0 1 180,142"/><path d="M128,60 V80 M78,80 L92,94 M178,80 L164,94 M62,118 H82 M194,118 H174"/><path d="M70,150 H186"/>'),
    # Ask AI: big sparkle + small sparkle
    'amerika-ai': ('amber', sparkle(122, 110, 56) + sparkle(178, 64, 16, .3) + sparkle(76, 160, 12, .3)),
    # Claude / ChatGPT launch tiles are the apps' own icons; these are generic stand-ins for the AI cluster
    # Stand-in tiles for the two AI apps in the dock and bar (the apps keep their own window icons)
    'claude-desktop': ('amber', '<path d="M64,76 H192 V138 H128 L100,162 V138 H64 Z"/>' + sparkle(128, 106, 24, .3).replace('<path', '<path fill="none"')),
    'chatgpt': ('phosphor', '<path d="M128,56 L180,86 V146 L128,176 L76,146 V86 Z"/><circle cx="128" cy="116" r="22"/><path d="M128,94 V56 M147,127 L180,146 M109,127 L76,146" opacity=".8"/>'),
    'amerika-assistant': ('violet', '<path d="M64,70 H192 V132 H132 L104,156 V132 H64 Z"/><path d="M92,96 H164 M92,114 H140" opacity=".8"/>'),
    'amerika-notifications': ('magenta', '<path d="M92,132 V96 A36,36 0 0 1 164,96 V132 L176,148 H80 Z"/><path d="M116,160 A12,12 0 0 0 140,160"/>'),
    'amerika-network': ('cyan', '<path d="M62,98 A92,92 0 0 1 194,98"/><path d="M82,120 A62,62 0 0 1 174,120"/><path d="M102,142 A32,32 0 0 1 154,142"/><circle cx="128" cy="160" r="5"/>'),
    'amerika-sound': ('amber', '<path d="M72,96 H98 L130,68 V148 L98,120 H72 Z"/><path d="M150,92 A26,26 0 0 1 150,124"/><path d="M164,76 A48,48 0 0 1 164,140"/>'),
    'amerika-display': ('silver', '<rect x="62" y="64" width="132" height="86" rx="10"/><path d="M104,166 H152 M128,150 V166"/>'),
    'amerika-power': ('crimson', '<path d="M128,62 V118"/><path d="M96,84 A52,52 0 1 0 160,84"/>'),
}

# friendly desktop-file icon aliases (some desktop entries use other names)
ALIASES = {
    'amerika-hub': 'amerika-home', 'system-file-manager': 'amerika-files', 'utilities-terminal': 'amerika-terminal',
    'accessories-text-editor': 'amerika-text', 'preferences-system': 'amerika-settings', 'org.amerika.Settings': 'amerika-settings',
    'org.amerika.Shell': 'amerika-home', 'preferences-desktop-notification': 'amerika-notifications',
}

# ---------------------------------------------------------------- symbolic panel icons (foreground colour #bebebe is recoloured by GTK)
SYMB = {
    'wifi': '<path d="M2,6 A10,10 0 0 1 14,6 M4,9 A6.5,6.5 0 0 1 12,9 M6,12 A3,3 0 0 1 10,12" /><circle cx="8" cy="14" r="1"/>',
    'volume': '<path d="M2,6 H5 L9,3 V13 L5,10 H2 Z"/><path d="M11,6 A3,3 0 0 1 11,10 M13,4 A6,6 0 0 1 13,12"/>',
    'battery': '<rect x="1.5" y="4.5" width="11" height="7" rx="1.2"/><path d="M14,7 V9"/><rect x="3" y="6" width="6" height="4" fill="#bebebe"/>',
    'power': '<path d="M8,2 V8 M4.5,4.3 A5.5,5.5 0 1 0 11.5,4.3"/>',
    'bluetooth': '<path d="M4,5 L12,11 L8,14 V2 L12,5 L4,11"/>',
    'bell': '<path d="M4,11 V7 A4,4 0 0 1 12,7 V11 L13.5,12.5 H2.5 Z M6.5,14 A1.5,1.5 0 0 0 9.5,14"/>',
    'brightness': '<circle cx="8" cy="8" r="3"/><path d="M8,1.5 V3 M8,13 V14.5 M1.5,8 H3 M13,8 H14.5 M3.4,3.4 L4.5,4.5 M11.5,11.5 L12.6,12.6 M3.4,12.6 L4.5,11.5 M11.5,4.5 L12.6,3.4"/>',
    'search': '<circle cx="7" cy="7" r="4.5"/><path d="M10.5,10.5 L14,14"/>',
    'grid': '<rect x="2" y="2" width="4.5" height="4.5" rx=".8"/><rect x="9.5" y="2" width="4.5" height="4.5" rx=".8"/><rect x="2" y="9.5" width="4.5" height="4.5" rx=".8"/><rect x="9.5" y="9.5" width="4.5" height="4.5" rx=".8"/>',
    'ai': '<path d="M8,1.5 L9.6,6.4 L14.5,8 L9.6,9.6 L8,14.5 L6.4,9.6 L1.5,8 L6.4,6.4 Z"/>',
    'lock': '<rect x="3" y="7" width="10" height="7" rx="1.4"/><path d="M5,7 V5 A3,3 0 0 1 11,5 V7"/>',
    'logout': '<path d="M6,2.5 H3 V13.5 H6 M7,8 H14 M11.5,5.5 L14,8 L11.5,10.5"/>',
    'settings': '<circle cx="8" cy="8" r="2.4"/><path d="M8,1.5 V3.2 M8,12.8 V14.5 M1.5,8 H3.2 M12.8,8 H14.5 M3.4,3.4 L4.6,4.6 M11.4,11.4 L12.6,12.6 M3.4,12.6 L4.6,11.4 M11.4,4.6 L12.6,3.4"/>',
    'stop': '<rect x="3.5" y="3.5" width="9" height="9" rx="1.5"/>',
    'check': '<path d="M3,8.5 L6.5,12 L13,4.5"/>',
    'close': '<path d="M3.5,3.5 L12.5,12.5 M12.5,3.5 L3.5,12.5"/>',
    'shield': '<path d="M8,1.8 L13.2,3.8 V8 C13.2,11 10.8,13.2 8,14.4 C5.2,13.2 2.8,11 2.8,8 V3.8 Z"/>',
    'eye': '<path d="M1.5,8 C3.5,4.5 12.5,4.5 14.5,8 C12.5,11.5 3.5,11.5 1.5,8 Z"/><circle cx="8" cy="8" r="2"/>',
    'folder': '<path d="M2,4 H6.2 L7.6,5.6 H14 V12.5 H2 Z"/>',
    'moon': '<path d="M12.5,10.5 A5.5,5.5 0 1 1 6,3 A4.5,4.5 0 0 0 12.5,10.5 Z"/>',
    'plug': '<path d="M6,2 V5 M10,2 V5 M4.5,5 H11.5 V8 A3.5,3.5 0 0 1 4.5,8 Z M8,11.5 V14.5"/>',
}


def symbolic(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<g fill="none" stroke="#bebebe" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>\n')


INDEX = '''[Icon Theme]
Name=AltStack Desktop
Comment=AltStack Desktop retro-futurist icon theme
Inherits=Adwaita,hicolor
Directories=scalable/apps,scalable/status

[scalable/apps]
Size=256
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications

[scalable/status]
Size=16
MinSize=8
MaxSize=64
Type=Scalable
Context=Status
'''


def main():
    apps = OUT / 'scalable/apps'
    status = OUT / 'scalable/status'
    apps.mkdir(parents=True, exist_ok=True)
    status.mkdir(parents=True, exist_ok=True)
    for name, (way, body) in GLYPHS.items():
        (apps / f'{name}.svg').write_text(icon_svg(name, way, body))
    for alias, target in ALIASES.items():
        link = apps / f'{alias}.svg'
        link.unlink(missing_ok=True)
        link.write_text((apps / f'{target}.svg').read_text())
    for name, body in SYMB.items():
        (status / f'amerika-{name}-symbolic.svg').write_text(symbolic(body))
    (OUT / 'index.theme').write_text(INDEX)
    print(f'wrote {len(GLYPHS)} app icons, {len(ALIASES)} aliases, {len(SYMB)} symbolic icons to {OUT}')
    if '--preview' in sys.argv:
        preview(Path(sys.argv[sys.argv.index('--preview') + 1]))


def preview(path):
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf
    from PIL import Image
    names = list(GLYPHS)
    cell, cols = 200, 5
    rows = math.ceil(len(names) / cols)
    sheet = Image.new('RGBA', (cols * cell + 20, rows * cell + 20), (13, 13, 19, 255))
    for i, n in enumerate(names):
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(OUT / f'scalable/apps/{n}.svg'), cell - 20, cell - 20)
        data = pb.save_to_bufferv('png', [], [])[1]
        import io
        im = Image.open(io.BytesIO(data)).convert('RGBA')
        sheet.alpha_composite(im, (10 + (i % cols) * cell, 10 + (i // cols) * cell))
    sheet.convert('RGB').save(path)
    print('preview ->', path)


if __name__ == '__main__':
    main()
