#!/usr/bin/python3
"""Renders the Amerika OS Plymouth boot theme images (logo + wordmark, neon throbber) into src/os/boot/amerika."""
import math
from pathlib import Path

import gi
from PIL import Image, ImageDraw, ImageFilter, ImageFont

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'src/os/boot/amerika'
LOGO = ROOT / 'src/os/login/amerika/assets/logo.svg'
OUT.mkdir(parents=True, exist_ok=True)


def logo(px):
    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(LOGO), px, px)
    return Image.frombytes('RGBA', (pb.get_width(), pb.get_height()), pb.get_pixels()) if pb.get_has_alpha() else \
        Image.frombytes('RGB', (pb.get_width(), pb.get_height()), pb.get_pixels()).convert('RGBA')


def font(size):
    for p in ('/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf', '/usr/share/fonts/truetype/inter/Inter-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# watermark: glowing logo tile above the wordmark
W, H = 640, 400
img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((W / 2 - 150, 0, W / 2 + 150, 300), fill=(255, 46, 99, 110))
img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
mark = logo(240)
img.alpha_composite(mark, (W // 2 - mark.width // 2, 20))
d = ImageDraw.Draw(img)
f = font(44)
text = 'A M E R I K A   O S'
w = d.textlength(text, font=f)
d.text(((W - w) / 2, 310), text, font=f, fill=(244, 242, 251, 255))
img.save(OUT / 'watermark.png')

# throbber: 60 frames, a neon arc chasing round a faint ring
S = 96
for n in range(60):
    big = Image.new('RGBA', (S * 4, S * 4), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    box = (S * 4 * 0.12, S * 4 * 0.12, S * 4 * 0.88, S * 4 * 0.88)
    g.ellipse(box, outline=(255, 255, 255, 40), width=S // 6 * 1)
    start = n * 6
    for i in range(36):
        a = start - i * 3
        t = 1 - i / 36
        col = (int(25 + 230 * (1 - t)), int(227 - 180 * (1 - t)), int(255 - 156 * (1 - t)), int(255 * t))
        g.arc(box, a - 3, a + 1, fill=col, width=S // 6 * 1)
    big.resize((S, S), Image.LANCZOS).save(OUT / f'throbber-{n + 1:04d}.png')
print('wrote', OUT)
