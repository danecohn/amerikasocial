"""One-time look and feel for the Amerika session: window buttons and effects (KWin), the colour scheme, and GTK colours.

Run at the start of every session; it only acts once per version (marker in ~/.local/state/amerika-os).
kwinrc and kdeglobals are shared with other KDE sessions on the same account, so only the keys below are touched.
"""
import configparser
import json
import os
import subprocess
import sys
from pathlib import Path

from . import common

VERSION = '3.0.3-1'
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


# ---- agent-ui: one-time migration that pins Amerika Agent in the dock of existing users
AGENT_DOCK_ID = 'amerika-agent'
AGENT_DOCK_AFTER = ('chatgpt', 'com.anthropic.Claude')


def migrate_dock_agent():
    """Append the Amerika Agent entry to an existing dock_pinned list exactly once (next to the AI apps).
    New users get it from common.DEFAULTS and are only marked as migrated. A user who removes it later keeps it removed."""
    path = common.CONFIG / 'settings.json'
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError):
        stored = {}
    if not isinstance(stored, dict):
        return False
    done = stored.setdefault('migrations', {})
    if not isinstance(done, dict) or done.get('agent_dock'):
        return False
    pinned = stored.get('dock_pinned')
    if isinstance(pinned, list) and AGENT_DOCK_ID not in pinned:
        at = max([pinned.index(i) + 1 for i in AGENT_DOCK_AFTER if i in pinned] or [len(pinned)])
        pinned.insert(at, AGENT_DOCK_ID)
    done['agent_dock'] = True
    common.CONFIG.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('settings.json.tmp')
    tmp.write_text(json.dumps(stored, indent=2))
    tmp.replace(path)
    return True


def migrate_claude_os():
    """Claude-first mode introduces new settings. Their defaults keep today's behaviour (dock shown, no home app), so nothing is
    changed for an existing user; this only records that the one-time opt-in card in Settings has not been answered yet."""
    path = common.CONFIG / 'settings.json'
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError):
        stored = {}
    if not isinstance(stored, dict):
        return False
    done = stored.setdefault('migrations', {})
    if not isinstance(done, dict) or done.get('claude_os'):
        return False
    stored.setdefault('claude_os_prompt', 'pending')
    done['claude_os'] = True
    common.CONFIG.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('settings.json.tmp')
    tmp.write_text(json.dumps(stored, indent=2))
    tmp.replace(path)
    return True


def run(force=False):
    migrate_dock_agent()
    migrate_claude_os()
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
