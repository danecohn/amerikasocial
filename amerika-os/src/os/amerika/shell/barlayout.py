"""Top bar layout engine: which widgets are shown, where, in which order, and how the clock is formatted. No GTK here."""
import copy
import time

ZONES = ('left', 'center', 'right')

# id -> (title, description)
WIDGETS = {
    'launcher': ('Launcher button', 'The AMERIKA button that opens the app menu'),
    'home': ('Home button', 'Brings the home AI app to the front'),
    'ai_apps': ('AI app buttons', 'Quick buttons for Claude and ChatGPT'),
    'title': ('Active window title', 'Name of the focused app'),
    'pager': ('Desktop pager', 'Virtual desktops'),
    'clock': ('Clock', 'The time'),
    'date': ('Date', 'Day and date'),
    'ai_chip': ('AI activity chip', 'What Claude or ChatGPT is doing, with the Stop switch'),
    'agent_chip': ('Agent chip', 'Amerika Agent state (only when the agent is installed)'),
    'status': ('Status icons', 'Network, volume, battery and quick controls'),
    'tray': ('System tray', 'Status icons of running apps'),
    'bell': ('Notifications bell', 'Notification centre'),
}

# the classic bar, exactly as before the Claude-first work
CLASSIC = [
    ('launcher', True, 'left'), ('home', False, 'left'), ('ai_apps', True, 'left'), ('title', True, 'left'), ('pager', True, 'left'),
    ('date', True, 'center'), ('clock', True, 'center'),
    ('ai_chip', True, 'right'), ('agent_chip', True, 'right'), ('tray', True, 'right'), ('status', True, 'right'), ('bell', True, 'right'),
]
# the home bar: Home button, window title, clock in the middle, AI/status on the right; no AI app buttons or pager
HOME = [
    ('launcher', True, 'left'), ('home', True, 'left'), ('title', True, 'left'), ('ai_apps', False, 'left'), ('pager', False, 'left'),
    ('clock', True, 'center'), ('date', True, 'center'),
    ('ai_chip', True, 'right'), ('agent_chip', True, 'right'), ('tray', True, 'right'), ('status', True, 'right'), ('bell', True, 'right'),
]
PRESETS = {'classic': CLASSIC, 'home': HOME}

CLOCK_DEFAULTS = {'hour24': None, 'seconds': False, 'date': 'short'}   # hour24 None: follow the legacy clock_24h setting
DATE_STYLES = [('none', 'No date'), ('short', 'Sun 21 Oct'), ('long', 'Sunday 21 October 2026'), ('numeric', '2026-10-21')]
DATE_FORMATS = {'short': '%a %d %b', 'long': '%A %d %B %Y', 'numeric': '%Y-%m-%d'}
HEIGHT_MIN, HEIGHT_MAX, HEIGHT_DEFAULT = 28, 64, 36
OPACITY_MIN, OPACITY_MAX = 0.3, 1.0


def preset(name):
    rows = PRESETS.get(name, CLASSIC)
    return [{'id': i, 'enabled': e, 'zone': z, 'order': n} for n, (i, e, z) in enumerate(rows)]


def default_layout():
    return preset('classic')


def normalize(layout):
    """A clean, complete layout: unknown ids dropped, duplicates removed, missing widgets appended (disabled unless the classic
    bar shows them), bad zones fixed, order renumbered per zone. Never raises; garbage in gives the default out."""
    classic = {r['id']: r for r in preset('classic')}
    seen, rows = set(), []
    for entry in layout if isinstance(layout, list) else []:
        if not isinstance(entry, dict):
            continue
        wid = entry.get('id')
        if wid not in WIDGETS or wid in seen:
            continue
        seen.add(wid)
        zone = entry.get('zone') if entry.get('zone') in ZONES else classic[wid]['zone']
        try:
            order = int(entry.get('order'))
        except (TypeError, ValueError):
            order = 1000 + len(rows)
        rows.append({'id': wid, 'enabled': bool(entry.get('enabled', True)), 'zone': zone, 'order': order})
    had_rows = bool(rows)
    for wid, base in classic.items():
        if wid not in seen:
            rows.append({'id': wid, 'enabled': False if had_rows else base['enabled'], 'zone': base['zone'], 'order': 2000 + len(rows)})
    out = []
    for zone in ZONES:
        zrows = sorted((r for r in rows if r['zone'] == zone), key=lambda r: (r['order'], r['id']))
        for n, r in enumerate(zrows):
            out.append({**r, 'order': n})
    return out


def zones(layout):
    """{'left': [ids], 'center': [...], 'right': [...]}: enabled widgets in display order."""
    res = {z: [] for z in ZONES}
    for r in normalize(layout):
        if r['enabled']:
            res[r['zone']].append(r['id'])
    return res


def set_enabled(layout, wid, enabled):
    out = normalize(layout)
    for r in out:
        if r['id'] == wid:
            r['enabled'] = bool(enabled)
    return out


def set_zone(layout, wid, zone):
    if zone not in ZONES:
        raise ValueError('zone must be left, center or right')
    out = normalize(layout)
    for r in out:
        if r['id'] == wid:
            r['zone'] = zone
            r['order'] = 10 ** 6          # to the end of the new zone
    return normalize(out)


def move(layout, wid, delta):
    """Move a widget up (-1) or down (+1) within its zone."""
    out = normalize(layout)
    me = next((r for r in out if r['id'] == wid), None)
    if me is None:
        return out
    peers = sorted((r for r in out if r['zone'] == me['zone']), key=lambda r: r['order'])
    at = peers.index(me)
    to = max(0, min(len(peers) - 1, at + delta))
    peers.insert(to, peers.pop(at))
    for n, r in enumerate(peers):
        r['order'] = n
    return normalize(out)


def clock_format(settings):
    conf = copy.deepcopy(CLOCK_DEFAULTS)
    stored = settings.get('bar_clock_format')
    if isinstance(stored, dict):
        conf.update({k: v for k, v in stored.items() if k in conf})
    if conf['hour24'] is None:
        conf['hour24'] = bool(settings.get('clock_24h'))
    conf['hour24'], conf['seconds'] = bool(conf['hour24']), bool(conf['seconds'])
    if conf['date'] not in dict(DATE_STYLES):
        conf['date'] = 'short'
    return conf


def format_time(conf, now=None, upper=True):
    pattern = ('%H:%M' if conf['hour24'] else '%I:%M') + (':%S' if conf['seconds'] else '') + ('' if conf['hour24'] else ' %p')
    out = time.strftime(pattern, now or time.localtime())
    return out.upper() if upper else out


def format_date(conf, now=None, upper=True):
    pattern = DATE_FORMATS.get(conf['date'])
    if not pattern:
        return ''
    out = time.strftime(pattern, now or time.localtime())
    return out.upper() if upper else out


def height(settings):
    try:
        return max(HEIGHT_MIN, min(HEIGHT_MAX, int(settings.get('bar_height', HEIGHT_DEFAULT))))
    except (TypeError, ValueError):
        return HEIGHT_DEFAULT


def opacity(settings):
    try:
        return max(OPACITY_MIN, min(OPACITY_MAX, float(settings.get('bar_opacity', 1.0))))
    except (TypeError, ValueError):
        return 1.0


def runs(layout_zone_ids):
    """Group a zone's widget ids so a date and a clock that sit next to each other share one button (as in the classic bar).
    Returns a list of tuples of ids."""
    out, ids = [], list(layout_zone_ids)
    i = 0
    while i < len(ids):
        if ids[i] in ('clock', 'date') and i + 1 < len(ids) and ids[i + 1] in ('clock', 'date') and ids[i + 1] != ids[i]:
            out.append((ids[i], ids[i + 1]))
            i += 2
        else:
            out.append((ids[i],))
            i += 1
    return out


def signature(settings):
    """Everything that makes the bar need rebuilding. Equal signature: leave the bar (and open popovers) alone."""
    z = zones(settings.get('bar_layout'))
    conf = clock_format(settings)
    ai = tuple(settings.get('bar_ai_apps', []))
    return (tuple((k, tuple(v)) for k, v in z.items()), conf['hour24'], conf['seconds'], conf['date'], height(settings),
            round(opacity(settings), 2), ai, bool(settings.get('home_mode', 'off') != 'off'), settings.get('ui_style', 'retro'))
