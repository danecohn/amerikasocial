#!/usr/bin/env python3
"""Turn AI-generated icon PNGs (assets/ai-icons/<icon-name>.png) into the AmerikaTesla icon theme.

Each PNG must be square (>= 512 px), RGBA, with transparent corners. The script validates, then writes
src/os/icons/AmerikaTesla/<N>x<N>/apps/<name>.png for N in 512, 256, 128, 64, 48 (Lanczos downscale) and adds those
directories to the theme's index.theme. SVG icons stay as the fallback for any name without a PNG.
Usage: tools/ingest_ai_icons.py [FOLDER] [--theme DIR] [--report]"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZES = (512, 256, 128, 64, 48)
NAME_OK = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')


def check(path):
    """-> (ok, message)"""
    name = path.stem
    if not name or set(name) - NAME_OK:
        return False, 'file name must be an icon name (letters, digits, - _ .)'
    try:
        im = Image.open(path)
        im.load()
    except Exception as exc:  # unreadable or not an image
        return False, f'unreadable image: {exc}'
    if im.width != im.height or im.width < 512:
        return False, f'must be square and at least 512 px (got {im.width}x{im.height})'
    im = im.convert('RGBA')
    corners = [im.getpixel(p)[3] for p in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1))]
    if max(corners) > 24:
        return False, 'corners are not transparent: ask for a transparent background (squircle shape on alpha)'
    center = im.getpixel((im.width // 2, im.height // 2))[3]
    if center < 200:
        return False, 'the icon body is not opaque'
    return True, 'ok'


def ingest(folder, theme):
    ok, bad = [], []
    for path in sorted(Path(folder).glob('*.png')):
        good, msg = check(path)
        if not good:
            bad.append((path.name, msg))
            continue
        im = Image.open(path).convert('RGBA')
        for n in SIZES:
            d = Path(theme) / f'{n}x{n}/apps'
            d.mkdir(parents=True, exist_ok=True)
            im.resize((n, n), Image.LANCZOS).save(d / f'{path.stem}.png', optimize=True)
        ok.append(path.stem)
    if ok:
        index = Path(theme) / 'index.theme'
        text = index.read_text()
        lines = text.splitlines()
        dirs_line = next(i for i, l in enumerate(lines) if l.startswith('Directories='))
        have = lines[dirs_line].split('=', 1)[1].split(',')
        for n in SIZES:
            entry = f'{n}x{n}/apps'
            if entry not in have:
                have.append(entry)
                text += f'\n[{entry}]\nSize={n}\nType=Fixed\nContext=Applications\n'
        lines = text.splitlines()
        lines[dirs_line] = 'Directories=' + ','.join(have)
        index.write_text('\n'.join(lines) + '\n')
    return ok, bad


def main(argv):
    folder = ROOT / 'assets/ai-icons'
    theme = ROOT / 'src/os/icons/AmerikaTesla'
    args = list(argv)
    if '--theme' in args:
        i = args.index('--theme')
        theme = Path(args[i + 1])
        del args[i:i + 2]
    args = [a for a in args if not a.startswith('--')]
    if args:
        folder = Path(args[0])
    ok, bad = ingest(folder, theme)
    print(f'ingested {len(ok)} icon(s): ' + ', '.join(ok))
    for name, msg in bad:
        print(f'REJECTED {name}: {msg}')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
