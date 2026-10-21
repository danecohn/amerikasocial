#!/usr/bin/env python3
"""Generate the Amerika OS GRUB theme assets in flavor/branding/grub-theme.

    python3 flavor/tools/make_grub_theme.py [--no-fonts]

The theme is shipped by amerika-branding in /usr/share/grub/themes/amerika but is NEVER enabled automatically; see
docs/FLAVOR.md ("GRUB theme") for the opt-in steps. Pillow is required; grub-mkfont (grub-common) is used for the
.pf2 fonts when available, otherwise theme.txt falls back to GRUB's built-in "Unifont Regular 16".
"""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'flavor/branding/grub-theme'
WALL = ROOT / 'src/os/wallpapers/horizon.png'
INTER = Path('/usr/share/fonts/opentype/inter/InterDisplay-Regular.otf')
INTER_ALT = [Path('/usr/share/fonts/opentype/inter/Inter-Regular.otf'), Path('/usr/share/fonts/truetype/inter/Inter-Regular.ttf')]
MONO = Path('/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf')
PINK, CYAN, INK = (255, 46, 99), (25, 227, 255), (5, 4, 10)


def background(w=1920, h=1080):
    im = Image.open(WALL).convert('RGB').resize((w, h), Image.LANCZOS)
    veil = Image.new('RGB', (w, h), INK)
    return Image.blend(im, veil, 0.55).filter(ImageFilter.GaussianBlur(1.2))


def nine_patch(path, fill, edge, size=24, radius=6):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=fill, outline=edge, width=2)
    im.save(path)


def slices(prefix, fill, edge, size=24, r=6):
    # GRUB styled boxes use <prefix>_c, _n, _s, _e, _w, _ne, _nw, _se, _sw. Cut one rounded rectangle into the nine parts.
    base = Image.new('RGBA', (size * 3, size * 3), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle((0, 0, size * 3 - 1, size * 3 - 1), r, fill=fill, outline=edge, width=2)
    names = {'nw': (0, 0), 'n': (1, 0), 'ne': (2, 0), 'w': (0, 1), 'c': (1, 1), 'e': (2, 1), 'sw': (0, 2), 's': (1, 2), 'se': (2, 2)}
    for name, (cx, cy) in names.items():
        base.crop((cx * size, cy * size, cx * size + size, cy * size + size)).save(OUT / f'{prefix}_{name}.png')


def fonts():
    mkfont = shutil.which('grub-mkfont')
    inter = next((p for p in [INTER] + INTER_ALT if p.exists()), None)
    if not (mkfont and inter and MONO.exists()):
        return False
    for name, src, size in (('inter-18', inter, 18), ('inter-32', inter, 32), ('mono-14', MONO, 14)):
        subprocess.run([mkfont, '-s', str(size), '-o', str(OUT / f'{name}.pf2'), str(src)], check=True, stderr=subprocess.DEVNULL)
    return True


THEME = '''# Amerika OS GRUB theme (retro-futurist). Not enabled automatically.
desktop-image: "background.png"
desktop-color: "#05040a"
title-text: ""
terminal-font: "{mono}"
terminal-left: "8%"
terminal-top: "8%"
terminal-width: "84%"
terminal-height: "84%"
terminal-border: "0"

+ label {{
  top = 14%
  left = 0
  width = 100%
  align = "center"
  text = "A M E R I K A   O S"
  font = "{big}"
  color = "#19e3ff"
}}

+ boot_menu {{
  left = 25%
  top = 30%
  width = 50%
  height = 44%
  item_font = "{font}"
  item_color = "#cfcfe4"
  selected_item_color = "#ffffff"
  item_height = 38
  item_padding = 8
  item_spacing = 6
  icon_width = 0
  icon_height = 0
  item_icon_space = 0
  menu_pixmap_style = "menu_*.png"
  selected_item_pixmap_style = "select_*.png"
  scrollbar = false
}}

+ progress_bar {{
  id = "__timeout__"
  left = 25%
  top = 78%
  width = 50%
  height = 14
  show_text = false
  bar_style = "progress_bar_*.png"
  highlight_style = "progress_highlight_*.png"
}}

+ label {{
  id = "__timeout__"
  top = 82%
  left = 0
  width = 100%
  align = "center"
  text = "Booting in %d seconds"
  font = "{font}"
  color = "#7c7c98"
}}

+ label {{
  top = 94%
  left = 0
  width = 100%
  align = "center"
  text = "Enter: boot    e: edit    c: command line"
  font = "{font}"
  color = "#7c7c98"
}}
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    background().save(OUT / 'background.png', optimize=True)
    slices('menu', (10, 9, 20, 200), (58, 57, 80, 255))
    slices('select', (255, 46, 99, 70), CYAN + (255,))
    slices('progress_bar', (26, 25, 48, 255), (58, 57, 80, 255), size=7, r=3)
    slices('progress_highlight', CYAN + (255,), CYAN + (255,), size=7, r=3)
    have = '--no-fonts' not in sys.argv and fonts()
    names = ('Inter Display Regular 18', 'Inter Display Regular 32', 'JetBrains Mono Regular 14') if have else ('Unifont Regular 16',) * 3
    (OUT / 'theme.txt').write_text(THEME.format(font=names[0], big=names[1], mono=names[2]))
    print('GRUB theme written to', OUT, '(custom fonts)' if have else '(built-in font)')


if __name__ == '__main__':
    main()
