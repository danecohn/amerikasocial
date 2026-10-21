"""One-time look and feel for the Amerika session: window buttons and effects (KWin), the colour scheme, and GTK colours.

Run at the start of every session; it only acts once per version (marker in ~/.local/state/amerika-os).
kwinrc and kdeglobals are shared with other KDE sessions on the same account, so only the keys below are touched.
"""
import configparser
import os
import subprocess
import sys
from pathlib import Path

from . import common

VERSION = '3.0.1-1'
SCHEME = Path(os.environ.get('AMERIKA_SCHEMES', '/usr/share/color-schemes')) / 'AmerikaRetro.colors'
KWIN_KEYS = [
    ('kwinrc', 'org.kde.kdecoration2', 'ButtonsOnLeft', 'XIA'),
    ('kwinrc', 'org.kde.kdecoration2', 'ButtonsOnRight', ''),
    ('kwinrc', 'org.kde.kdecoration2', 'library', 'org.kde.breeze'),
    ('kwinrc', 'org.kde.kdecoration2', 'theme', 'Breeze'),
    ('kwinrc', 'Windows', 'FocusPolicy', 'ClickToFocus'),
    ('kwinrc', 'Windows', 'BorderlessMaximizedWindows', 'false'),
    ('kwinrc', 'Plugins', 'blurEnabled', 'true'),
    ('kwinrc', 'Plugins', 'magiclampEnabled', 'true'),
    ('kwinrc', 'Plugins', 'overviewEnabled', 'true'),
    ('kwinrc', 'Plugins', 'slidingpopupsEnabled', 'true'),
    ('kwinrc', 'Plugins', 'fadingpopupsEnabled', 'true'),
    ('kwinrc', 'Plugins', 'wobblywindowsEnabled', 'false'),
    ('kwinrc', 'Plugins', 'squashEnabled', 'false'),
    ('kwinrc', 'Desktops', 'Number', '2'),
    ('kwinrc', 'Effect-overview', 'BorderActivate', '9'),
    ('kdeglobals', 'General', 'ColorScheme', 'AmerikaRetro'),
    ('kdeglobals', 'Icons', 'Theme', 'AmerikaOS'),
    ('kdeglobals', 'KDE', 'widgetStyle', 'Breeze'),
]
GTK_MARK_START = '/* >>> amerika-os (managed) >>> */'
GTK_MARK_END = '/* <<< amerika-os (managed) <<< */'
GTK_CSS = f'''{GTK_MARK_START}
@define-color accent_bg_color #ff2e63;
@define-color accent_color #ff5d85;
@define-color window_bg_color #0b0a14;
@define-color view_bg_color #0f0e18;
@define-color headerbar_bg_color #14131f;
@define-color card_bg_color #1a1928;
@define-color popover_bg_color #1a1928;
{GTK_MARK_END}
'''


def kwrite(file, group, key, value):
    argv = ['kwriteconfig6', '--file', file]
    for g in group.split(']['):
        argv += ['--group', g]
    subprocess.run(argv + ['--key', key, value], check=False, timeout=10)


def apply_scheme():
    if not SCHEME.is_file():
        return
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(SCHEME)
    for section in parser.sections():
        for key, value in parser.items(section):
            kwrite('kdeglobals', section, key, value)


def apply_gtk():
    for version in ('gtk-3.0', 'gtk-4.0'):
        path = Path.home() / '.config' / version / 'gtk.css'
        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text() if path.exists() else ''
        if GTK_MARK_START in text:
            start, end = text.index(GTK_MARK_START), text.index(GTK_MARK_END) + len(GTK_MARK_END)
            text = text[:start] + text[end:]
        path.write_text(text.rstrip('\n') + ('\n\n' if text.strip() else '') + GTK_CSS)


def reconfigure_kwin():
    subprocess.run(['busctl', '--user', 'call', 'org.kde.KWin', '/KWin', 'org.kde.KWin', 'reconfigure'], check=False, timeout=10)


def run(force=False):
    marker = common.STATE / 'first-run'
    if not force and marker.exists() and marker.read_text().strip() == VERSION:
        return False
    for file, group, key, value in KWIN_KEYS:
        kwrite(file, group, key, value)
    apply_scheme()
    apply_gtk()
    reconfigure_kwin()
    common.STATE.mkdir(parents=True, exist_ok=True)
    marker.write_text(VERSION)
    return True


def main():
    run(force='--force' in sys.argv)


if __name__ == '__main__':
    main()
