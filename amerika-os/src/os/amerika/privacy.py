"""Privacy & security backend: portal permission store, device-in-use indicators, screen lock, recent files, ufw firewall (read-only status;
enabling goes through pkexec and amerika-settings-helper)."""
import json
import os
from pathlib import Path

from . import audio, common, sysutil
from .bluetooth import _unwrap
from .updates import SETTINGS_HELPER

STORE = ['--user', '-j', 'call', 'org.freedesktop.impl.portal.PermissionStore', '/org/freedesktop/impl/portal/PermissionStore',
         'org.freedesktop.impl.portal.PermissionStore']
RESOURCES = [('devices', 'camera', 'Camera'), ('devices', 'microphone', 'Microphone'), ('location', 'location', 'Location'),
             ('screenshot', 'screenshot', 'Screenshots and screen sharing'), ('background', 'background', 'Run in the background')]
VALUES = ('yes', 'no', 'ask')


def _store(method, *args):
    return sysutil.run(['busctl'] + STORE + [method, *args], timeout=6)


def permissions(table, resource):
    """{app id: 'yes'|'no'|'ask'} for one resource."""
    res = _store('Lookup', 'ss', table, resource)
    if res.code != 0 or not res.out:
        return {}
    try:
        data = _unwrap(json.loads(res.out)['data'][0])
    except (ValueError, KeyError, IndexError):
        return {}
    out = {}
    for app, vals in (data or {}).items():
        v = vals[0] if vals else 'ask'
        out[app] = v if v in VALUES else 'ask'
    return out


def all_permissions():
    out = []
    for table, resource, title in RESOURCES:
        out.append({'table': table, 'resource': resource, 'title': title, 'apps': permissions(table, resource)})
    return out


def set_permission(table, resource, app, value):
    if value not in VALUES:
        raise ValueError('permission must be yes, no or ask')
    if (table, resource) not in {(t, r) for t, r, _n in RESOURCES}:
        raise ValueError('unknown permission')
    if not app or len(app) > 200 or any(c in app for c in '\x00\n'):
        raise ValueError('invalid app id')
    res = _store('SetPermission', 'sbssas', table, 'true', resource, app, '1', value)
    return res.code == 0


def camera_users():
    res = sysutil.run(['pw-dump'], timeout=6)
    if res.code != 0 or not res.out:
        return []
    try:
        nodes = json.loads(res.out)
    except ValueError:
        return []
    names = []
    for n in nodes:
        info = n.get('info', {})
        props = info.get('props', {})
        if n.get('type') == 'PipeWire:Interface:Node' and props.get('media.class') == 'Stream/Input/Video' and info.get('state') == 'running':
            names.append(props.get('application.name') or props.get('node.name') or 'An app')
    return names


def location_in_use():
    res = sysutil.run(['busctl', '--system', 'get-property', 'org.freedesktop.GeoClue2', '/org/freedesktop/GeoClue2/Manager',
                       'org.freedesktop.GeoClue2.Manager', 'InUse'])
    return res.code == 0 and res.out.endswith('true')


def indicators():
    return {'camera': camera_users(), 'microphone': audio.mic_users(), 'location': location_in_use()}


# ---------------------------------------------------------------- screen lock
def lock_settings():
    s = common.load_settings()
    return {'auto_lock': sysutil.kread('kscreenlockerrc', 'Daemon', 'Autolock', 'true') == 'true',
            'timeout_min': int(sysutil.kread('kscreenlockerrc', 'Daemon', 'Timeout', '5') or 5),
            'lock_on_resume': sysutil.kread('kscreenlockerrc', 'Daemon', 'LockOnResume', 'true') == 'true',
            'lock_timeout_min': s.get('lock_timeout_min')}


def set_lock(auto_lock=None, timeout_min=None, lock_on_resume=None):
    s = common.load_settings()
    if auto_lock is not None:
        sysutil.kwrite('kscreenlockerrc', 'Daemon', 'Autolock', bool(auto_lock))
        s['lock_auto'] = bool(auto_lock)
    if timeout_min is not None:
        timeout_min = int(timeout_min)
        if not 1 <= timeout_min <= 240:
            raise ValueError('The lock timeout must be between 1 and 240 minutes.')
        sysutil.kwrite('kscreenlockerrc', 'Daemon', 'Timeout', timeout_min)
        s['lock_timeout_min'] = timeout_min
    if lock_on_resume is not None:
        sysutil.kwrite('kscreenlockerrc', 'Daemon', 'LockOnResume', bool(lock_on_resume))
    common.save_settings(s)
    return lock_settings()


# ---------------------------------------------------------------- recent files
RECENT = 'recently-used.xbel'
EMPTY_XBEL = ('<?xml version="1.0" encoding="UTF-8"?>\n<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks" '
              'xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">\n</xbel>\n')


def recent_enabled():
    return sysutil.gsettings_get('org.gnome.desktop.privacy', 'remember-recent-files', 'true') != 'false'


def set_recent_enabled(on):
    sysutil.gsettings_set('org.gnome.desktop.privacy', 'remember-recent-files', 'true' if on else 'false')
    return bool(on)


def clear_recent():
    """Forget the recent-files list (the files themselves are not touched)."""
    path = sysutil.data_home() / RECENT
    if path.exists():
        path.write_text(EMPTY_XBEL, encoding='utf-8')
    return True


def recent_count():
    try:
        return (sysutil.data_home() / RECENT).read_text(encoding='utf-8').count('<bookmark ')
    except OSError:
        return 0


# ---------------------------------------------------------------- firewall
def firewall_enabled():
    """Read-only: /etc/ufw/ufw.conf is world-readable; `ufw status` needs root so it is never called here."""
    try:
        for line in Path('/etc/ufw/ufw.conf').read_text().splitlines():
            if line.strip().startswith('ENABLED='):
                return line.split('=', 1)[1].strip().lower() == 'yes'
    except OSError:
        return None
    return False


def firewall_installed():
    return os.path.exists('/usr/sbin/ufw')


def set_firewall(on):
    res = sysutil.run(['pkexec', SETTINGS_HELPER, 'firewall-enable' if on else 'firewall-disable'], timeout=60)
    return {'ok': res.code == 0, 'cancelled': res.code in (126, 127), 'error': '' if res.code == 0 else (res.err or res.out)[-200:]}
