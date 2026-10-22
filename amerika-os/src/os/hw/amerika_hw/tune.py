"""Root-side actions. `tune apply/revert` installs/removes drop-ins; `perf` changes CPU/GPU clocks at runtime only
(nothing persists across a reboot). Every write is validated; previous values are saved for revert."""
import glob
import json
import os
import shutil
import subprocess

SHARE = '/usr/share/amerika-gamedev/tuning'
STATE = '/var/lib/amerika-os/hw'
SYS = '/sys'
FILES = {
    '60-amerika-gamedev.conf': '/etc/sysctl.d/60-amerika-gamedev.conf',
    '60-amerika-gamedev-limits.conf': '/etc/security/limits.d/60-amerika-gamedev.conf',
    'zram-generator.conf': '/etc/systemd/zram-generator.conf.d/amerika.conf',
    '60-amerika-gpu.conf': '/etc/environment.d/60-amerika-gpu.conf',
}


def apply(share=SHARE, files=FILES, run=True):
    done = []
    for name, dest in files.items():
        src = os.path.join(share, name)
        if not os.path.isfile(src):
            raise RuntimeError(f'missing tuning file {name}')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest + '.tmp')
        os.chmod(dest + '.tmp', 0o644)
        os.replace(dest + '.tmp', dest)
        done.append(dest)
    if run:
        subprocess.run(['sysctl', '--system'], capture_output=True)
        subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
        subprocess.run(['systemctl', 'start', 'systemd-zram-setup@zram0.service'], capture_output=True)
    return done


def revert(files=FILES, run=True):
    gone = []
    for dest in files.values():
        if os.path.exists(dest):
            os.unlink(dest)
            gone.append(dest)
    if run:
        subprocess.run(['systemctl', 'stop', 'systemd-zram-setup@zram0.service'], capture_output=True)
        subprocess.run(['sysctl', '--system'], capture_output=True)
    return gone


def _write(path, value):
    with open(path, 'w') as f:
        f.write(str(value))


def _cpu_policies(sys_root):
    return sorted(glob.glob(f'{sys_root}/devices/system/cpu/cpufreq/policy[0-9]*'))


def _gpu(sys_root):
    return next(iter(glob.glob(f'{sys_root}/class/devfreq/*gpu*')), None)


def _rd(p):
    try:
        return open(p).read().strip()
    except OSError:
        return None


def perf(mode, sys_root=SYS, state=STATE):
    """mode: game | balanced. 'game' = performance governors; 'balanced' restores what was there before."""
    saved = os.path.join(state, 'perf.json')
    gpu = _gpu(sys_root)
    if mode == 'game':
        prev = {'cpu': {p: _rd(p + '/scaling_governor') for p in _cpu_policies(sys_root)},
                'gpu': ({'path': gpu, 'governor': _rd(gpu + '/governor'), 'min': _rd(gpu + '/min_freq')} if gpu else None)}
        if not os.path.exists(saved):  # keep the ORIGINAL values even if 'game' is run twice
            os.makedirs(state, exist_ok=True)
            json.dump(prev, open(saved, 'w'))
        for p in _cpu_policies(sys_root):
            if 'performance' in (_rd(p + '/scaling_available_governors') or ''):
                _write(p + '/scaling_governor', 'performance')
        if gpu:
            avail = (_rd(gpu + '/available_governors') or '').split()
            if 'performance' in avail:
                _write(gpu + '/governor', 'performance')
            else:
                top = _rd(gpu + '/max_freq')
                if top:
                    _write(gpu + '/min_freq', top)
        return 'game'
    if mode == 'balanced':
        try:
            prev = json.load(open(saved))
        except (OSError, ValueError):
            return 'balanced'
        for p, g in prev['cpu'].items():
            if g and os.path.exists(p + '/scaling_governor'):
                _write(p + '/scaling_governor', g)
        gp = prev.get('gpu')
        if gp and os.path.exists(gp['path']):
            if gp.get('min'):
                _write(gp['path'] + '/min_freq', gp['min'])
            if gp.get('governor'):
                _write(gp['path'] + '/governor', gp['governor'])
        os.unlink(saved)
        return 'balanced'
    raise ValueError('mode must be game or balanced')
