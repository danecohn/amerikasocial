"""About backend: hardware and software facts for the About page, and a copy-to-clipboard report that carries no secrets
(no host name, user name, serial numbers, machine id, addresses or home paths)."""
import os
import re
from pathlib import Path

from . import sysutil, system

DMI = Path('/sys/class/dmi/id')
DRM = Path('/sys/class/drm')


def _read(path):
    try:
        return Path(path).read_text(errors='replace').strip().strip('\x00')
    except OSError:
        return ''


def cpu():
    res = sysutil.run(['lscpu'])
    kv = sysutil.parse_kv(res.out, ':') if res.code == 0 else {}
    name = kv.get('Model name') or kv.get('Vendor ID') or ''
    if not name:
        for line in _read('/proc/cpuinfo').splitlines():
            if line.lower().startswith(('model name', 'hardware')):
                name = line.split(':', 1)[1].strip()
                break
    return {'name': name or 'Unknown processor', 'arch': kv.get('Architecture') or os.uname().machine, 'threads': int(kv.get('CPU(s)') or os.cpu_count() or 1)}


def memory():
    for line in _read('/proc/meminfo').splitlines():
        if line.startswith('MemTotal:'):
            kb = int(re.search(r'(\d+)', line).group(1))
            return {'bytes': kb * 1024, 'text': f'{kb / 1048576:.1f} GiB'}
    return {'bytes': 0, 'text': 'Unknown'}


def gpus():
    out = []
    if sysutil.have('lspci'):
        for line in sysutil.run(['lspci', '-mm']).out.splitlines():
            if re.search(r'"(VGA compatible controller|3D controller|Display controller)"', line):
                parts = re.findall(r'"([^"]*)"', line)
                if len(parts) >= 3:
                    out.append(f'{parts[2]} {parts[3] if len(parts) > 3 else ""}'.strip())
    if not out and DRM.exists():
        for card in sorted(DRM.glob('card[0-9]')):
            driver = sysutil.parse_kv(_read(card / 'device/uevent')).get('DRIVER', '')
            if driver:
                out.append(f'{driver} graphics driver')
    return out or ['Unknown graphics']


def firmware():
    vendor = _read(DMI / 'bios_vendor')
    version = _read(DMI / 'bios_version')
    date = _read(DMI / 'bios_date')
    model = _read(DMI / 'product_name') or _read('/proc/device-tree/model')
    maker = _read(DMI / 'sys_vendor')
    return {'model': ' '.join(x for x in (maker, model) if x) or 'Unknown device', 'firmware': ' '.join(x for x in (vendor, version, date) if x) or 'Not reported'}


def desktop_versions():
    out = {}
    for name, argv in (('KDE Plasma', ['plasmashell', '--version']), ('KWin', ['kwin_wayland', '--version'])):
        res = sysutil.run(argv, timeout=4)
        m = re.search(r'(\d+\.\d+(\.\d+)*)', res.out)
        out[name] = m.group(1) if m else ''
    return {k: v for k, v in out.items() if v}


def amerika_packages():
    res = sysutil.run(['dpkg-query', '-W', '-f', '${Package}\t${Version}\n', 'amerika-*'])
    return [tuple(line.split('\t', 1)) for line in res.out.splitlines() if '\t' in line]


def collect():
    from . import __version__
    info = system.os_info()
    return {'os': info.get('distribution') or 'Linux', 'amerika_version': __version__, 'kernel': info.get('kernel'), 'arch': info.get('machine'),
            'host': info.get('host'), 'cpu': cpu(), 'memory': memory(), 'gpus': gpus(), **firmware(), 'desktop': desktop_versions(),
            'session': os.environ.get('XDG_SESSION_TYPE', ''), 'packages': amerika_packages()}


def report(info):
    """Plain-text report for the clipboard. Deliberately leaves out the host name and any identifier."""
    lines = ['AltStack Desktop system information', '',
             f"AltStack Desktop: {info['amerika_version']}", f"Base system: {info['os']}", f"Kernel: {info['kernel']} ({info['arch']})",
             f"Device: {info['model']}", f"Firmware: {info['firmware']}",
             f"Processor: {info['cpu']['name']} ({info['cpu']['threads']} threads)", f"Memory: {info['memory']['text']}",
             'Graphics: ' + '; '.join(info['gpus'])]
    for k, v in info['desktop'].items():
        lines.append(f'{k}: {v}')
    if info.get('session'):
        lines.append(f"Session: {info['session']}")
    if info['packages']:
        lines += ['', 'Amerika packages:'] + [f'  {n} {v}' for n, v in info['packages']]
    return '\n'.join(lines) + '\n'
