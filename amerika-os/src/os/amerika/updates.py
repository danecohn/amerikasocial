"""Updates backend: read-only apt state plus privileged actions that always go through pkexec and a fixed helper.

* Amerika packages: the existing `amerika-software-helper` (update / upgrade, restricted to the signed Amerika repository).
* Everything else (Ubuntu): `amerika-settings-helper apt-update | apt-upgrade` (fixed arguments; never dist-upgrade).
Nothing here ever runs apt directly with elevated rights.
"""
import os
import re
import time
from pathlib import Path

from . import sysutil

SOFTWARE_HELPER = os.environ.get('AMERIKA_SOFTWARE_HELPER', '/usr/libexec/amerika-software-helper')
SETTINGS_HELPER = os.environ.get('AMERIKA_SETTINGS_HELPER', '/usr/libexec/amerika/amerika-settings-helper')
AMERIKA_SOURCES = Path('/etc/apt/sources.list.d/amerika.sources')
STAMPS = ('/var/lib/apt/periodic/update-success-stamp', '/var/lib/apt/lists')
REBOOT_FLAG = Path('/var/run/reboot-required')
_LINE = re.compile(r'^(?P<name>[^/\s]+)/(?P<suite>\S+)\s+(?P<new>\S+)\s+(?P<arch>\S+)(?:\s+\[upgradable from: (?P<old>[^\]]+)\])?')


def upgradable():
    res = sysutil.run(['apt', 'list', '--upgradable'], timeout=20, env={'LANG': 'C', 'LC_ALL': 'C'})
    out = []
    for line in res.out.splitlines():
        m = _LINE.match(line)
        if m:
            suite = m.group('suite')
            out.append({'name': m.group('name'), 'new': m.group('new'), 'old': m.group('old') or '', 'suite': suite,
                        'security': 'security' in suite, 'amerika': m.group('name').startswith('amerika') or 'amerika' in suite.lower()})
    return out


def last_refresh():
    for p in STAMPS:
        try:
            return int(os.stat(p).st_mtime)
        except OSError:
            continue
    return None


def ago(ts, now=None):
    if not ts:
        return 'never'
    delta = int((now or time.time()) - ts)
    if delta < 90:
        return 'just now'
    if delta < 5400:
        return f'{delta // 60} minutes ago'
    if delta < 172800:
        return f'{delta // 3600} hours ago'
    return f'{delta // 86400} days ago'


def amerika_repo():
    """State of the Amerika apt repository: configured, where, signed by what, and which Amerika packages are installed."""
    info = {'configured': AMERIKA_SOURCES.exists(), 'uri': '', 'suite': '', 'signed_by': '', 'keyring_present': False, 'packages': []}
    try:
        for line in AMERIKA_SOURCES.read_text(encoding='utf-8').splitlines():
            if ':' in line and not line.startswith('#'):
                k, v = line.split(':', 1)
                k = k.strip().lower()
                if k == 'uris':
                    info['uri'] = v.strip()
                elif k == 'suites':
                    info['suite'] = v.strip()
                elif k == 'signed-by':
                    info['signed_by'] = v.strip()
    except OSError:
        pass
    if info['signed_by']:
        info['keyring_present'] = Path(info['signed_by']).exists()
    res = sysutil.run(['dpkg-query', '-W', '-f', '${Package}\t${Version}\n', 'amerika-*'])
    for line in res.out.splitlines():
        if '\t' in line:
            n, v = line.split('\t', 1)
            info['packages'].append({'name': n, 'version': v})
    return info


def status():
    ups = upgradable()
    return {'upgradable': ups, 'count': len(ups), 'security': sum(1 for u in ups if u['security']), 'amerika_count': sum(1 for u in ups if u['amerika']),
            'last_refresh': last_refresh(), 'reboot_required': REBOOT_FLAG.exists(), 'amerika_repo': amerika_repo()}


def _pkexec(helper, *args, timeout=1800):
    res = sysutil.run(['pkexec', helper, *args], timeout=timeout)
    cancelled = res.code in (126, 127)
    return {'ok': res.code == 0, 'cancelled': cancelled, 'output': (res.out or '')[-2000:], 'error': '' if res.code == 0 else (res.err or res.out)[-300:]}


def refresh_amerika():
    return _pkexec(SOFTWARE_HELPER, 'update')


def upgrade_amerika():
    return _pkexec(SOFTWARE_HELPER, 'upgrade')


def refresh_system():
    return _pkexec(SETTINGS_HELPER, 'apt-update')


def upgrade_system():
    return _pkexec(SETTINGS_HELPER, 'apt-upgrade')
