"""Power backend: power profiles (power-profiles-daemon), battery facts (UPower), lid/idle actions (powerdevil),
battery charge limit (sysfs read; changes through pkexec and amerika-settings-helper)."""
import json
from pathlib import Path

from . import sysutil, system
from .bluetooth import _unwrap
from .updates import SETTINGS_HELPER

PROFILES = [('power-saver', 'Power saver'), ('balanced', 'Balanced'), ('performance', 'Performance')]
ACTIONS = [(0, 'Do nothing'), (1, 'Sleep'), (2, 'Hibernate'), (8, 'Shut down'), (32, 'Lock screen')]
SUPPLY = Path('/sys/class/power_supply')
THRESHOLD_FILES = ('charge_control_end_threshold', 'charge_stop_threshold')


def profiles():
    res = sysutil.run(['powerprofilesctl', 'list'])
    names = [n for n, _t in PROFILES if n in res.out] if res.code == 0 else []
    return {'available': names, 'current': system.power_profile()}


def set_profile(name):
    return system.set_power_profile(name)


def battery():
    res = sysutil.run(['busctl', '--system', '-j', 'call', 'org.freedesktop.UPower', '/org/freedesktop/UPower/devices/DisplayDevice',
                       'org.freedesktop.DBus.Properties', 'GetAll', 's', 'org.freedesktop.UPower.Device'])
    if res.code != 0:
        return None
    try:
        p = _unwrap(json.loads(res.out)['data'][0])
    except (ValueError, KeyError, IndexError):
        return None
    if not p.get('IsPresent', True):
        return None
    state = {1: 'charging', 2: 'discharging', 4: 'full', 5: 'pending charge'}.get(p.get('State'), 'unknown')
    return {'percent': round(p.get('Percentage', 0)), 'state': state, 'time_to_empty': int(p.get('TimeToEmpty', 0)),
            'time_to_full': int(p.get('TimeToFull', 0)), 'health': battery_health()}


def battery_health():
    for b in sorted(SUPPLY.glob('BAT*')) if SUPPLY.exists() else []:
        try:
            full = int((b / 'energy_full').read_text() if (b / 'energy_full').exists() else (b / 'charge_full').read_text())
            design = int((b / 'energy_full_design').read_text() if (b / 'energy_full_design').exists() else (b / 'charge_full_design').read_text())
            return round(100 * full / design) if design else None
        except (OSError, ValueError):
            continue
    return None


def duration(seconds):
    if not seconds:
        return ''
    h, m = divmod(int(seconds) // 60, 60)
    return f'{h} h {m:02d} min' if h else f'{m} min'


def threshold():
    """Current charge limit and whether the hardware supports one."""
    for b in sorted(SUPPLY.glob('BAT*')) if SUPPLY.exists() else []:
        for name in THRESHOLD_FILES:
            f = b / name
            if f.exists():
                try:
                    return {'supported': True, 'value': int(f.read_text())}
                except (OSError, ValueError):
                    return {'supported': True, 'value': 100}
    return {'supported': False, 'value': 100}


def set_threshold(value):
    value = int(value)
    if not 50 <= value <= 100:
        raise ValueError('The charge limit must be between 50% and 100%.')
    res = sysutil.run(['pkexec', SETTINGS_HELPER, 'battery-threshold', str(value)], timeout=60)
    return {'ok': res.code == 0, 'cancelled': res.code in (126, 127), 'error': '' if res.code == 0 else (res.err or res.out)[-200:]}


# powerdevilrc: [AC|Battery|LowBattery][SuspendAndShutdown] LidAction, AutoSuspendAction, AutoSuspendIdleTimeoutSec; [..][Display] TurnOffDisplay*
def _grp(source, section):
    return f'{source}][{section}'


def power_options(source='AC'):
    ss = _grp(source, 'SuspendAndShutdown')
    disp = _grp(source, 'Display')
    return {'lid_action': int(sysutil.kread('powerdevilrc', ss, 'LidAction', '1') or 1),
            'idle_action': int(sysutil.kread('powerdevilrc', ss, 'AutoSuspendAction', '1') or 1),
            'idle_minutes': max(1, int(sysutil.kread('powerdevilrc', ss, 'AutoSuspendIdleTimeoutSec', '900') or 900) // 60),
            'screen_off_minutes': max(1, int(sysutil.kread('powerdevilrc', disp, 'TurnOffDisplayIdleTimeoutSec', '300') or 300) // 60),
            'power_button': int(sysutil.kread('powerdevilrc', ss, 'PowerButtonAction', '16') or 16)}


def set_power_options(source='AC', lid_action=None, idle_action=None, idle_minutes=None, screen_off_minutes=None):
    if source not in ('AC', 'Battery', 'LowBattery'):
        raise ValueError('source must be AC, Battery or LowBattery')
    valid = {v for v, _t in ACTIONS}
    ss, disp = _grp(source, 'SuspendAndShutdown'), _grp(source, 'Display')
    for key, value in (('LidAction', lid_action), ('AutoSuspendAction', idle_action)):
        if value is not None:
            if int(value) not in valid:
                raise ValueError('unknown power action')
            sysutil.kwrite('powerdevilrc', ss, key, int(value))
    if idle_minutes is not None:
        sysutil.kwrite('powerdevilrc', ss, 'AutoSuspendIdleTimeoutSec', max(1, min(720, int(idle_minutes))) * 60)
    if screen_off_minutes is not None:
        sysutil.kwrite('powerdevilrc', disp, 'TurnOffDisplayIdleTimeoutSec', max(1, min(720, int(screen_off_minutes))) * 60)
        sysutil.kwrite('powerdevilrc', disp, 'TurnOffDisplayWhenIdle', True)
    sysutil.run(['busctl', '--user', 'call', 'org.kde.Solid.PowerManagement', '/org/kde/Solid/PowerManagement', 'org.kde.Solid.PowerManagement',
                 'reparseConfiguration'])
    return power_options(source)
