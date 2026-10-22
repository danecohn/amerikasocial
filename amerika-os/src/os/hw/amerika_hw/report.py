"""Hardware report. Every probe is read-only and degrades to None/'unknown' when a file or tool is missing."""
import glob
import json
import os
import re
import shutil
import subprocess

SYS = '/sys'
PROC = '/proc'


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _run(cmd, timeout=15):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def cpu(sys_root=SYS, proc_root=PROC):
    text = _read(f'{proc_root}/cpuinfo', '') or ''
    model = _read(f'{sys_root}/devices/soc0/machine') or ''
    lscpu = _run(['lscpu'])
    name = re.search(r'Model name:\s*(.+)', lscpu)
    cores = len(glob.glob(f'{sys_root}/devices/system/cpu/cpu[0-9]*'))
    gov = _read(f'{sys_root}/devices/system/cpu/cpu0/cpufreq/scaling_governor')
    gov_avail = (_read(f'{sys_root}/devices/system/cpu/cpu0/cpufreq/scaling_available_governors') or '').split()
    mx = _read(f'{sys_root}/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
    return {'name': name.group(1).strip() if name else 'unknown', 'cores': cores, 'governor': gov, 'governors': gov_avail,
            'max_mhz': int(mx) // 1000 if mx and mx.isdigit() else None, 'soc': model or None}


def memory(proc_root=PROC):
    info = {}
    for line in (_read(f'{proc_root}/meminfo', '') or '').splitlines():
        k, _, v = line.partition(':')
        m = re.match(r'\s*(\d+)', v)
        if m:
            info[k] = int(m.group(1)) // 1024
    zram = os.path.exists('/sys/block/zram0')
    return {'total_mb': info.get('MemTotal'), 'available_mb': info.get('MemAvailable'), 'swap_mb': info.get('SwapTotal'),
            'swap_used_mb': (info.get('SwapTotal', 0) - info.get('SwapFree', 0)) if 'SwapTotal' in info else None, 'zram': zram}


def gpu(sys_root=SYS):
    out = {'driver': None, 'vulkan': [], 'opengl': None, 'devfreq': None, 'render_node': os.path.exists('/dev/dri/renderD128')}
    if shutil.which('vulkaninfo'):
        text = _run(['vulkaninfo', '--summary'])
        for block in re.split(r'\n\s*GPU\d+:', text)[1:]:
            name = re.search(r'deviceName\s*=\s*(.+)', block)
            drv = re.search(r'driverName\s*=\s*(.+)', block)
            api = re.search(r'apiVersion\s*=\s*(\S+)', block)
            info = re.search(r'driverInfo\s*=\s*(.+)', block)
            if name:
                out['vulkan'].append({'device': name.group(1).strip(), 'driver': drv.group(1).strip() if drv else None,
                                      'api': api.group(1) if api else None, 'info': info.group(1).strip() if info else None})
    if shutil.which('eglinfo'):
        m = re.search(r'OpenGL ES profile.*?renderer string:\s*(.+)', _run(['eglinfo', '-B']), re.S)
        out['opengl'] = m.group(1).strip() if m else None
    for d in glob.glob(f'{sys_root}/class/devfreq/*gpu*'):
        out['devfreq'] = {'name': os.path.basename(d), 'governor': _read(d + '/governor'), 'min_mhz': _mhz(_read(d + '/min_freq')),
                          'max_mhz': _mhz(_read(d + '/max_freq')), 'cur_mhz': _mhz(_read(d + '/cur_freq')),
                          'available': (_read(d + '/available_governors') or '').split()}
    out['hardware_accelerated'] = any('llvmpipe' not in v['device'] for v in out['vulkan']) if out['vulkan'] else None
    out['driver'] = next((v['driver'] for v in out['vulkan'] if 'llvmpipe' not in v['device']), None)
    return out


def _mhz(v):
    return int(v) // 1_000_000 if v and v.isdigit() else None


def npu(sys_root=SYS):
    """Honest status of the Hexagon NPU/DSP: the kernel exposes FastRPC nodes, but a usable stack needs Qualcomm's
    user-space runtime and signed DSP libraries, which Ubuntu does not ship."""
    nodes = sorted(glob.glob('/dev/fastrpc-*')) + sorted(glob.glob('/dev/accel/*'))
    libs = [p for p in ('/usr/lib/aarch64-linux-gnu/libcdsprpc.so', '/usr/lib/libcdsprpc.so') if os.path.exists(p)]
    qnn = bool(shutil.which('qnn-net-run'))
    return {'device_nodes': nodes, 'cdsp_node': any('cdsp' in n for n in nodes), 'userspace_runtime': bool(libs), 'qnn_tools': qnn,
            'usable_for_inference': bool(libs and qnn),
            'note': ('The compute DSP node exists, but no Hexagon user-space runtime is installed, so models cannot run on it. '
                     'This is the NPU: it does neural-network inference, not rendering, so it cannot speed up graphics.')
            if nodes and not (libs and qnn) else ('No NPU/DSP device node found.' if not nodes else 'Runtime present.')}


def thermals():
    out = {}
    for z in glob.glob(f'{SYS}/class/thermal/thermal_zone*'):
        t = _read(z + '/temp')
        if t and t.lstrip('-').isdigit():
            out[_read(z + '/type') or os.path.basename(z)] = round(int(t) / 1000, 1)
    hottest = max(out.values()) if out else None
    return {'hottest_c': hottest, 'zones': len(out)}


def power():
    prof = _run(['powerprofilesctl', 'get']).strip() or None
    avail = re.findall(r'^[ *]\s*([a-z-]+):', _run(['powerprofilesctl', 'list']), re.M)
    return {'profile': prof, 'profiles': avail, 'note': 'no performance profile on this machine' if avail and 'performance' not in avail else None}


def storage(path=None):
    path = path or os.path.expanduser('~')
    st = shutil.disk_usage(path)
    return {'free_gb': st.free // 2**30, 'total_gb': st.total // 2**30}


def limits():
    return {'inotify_watches': _int(_read(f'{PROC}/sys/fs/inotify/max_user_watches')), 'max_map_count': _int(_read(f'{PROC}/sys/vm/max_map_count')),
            'swappiness': _int(_read(f'{PROC}/sys/vm/swappiness'))}


def _int(v):
    return int(v) if v and v.lstrip('-').isdigit() else None


def tools():
    names = ['godot', 'blender', 'gcc', 'clang', 'cmake', 'ninja', 'git', 'git-lfs', 'dotnet', 'rustc', 'node', 'box64', 'gamemoderun', 'mangohud',
             'vkmark', 'glmark2-wayland', 'vulkaninfo']
    return {n: bool(shutil.which(n)) for n in names}


def advice(r):
    tips = []
    m = r['memory']
    if m['total_mb'] and m['total_mb'] < 20000:
        tips.append(f"{m['total_mb'] // 1024} GB of RAM: run 'amerika-hw tune apply' for compressed swap (zram) and larger limits; close Blender while exporting big scenes.")
    if r['limits']['inotify_watches'] and r['limits']['inotify_watches'] < 262144:
        tips.append('File-watch limit is low for Godot/Blender projects: amerika-hw tune apply raises it.')
    g = r['gpu']
    if g['hardware_accelerated'] is False:
        tips.append('Only a software Vulkan device was found: the GPU driver is not active.')
    if g['devfreq'] and g['devfreq']['governor'] != 'performance':
        tips.append("GPU clocks scale on demand; 'amerika-hw perf game' pins them high while you work (temporary, resets on reboot).")
    if not r['tools']['gcc']:
        tips.append('No C compiler: sudo apt install amerika-gamedev.')
    return tips


def build():
    r = {'cpu': cpu(), 'memory': memory(), 'gpu': gpu(), 'npu': npu(), 'thermal': thermals(), 'power': power(), 'storage': storage(),
         'limits': limits(), 'tools': tools()}
    r['advice'] = advice(r)
    return r


def text(r):
    c, m, g, n = r['cpu'], r['memory'], r['gpu'], r['npu']
    lines = [f"CPU      {c['name']} x{c['cores']}  governor {c['governor']}  max {c['max_mhz']} MHz",
             f"Memory   {m['total_mb']} MB total, {m['available_mb']} MB free, swap {m['swap_used_mb']}/{m['swap_mb']} MB, zram {'on' if m['zram'] else 'off'}"]
    for v in g['vulkan']:
        lines.append(f"Vulkan   {v['device']}  ({v['driver']}, API {v['api']})")
    if g['devfreq']:
        d = g['devfreq']
        lines.append(f"GPU clk  {d['cur_mhz']} MHz now, range {d['min_mhz']}-{d['max_mhz']} MHz, governor {d['governor']}")
    lines.append(f"NPU/DSP  nodes {', '.join(n['device_nodes']) or 'none'}; usable for inference: {'yes' if n['usable_for_inference'] else 'no'}")
    lines.append(f"Thermal  hottest zone {r['thermal']['hottest_c']} C   Power profile {r['power']['profile']}")
    lines.append(f"Storage  {r['storage']['free_gb']} GB free of {r['storage']['total_gb']} GB")
    lines.append('Tools    ' + ', '.join(f"{k}{'' if v else ' (missing)'}" for k, v in r['tools'].items()))
    if r['advice']:
        lines.append('')
        lines += ['* ' + t for t in r['advice']]
    return '\n'.join(lines)
