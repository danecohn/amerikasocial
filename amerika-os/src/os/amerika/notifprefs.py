"""Notification preferences and the decision the notification daemon asks for.

Stored in settings.json under "notifications":
  {"dnd": bool, "schedule": {"enabled": bool, "from": "22:00", "to": "07:00"}, "allow_urgent": bool,
   "show_on_lock": bool, "apps": {"<app name>": {"enabled": bool, "banners": bool}}}
`allows(app, urgency, manual_dnd)` is the single function the daemon calls: True means "show a toast".
"""
import json
import re
import time

from . import common

DEFAULT = {'dnd': False, 'schedule': {'enabled': False, 'from': '22:00', 'to': '07:00'}, 'allow_urgent': True, 'show_on_lock': False, 'apps': {}}
TIME_OK = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
SEEN = 'notification-apps.json'


def load():
    cfg = json.loads(json.dumps(DEFAULT))
    stored = common.load_settings().get('notifications') or {}
    for k, v in stored.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def save(cfg):
    s = common.load_settings()
    s['notifications'] = cfg
    common.save_settings(s)
    return cfg


def minutes(text):
    h, m = text.split(':')
    return int(h) * 60 + int(m)


def schedule_active(cfg, now=None):
    """True when the scheduled quiet hours include `now` (a struct_time or datetime-like with tm_hour/tm_min, or None for the clock)."""
    sch = cfg.get('schedule', {})
    if not sch.get('enabled'):
        return False
    t = now or time.localtime()
    cur = t.tm_hour * 60 + t.tm_min
    start, end = minutes(sch['from']), minutes(sch['to'])
    if start == end:
        return False
    return start <= cur < end if start < end else (cur >= start or cur < end)


def allows(app, urgency=1, manual_dnd=False, now=None, cfg=None):
    cfg = cfg or load()
    entry = cfg['apps'].get(app or '', {})
    if entry.get('enabled') is False or entry.get('banners') is False:
        return urgency >= 2 and cfg.get('allow_urgent', True) and entry.get('enabled') is not False
    quiet = manual_dnd or cfg.get('dnd') or schedule_active(cfg, now)
    if quiet:
        return urgency >= 2 and cfg.get('allow_urgent', True)
    return True


def set_dnd(on):
    cfg = load()
    cfg['dnd'] = bool(on)
    return save(cfg)['dnd']


def set_schedule(enabled=None, start=None, end=None):
    cfg = load()
    for key, value in (('from', start), ('to', end)):
        if value is not None:
            if not TIME_OK.match(value):
                raise ValueError('Times look like 22:00.')
            cfg['schedule'][key] = value
    if enabled is not None:
        cfg['schedule']['enabled'] = bool(enabled)
    return save(cfg)['schedule']


def set_option(name, value):
    if name not in ('allow_urgent', 'show_on_lock'):
        raise ValueError('unknown notification option')
    cfg = load()
    cfg[name] = bool(value)
    save(cfg)
    return bool(value)


def set_app(app, enabled=None, banners=None):
    if not app or len(app) > 80 or re.search(r'[\x00-\x1f]', app):
        raise ValueError('Invalid application name.')
    cfg = load()
    entry = cfg['apps'].setdefault(app, {'enabled': True, 'banners': True})
    if enabled is not None:
        entry['enabled'] = bool(enabled)
    if banners is not None:
        entry['banners'] = bool(banners)
    save(cfg)
    return entry


def record_seen(app):
    """Remember which apps have sent notifications, so Settings can list them. Cheap and best-effort."""
    if not app or len(app) > 80:
        return
    try:
        path = common.STATE / SEEN
        seen = json.loads(path.read_text()) if path.exists() else []
        if app not in seen:
            seen.append(app)
            common.STATE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sorted(seen)[:200]))
    except (OSError, ValueError):
        pass


def known_apps():
    cfg = load()
    names = set(cfg['apps'])
    try:
        names.update(json.loads((common.STATE / SEEN).read_text()))
    except (OSError, ValueError):
        pass
    return sorted(names, key=str.lower)
