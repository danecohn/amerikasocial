"""Boot splash for new projects: neon sun over a perspective grid, drawn with PIL (or Qt/pure-python fallback)."""
import struct
import zlib
from pathlib import Path


def _png_fallback(path, w, h):
    rows = []
    for y in range(h):
        t = y / h
        r, g, b = int(248 - 17 * t), int(250 - 13 * t), int(252 - 9 * t)
        rows.append(b'\x00' + bytes([r, g, b]) * w)
    raw = b''.join(rows)
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def make_splash(path, title='Engine', w=640, h=360):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _png_fallback(path, w, h)
        return path
    image = Image.new('RGB', (w,h), '#e7edf3')
    draw = ImageDraw.Draw(image)
    logo = Image.open(next(p for p in [Path(__file__).resolve().parents[1] / 'icons/altstack-logo.png', Path('/usr/share/amerika-engine/icons/altstack-logo.png')] if p.exists())).convert('RGBA')
    logo.thumbnail((int(h*.48),int(h*.48)), Image.Resampling.LANCZOS)
    image.paste(logo, ((w-logo.width)//2,int(h*.12)), logo)
    label = 'AltStack ' + title.removeprefix('AltStack ')
    draw.text((w//2-len(label)*3, int(h*.72)),label,fill='#233649')
    draw.text((w//2-100,h-24),'Powered by the Godot Engine (MIT)',fill='#51677c')
    image.save(path)
    return path
