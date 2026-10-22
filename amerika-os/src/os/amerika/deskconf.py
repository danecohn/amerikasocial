"""Desktop-parity settings: defaults, validation and storage (inside settings.json, so the shell's file monitor sees changes).

The Settings app should call the wrappers in system.py (documented in docs/DESKTOP-APIS.md); the shell reads through `get`.
"""
import copy

from . import common

HOT_ACTIONS = ('none', 'overview', 'show-desktop', 'launcher', 'switcher', 'screenshot', 'clipboard', 'calendar', 'lock',
               'next-desktop', 'previous-desktop')
CORNERS = ('topleft', 'topright', 'bottomleft', 'bottomright')
TOUCH_EDGES = ('left', 'right', 'top', 'bottom')
FOCUS_POLICIES = ('click', 'follow', 'follow-strict')

DEFAULTS = {
    'desktop': {
        'switcher': {'group_apps': False, 'thumbnails': True, 'all_desktops': True, 'include_minimized': True},
        'hot_corners': {'topleft': 'overview', 'topright': 'none', 'bottomleft': 'none', 'bottomright': 'show-desktop'},
        'touch_edges': {'left': 'none', 'right': 'none', 'top': 'none', 'bottom': 'none'},
        'focus_policy': 'click',
        'desktop_animation': True,
        'snap_gaps': 0,
        'quick_tile': True,
        'clipboard': {'enabled': True, 'max_items': 50, 'max_item_bytes': 1 << 20, 'max_image_bytes': 8 << 20, 'persist': False,
                      'skip_passwords': True},
        'screenshot': {'dir': '', 'copy': True, 'notify': True, 'annotate': False, 'delay': 0, 'include_cursor': False},
        'osd': {'enabled': True, 'timeout_ms': 1400},
        'lock': {'enabled': False, 'on_suspend': True, 'idle_minutes': 0, 'grace_seconds': 0},
        'idle': {'dim_after': 0, 'dim_level': 30, 'screen_off_after': 0, 'suspend_after': 0},
        'night_light': {'enabled': False, 'mode': 'automatic', 'temperature': 4500, 'evening': '20:00', 'morning': '06:30'},
        'world_clocks': ['UTC'],
        'gestures': {'touchpad_desktops': True, 'touch_edges': False, 'osk': False},
        'per_desktop_wallpaper': {},
    }
}


def _merge(base, over):
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def merged(settings=None):
    """The `desktop` settings with defaults filled in (never mutates the input)."""
    settings = common.load_settings() if settings is None else settings
    return _merge(copy.deepcopy(DEFAULTS['desktop']), settings.get('desktop') or {})


def get(path, settings=None, default=None):
    node = merged(settings)
    for part in path.split('.'):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_value(path, value):
    """Store one value under settings['desktop'] (dotted path) and return the merged settings."""
    settings = common.load_settings()
    node = settings.setdefault('desktop', {})
    parts = path.split('.')
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError('settings path is not a table: ' + path)
    node[parts[-1]] = value
    common.save_settings(settings)
    return merged(settings)


def validate_hot_corner(corner, action):
    if corner not in CORNERS:
        raise ValueError('corner must be one of ' + ', '.join(CORNERS))
    if action not in HOT_ACTIONS:
        raise ValueError('action must be one of ' + ', '.join(HOT_ACTIONS))


def validate_touch_edge(edge, action):
    if edge not in TOUCH_EDGES:
        raise ValueError('edge must be one of ' + ', '.join(TOUCH_EDGES))
    if action not in HOT_ACTIONS:
        raise ValueError('action must be one of ' + ', '.join(HOT_ACTIONS))


def bridge_config(settings=None, locked=False, release=()):
    """What the KWin bridge script needs: enabled corners/edges, snap gap and the lock flag."""
    from .shell import home  # lazy: the shell package imports this module
    settings = common.load_settings() if settings is None else settings
    conf = merged(settings)
    return {
        'home': dict(home.rules(settings), release=[str(c).lower() for c in release]),
        'locked': bool(locked),
        'corners': {k: v for k, v in conf['hot_corners'].items() if k in CORNERS and v != 'none'},
        'touch_edges': {k: v for k, v in conf['touch_edges'].items() if k in TOUCH_EDGES and v != 'none'},
        'snap_gaps': max(0, min(64, int(conf.get('snap_gaps') or 0))),
    }
