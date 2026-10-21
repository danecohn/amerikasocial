"""Appearance backend: Amerika's own preferences (settings.json, picked up live by the shell) plus the KDE/GTK keys that
make other applications follow (colour scheme, fonts, icons, cursor, animations)."""
import os
import re
from pathlib import Path

from . import common, sysutil

ACCENTS = {'Crimson': '#ff2e63', 'Cyan': '#19e3ff', 'Magenta': '#ff3df0', 'Amber': '#ffb02e', 'Phosphor': '#39ff88', 'Violet': '#9b6bff'}
SECONDARY = {'#ff2e63': '#19e3ff', '#19e3ff': '#ff2e63', '#ff3df0': '#19e3ff', '#ffb02e': '#19e3ff', '#39ff88': '#ff3df0', '#9b6bff': '#19e3ff'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp')
DOCK_POSITIONS = [('bottom', 'Bottom'), ('left', 'Left'), ('right', 'Right')]
ANIMATION_LEVELS = [('off', 'Off', 0.0), ('fast', 'Fast', 0.5), ('normal', 'Normal', 1.0), ('slow', 'Relaxed', 2.0)]
DARK_SCHEME, LIGHT_SCHEME = 'AmerikaRetro', 'BreezeLight'
GNOME = 'org.gnome.desktop.interface'

DEFAULTS = {'color_mode': 'dark', 'dock_position': 'bottom', 'dock_autohide': False, 'dock_size': 56, 'transparency': 80,
            'animations': 'normal', 'bar_clock_seconds': False, 'bar_show_date': True, 'bar_translucent': True}


def _s():
    return common.load_settings()


def get(key):
    return _s().get(key, DEFAULTS.get(key))


def put(key, value):
    s = _s()
    s[key] = value
    common.save_settings(s)
    return value


# ---------------------------------------------------------------- colours
def check_hex(value):
    if not HEX.match(value or ''):
        raise ValueError('A colour looks like #ff2e63.')
    return value.lower()


def set_accent(value):
    value = check_hex(value)
    s = _s()
    s['accent'] = value
    s['secondary'] = SECONDARY.get(value, s.get('secondary', '#19e3ff'))
    common.save_settings(s)
    # apps built on GTK/Adwaita and KDE pick up the accent too
    sysutil.kwrite('kdeglobals', 'General', 'AccentColor', ','.join(str(int(value[i:i + 2], 16)) for i in (1, 3, 5)))
    return value


def set_color_mode(mode):
    if mode not in ('dark', 'light'):
        raise ValueError('mode must be dark or light')
    scheme = DARK_SCHEME if mode == 'dark' else LIGHT_SCHEME
    if sysutil.have('plasma-apply-colorscheme'):
        sysutil.run(['plasma-apply-colorscheme', scheme], timeout=15)
    else:
        sysutil.kwrite('kdeglobals', 'General', 'ColorScheme', scheme)
    sysutil.gsettings_set(GNOME, 'color-scheme', "'prefer-dark'" if mode == 'dark' else "'prefer-light'")
    return put('color_mode', mode)


# ---------------------------------------------------------------- wallpaper
def user_wallpaper_dirs():
    pictures = Path(os.environ.get('XDG_PICTURES_DIR') or Path.home() / 'Pictures')
    return [pictures / 'Wallpapers', pictures, common.CONFIG / 'wallpapers']


def user_wallpapers(limit=60):
    out = []
    for d in user_wallpaper_dirs():
        try:
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix.lower() in IMAGE_EXT and not p.name.startswith('.'):
                    out.append(str(p))
        except OSError:
            continue
    return out[:limit]


def check_wallpaper(value, builtin):
    if value in builtin:
        return value
    p = Path(value)
    if p.is_absolute() and p.is_file() and p.suffix.lower() in IMAGE_EXT and p.stat().st_size <= 80_000_000:
        return str(p)
    raise ValueError('Choose one of the built-in wallpapers or an image file (PNG, JPEG, WebP).')


def set_wallpaper(value, builtin=('horizon', 'grid', 'dusk')):
    return put('wallpaper', check_wallpaper(value, builtin))


# ---------------------------------------------------------------- fonts
def font_families():
    res = sysutil.run(['fc-list', ':', 'family'], timeout=10)
    names = {line.split(',')[0].strip() for line in res.out.splitlines() if line.strip()}
    return sorted(names, key=str.lower)


def fonts():
    def parse(raw, default):
        parts = (raw or default).split(',')
        try:
            return parts[0], int(float(parts[1]))
        except (IndexError, ValueError):
            return parts[0], 10
    ui = parse(sysutil.kread('kdeglobals', 'General', 'font', ''), 'Inter,10')
    mono = parse(sysutil.kread('kdeglobals', 'General', 'fixed', ''), 'JetBrains Mono,10')
    return {'ui': {'family': ui[0], 'size': ui[1]}, 'mono': {'family': mono[0], 'size': mono[1]}}


def set_font(kind, family, size):
    if kind not in ('ui', 'mono'):
        raise ValueError('font kind must be ui or mono')
    if not re.fullmatch(r'[A-Za-z0-9 ._+\-]{1,60}', family or ''):
        raise ValueError('Invalid font name.')
    size = int(size)
    if not 6 <= size <= 28:
        raise ValueError('Font size must be between 6 and 28.')
    kde = f'{family},{size},-1,5,400,0,0,0,0,0,0,0,0,0,0,1'
    sysutil.kwrite('kdeglobals', 'General', 'font' if kind == 'ui' else 'fixed', kde)
    sysutil.gsettings_set(GNOME, 'font-name' if kind == 'ui' else 'monospace-font-name', f"'{family} {size}'")
    return fonts()


# ---------------------------------------------------------------- icons and cursors
def _theme_dirs():
    return [Path('/usr/share/icons'), Path.home() / '.local/share/icons', Path.home() / '.icons', common.SHARE / 'icons']


def icon_themes():
    found = {}
    for base in _theme_dirs():
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for d in entries:
            index = d / 'index.theme'
            if not index.is_file():
                continue
            text = index.read_text(encoding='utf-8', errors='replace')
            if 'Directories=' in text and 'Hidden=true' not in text and not (d / 'cursors').is_dir():
                m = re.search(r'^Name=(.+)$', text, re.M)
                found[d.name] = (m.group(1) if m else d.name)
    return sorted(found.items(), key=lambda kv: kv[1].lower())


def cursor_themes():
    found = {}
    for base in _theme_dirs():
        try:
            for d in sorted(base.iterdir()):
                if (d / 'cursors').is_dir():
                    found[d.name] = d.name
        except OSError:
            continue
    return sorted(found)


def icon_theme():
    return sysutil.kread('kdeglobals', 'Icons', 'Theme', 'AmerikaOS')


def set_icon_theme(name):
    if not re.fullmatch(r'[A-Za-z0-9_.\-]{1,60}', name or ''):
        raise ValueError('Invalid icon theme.')
    sysutil.kwrite('kdeglobals', 'Icons', 'Theme', name)
    sysutil.gsettings_set(GNOME, 'icon-theme', f"'{name}'")
    return name


def cursor():
    return {'theme': sysutil.kread('kcminputrc', 'Mouse', 'cursorTheme', 'breeze_cursors'),
            'size': int(sysutil.kread('kcminputrc', 'Mouse', 'cursorSize', '24') or 24)}


def set_cursor(theme=None, size=None):
    if theme is not None:
        if not re.fullmatch(r'[A-Za-z0-9_.\-]{1,60}', theme):
            raise ValueError('Invalid cursor theme.')
        sysutil.kwrite('kcminputrc', 'Mouse', 'cursorTheme', theme)
        sysutil.gsettings_set(GNOME, 'cursor-theme', f"'{theme}'")
    if size is not None:
        size = int(size)
        if size not in (16, 24, 32, 36, 48, 64, 96, 128):
            raise ValueError('Cursor size must be one of 16, 24, 32, 36, 48, 64, 96 or 128.')
        sysutil.kwrite('kcminputrc', 'Mouse', 'cursorSize', size)
        sysutil.gsettings_set(GNOME, 'cursor-size', size)
    sysutil.run(['busctl', '--user', 'call', 'org.kde.KWin', '/KWin', 'org.kde.KWin', 'reconfigure'], timeout=10)
    return cursor()


# ---------------------------------------------------------------- animations, transparency
def animation_level():
    s = _s().get('animations')
    return s if s in {k for k, _t, _f in ANIMATION_LEVELS} else 'normal'


def set_animation_level(level):
    factor = {k: f for k, _t, f in ANIMATION_LEVELS}.get(level)
    if factor is None:
        raise ValueError('animations must be off, fast, normal or slow')
    sysutil.kwrite('kdeglobals', 'KDE', 'AnimationDurationFactor', factor)
    sysutil.kwin_reconfigure()
    return put('animations', level)


def set_transparency(percent):
    percent = max(0, min(100, int(percent)))
    sysutil.kwrite('kwinrc', 'Plugins', 'blurEnabled', percent > 0)
    sysutil.kwin_reconfigure()
    return put('transparency', percent)


# ---------------------------------------------------------------- dock and bar (read by the shell from settings.json)
def set_dock(position=None, size=None, autohide=None):
    if position is not None:
        if position not in dict(DOCK_POSITIONS):
            raise ValueError('dock position must be bottom, left or right')
        put('dock_position', position)
    if size is not None:
        size = int(size)
        if not 32 <= size <= 96:
            raise ValueError('dock size must be between 32 and 96')
        put('dock_size', size)
    if autohide is not None:
        put('dock_autohide', bool(autohide))
    return {k: get(k) for k in ('dock_position', 'dock_size', 'dock_autohide')}


def set_bar(**options):
    for key, value in options.items():
        if key not in ('bar_clock_seconds', 'bar_show_date', 'bar_translucent'):
            raise ValueError(f'unknown bar option {key}')
        put(key, bool(value))
    return {k: get(k) for k in ('bar_clock_seconds', 'bar_show_date', 'bar_translucent')}
