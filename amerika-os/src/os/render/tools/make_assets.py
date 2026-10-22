#!/usr/bin/env python3
"""Dev-time generator for the Amerika Render icon (SVG) and splash (PNG). Output is committed.

    python3 tools/make_assets.py     (run from src/os/render; needs Pillow for the splash)
"""
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ICON_SRC = HERE.parent / 'icons/AmerikaOS/scalable/apps/amerika-ai.svg'
UID = 'amerikarender'

CUBE = ('M128,48 L182,79 L182,141 L128,172 L74,141 L74,79Z',
        'M74,79 L128,110 L182,79 M128,110 L128,172',
        'M128,48 L128,110')
SPARK = 'M196,44 L200.2,59.8 L216,64 L200.2,68.2 L196,84 L191.8,68.2 L176,64 L191.8,59.8Z'


def icon():
    svg = ICON_SRC.read_text().replace('amerikaai', UID)
    glyph = ''
    for stroke, width, extra in (('#ffb02e', 17, ' filter="url(#glow%s)" opacity=".95"' % UID), ('#ffb02e', 9, ''), ('#fff0cf', 3.4, '')):
        paths = ''.join(f'<path d="{d}"/>' for d in (*CUBE, SPARK))
        glyph += f'<g stroke="{stroke}" stroke-width="{width}"{extra}>{paths}</g>'
    start = svg.index('<g fill="none" stroke-linecap="round" stroke-linejoin="round">')
    end = svg.index('<rect x="5" y="5"')
    svg = svg[:start] + '<g fill="none" stroke-linecap="round" stroke-linejoin="round">' + glyph + '</g>' + svg[end:]
    out = HERE / 'icons/amerika-render.svg'
    out.write_text(svg)
    return out


def splash():
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H, S = 1002, 564, 2
    w, h = W * S, H * S
    img = Image.new('RGB', (w, h), '#0e0810')
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.62)
    for y in range(horizon):  # sky
        t = y / horizon
        c = tuple(int(a + (b - a) * t) for a, b in zip((14, 8, 24), (74, 26, 58)))
        d.line([(0, y), (w, y)], fill=c)
    # sun with scanline cuts
    cx, cy, r = int(w * 0.72), horizon, int(h * 0.34)
    sun = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sun)
    for i in range(r, 0, -2):
        t = i / r
        col = (255, int(61 + (176 - 61) * (1 - t)), int(110 * t + 46 * (1 - t)), 255)
        sd.ellipse([cx - i, cy - i, cx + i, cy + i], fill=col)
    for k in range(8):  # scanline cuts, thicker toward the horizon
        y0 = cy - int(r * 0.72) + int(k * r * 0.095)
        th = int(r * (0.008 + 0.0085 * k))
        sd.rectangle([cx - r, y0, cx + r, y0 + th], fill=(0, 0, 0, 0))
    sun_mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(sun_mask).rectangle([0, 0, w, horizon], fill=255)
    img.paste(sun, (0, 0), Image.composite(sun.split()[3], Image.new('L', (w, h), 0), sun_mask))
    # glow
    glow = Image.new('RGB', (w, h), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - r * 1.5, cy - r * 1.5, cx + r * 1.5, cy + r * 1.5], fill=(90, 30, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(60 * S))
    img = Image.blend(img, Image.composite(Image.new('RGB', (w, h), (255, 176, 46)), img, glow.convert('L').point(lambda p: p // 2)), 0.5)
    d = ImageDraw.Draw(img)
    d.rectangle([0, horizon, w, h], fill='#0e0810')
    # perspective grid floor
    amber = (255, 176, 46)
    vp = (int(w * 0.5), horizon)
    for i in range(-24, 25):
        d.line([vp, (int(vp[0] + i * w * 0.12), h)], fill=(120, 76, 30), width=S)
    y, step = horizon, 4 * S
    while y < h:
        y += step
        step = int(step * 1.32)
        d.line([(0, y), (w, y)], fill=(160, 100, 36), width=S)
    d.line([(0, horizon), (w, horizon)], fill=amber, width=3 * S)
    # neon wireframe cube
    def iso(x, y, z, ox, oy, s):
        return (ox + (x - y) * s * 0.866, oy + (x + y) * s * 0.5 - z * s)
    ox, oy, s = int(w * 0.28), int(h * 0.50), int(h * 0.20)
    v = {(a, b, c): iso(a, b, c, ox, oy, s) for a in (0, 1) for b in (0, 1) for c in (0, 1)}
    edges = [(k1, k2) for k1 in v for k2 in v if sum(abs(a - b) for a, b in zip(k1, k2)) == 1 and k1 < k2]
    lay = Image.new('RGB', (w, h), (0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for a, b in edges:
        ld.line([v[a], v[b]], fill=amber, width=14 * S)
    lay = lay.filter(ImageFilter.GaussianBlur(10 * S))
    img = Image.composite(Image.new('RGB', (w, h), amber), img, lay.convert('L').point(lambda p: min(255, p * 2)).filter(ImageFilter.GaussianBlur(1)))
    d = ImageDraw.Draw(img)
    for a, b in edges:
        d.line([v[a], v[b]], fill=amber, width=7 * S)
        d.line([v[a], v[b]], fill=(255, 240, 207), width=2 * S)
    # text
    def font(size, bold=False):
        for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                  '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()
    d.text((int(w * 0.045), int(h * 0.09)), 'AMERIKA RENDER', font=font(54 * S, True), fill=(255, 240, 207))
    d.text((int(w * 0.047), int(h * 0.09) + 66 * S), 'Talk to Blender. Build 3D worlds with words.', font=font(20 * S), fill=(207, 207, 228))
    d.text((int(w * 0.047), int(h * 0.915)), 'Powered by Blender  -  GPL-3.0-or-later  -  not affiliated with the Blender Foundation', font=font(11 * S), fill=(156, 147, 179))
    # chrome rim
    d.rectangle([0, 0, w - 1, h - 1], outline=(207, 207, 228), width=3 * S)
    img = img.resize((W, H), Image.LANCZOS)
    out = HERE / 'data/splash.png'
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    return out


if __name__ == '__main__':
    print(icon())
    print(splash())
