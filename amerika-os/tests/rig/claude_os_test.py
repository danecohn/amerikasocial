"""End-to-end check of the Claude-first shell inside a private KWin (run via tests/rig/claude_os_rig.sh; see claude_os_test.sh).

Starts the real amerika-shell with fake Claude / ChatGPT apps and proves: the home window is maximized, borderless and under the bar;
it is supervised (relaunch with backoff); other windows open above it; the Win+H action and Caster work (open, move focus, choose,
Copilot key cycles); the dock is not created; the bar layout changes live; the scale flag reaches a launched app; and switching the
home mode off gives the window its frame back. Screenshots go to dist/claude-os/ (override with CLAUDE_OS_SHOTS)."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/os'))
OUT = Path(os.environ.get('CLAUDE_OS_SHOTS') or ROOT / 'dist/claude-os')
OUT.mkdir(parents=True, exist_ok=True)
T = Path(os.environ['T'])
LOG = T / 'shell.log'
FAKELOG = T / 'fake-ai.log'
os.environ.update({'AMERIKA_SHARE': str(ROOT / 'src/os/amerika'), 'AMERIKA_ICONS': str(ROOT / 'src/os/icons'),
                   'AMERIKA_WALLPAPERS': str(ROOT / 'src/os/wallpapers'), 'AMERIKA_DEBUG': '1', 'AMERIKA_SCREENSHOT_DIR': str(OUT),
                   'FAKE_AI_LOG': str(FAKELOG), 'GTK_A11Y': 'none'})
from amerika import common  # noqa: E402
from amerika.shell import barlayout  # noqa: E402

failures = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        failures.append(name)


def wait(pred, timeout=15, step=0.2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None


def action(name):
    subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.amerika.Shell', '--object-path', '/Control',
                    '--method', 'org.amerika.Control.Action', name], capture_output=True, timeout=10)


def debug(name, prefix, timeout=6):
    """Send a debug action and return the shell's reply line (the newest line with this prefix that appears after the call)."""
    before = LOG.read_text().count(prefix) if LOG.exists() else 0
    action(name)
    def new():
        text = LOG.read_text() if LOG.exists() else ''
        lines = [l for l in text.splitlines() if l.startswith(prefix)]
        return lines[-1] if len(lines) > before else None
    return wait(new, timeout, 0.1)


def windows():
    line = debug('debug-windows', 'DEBUG windows ')
    return json.loads(line[len('DEBUG windows '):]) if line else {'windows': [], 'screens': []}


def win(cls, data=None):
    data = data or windows()
    return next((w for w in data['windows'] if str(w.get('cls', '')).lower() == cls.lower()), None)


def launches(cls=None):
    try:
        lines = FAKELOG.read_text().splitlines()
    except OSError:
        return []
    return [l for l in lines if cls is None or l.startswith('launch ' + cls + ' ')]


def set_settings(**kw):
    s = common.load_settings()
    s.update(kw)
    common.save_settings(s)


def screen(name):
    debug('debug-screen:' + name, 'DEBUG screen saved=', 20)
    print('  screenshot', name, flush=True)


def widget_shot(name):
    action('debug-shot:' + name)
    time.sleep(0.8)


# ---------------------------------------------------------------- start the shell
common.CONFIG.mkdir(parents=True, exist_ok=True)
set_settings(home_mode='claude', dock_enabled=False, copilot_app='caster', bar_layout=barlayout.preset('home'), bar_preset='home',
             ai_text_scale={'claude': 1.0, 'chatgpt': 1.25})
shell = subprocess.Popen(['amerika-shell'], stdout=open(LOG, 'w'), stderr=subprocess.STDOUT, env=os.environ.copy())
try:
    ready = wait(lambda: (common.RUNTIME / 'shell-ready').exists(), 40)
    check('shell reports ready', bool(ready))
    action('home-start')           # what session-start does once the shell is ready

    # ---- 1. home window: maximized, borderless, under the bar, no dock
    w = wait(lambda: win('com.anthropic.Claude'), 30)
    check('home app launched at login', w is not None, launches('com.anthropic.Claude'))
    time.sleep(2.5)
    data = windows()
    w = win('com.anthropic.Claude', data)
    area = ((data['screens'] or [{}])[0]).get('work') or {}
    print('  screens:', json.dumps(data['screens'])[:300], '\n  home window:', json.dumps(w), flush=True)
    check('home window is borderless', bool(w and w['noBorder']))
    check('home window is flagged as the home window', bool(w and w['home']))
    ax, ay, aw, ah = (area.get('x', 0), area.get('y', 0), area.get('w', 1920), area.get('h', 1039))
    check('home window fills the work area', bool(w) and abs(w['x'] - ax) <= 2 and abs(w['y'] - ay) <= 2 and abs(w['w'] - aw) <= 2 and abs(w['h'] - ah) <= 2, (w and (w['x'], w['y'], w['w'], w['h']), (ax, ay, aw, ah)))
    check('work area starts below the top bar', ay >= 28, ay)
    check('home window not minimized', bool(w) and not w['minimized'])
    info = debug('debug-home', 'DEBUG home ')
    check('no dock window is created', info is not None and 'dock=False' in info, info)
    screen('home-claude')
    widget_shot('bar')
    os.replace(OUT / 'bar.png', OUT / 'bar-home.png')

    # ---- 2. supervision: killing the app brings it back
    n_before = len(launches('com.anthropic.Claude'))
    os.kill(w['pid'], signal.SIGKILL)
    relaunched = wait(lambda: len(launches('com.anthropic.Claude')) > n_before, 25)
    check('closed home app is relaunched by the supervisor', bool(relaunched), launches('com.anthropic.Claude'))
    w2 = wait(lambda: (lambda x: x if x and x['pid'] != w['pid'] else None)(win('com.anthropic.Claude')), 20)
    time.sleep(2)
    w2 = win('com.anthropic.Claude')
    check('relaunched window is borderless and maximized again', bool(w2 and w2['noBorder'] and abs(w2['w'] - aw) <= 2 and abs(w2['h'] - ah) <= 2), w2 and (w2['w'], w2['h']))

    # ---- 3. other windows open above the home window; Win+H brings it back
    other = subprocess.Popen([sys.executable, str(ROOT / 'tests/rig/claude_os_fake/fake_ai_app.py'), 'org.test.Other'], env=os.environ.copy())
    o = wait(lambda: win('org.test.Other'), 15)
    time.sleep(1)
    data = windows()
    o, h = win('org.test.Other', data), win('com.anthropic.Claude', data)
    check('another app opens above the home window', bool(o and h and o['z'] > h['z']), (o and o['z'], h and h['z']))
    check('other apps keep their frame', bool(o) and not o['noBorder'] and o['w'] < aw)
    check('home window was not minimized by it', bool(h) and not h['minimized'])
    action('home')
    ok = wait(lambda: (lambda d: (win('com.anthropic.Claude', d) or {}).get('z', -1) > (win('org.test.Other', d) or {}).get('z', 99) and d)(windows()), 10)
    check('Win+H (action home) raises the home window above the other app', bool(ok))
    screen('home-over-other')
    other.terminate()

    # ---- 4. Caster
    action('caster')
    st = wait(lambda: (lambda l: l if l and 'visible=True' in l else None)(debug('debug-caster-state', 'DEBUG caster visible=')), 8)
    check('Copilot key action opens the Caster', bool(st), st)
    check('Caster starts on the last choice (claude)', bool(st) and 'focused=claude' in st, st)
    time.sleep(0.6)
    widget_shot('caster')
    os.replace(OUT / 'caster.png', OUT / 'caster-focus-claude.png')
    r = debug('debug-caster-key:Right', 'DEBUG caster key=')
    check('Right moves focus to ChatGPT', bool(r) and 'focused=chatgpt' in r, r)
    time.sleep(0.5)
    widget_shot('caster')
    os.replace(OUT / 'caster.png', OUT / 'caster-focus-chatgpt.png')
    action('caster')   # Copilot key again cycles to the other card
    time.sleep(0.3)
    st = debug('debug-caster-state', 'DEBUG caster visible=')
    check('Copilot key again cycles to the other card', bool(st) and 'focused=claude' in st and 'visible=True' in st, st)
    r = debug('debug-caster-key:2', 'DEBUG caster key=')
    check('key 2 picks ChatGPT and closes the Caster', bool(r), r)
    time.sleep(0.8)
    st = debug('debug-caster-state', 'DEBUG caster visible=')
    check('Caster is closed after choosing', bool(st) and 'visible=False' in st, st)
    s = common.load_settings()
    check('choosing ChatGPT makes it the home app', s['home_mode'] == 'chatgpt' and s['caster_last'] == 'chatgpt', (s['home_mode'], s['caster_last']))
    ch = wait(lambda: win('chatgpt'), 20)
    time.sleep(2.5)
    data = windows()
    ch, cl = win('chatgpt', data), win('com.anthropic.Claude', data)
    check('ChatGPT launched and is borderless under the bar', bool(ch and ch['noBorder'] and abs(ch['y'] - ay) <= 2 and abs(ch['w'] - aw) <= 2), ch and (ch['x'], ch['y'], ch['w'], ch['h']))
    check('ChatGPT is in front', bool(ch and cl and ch['z'] > cl['z']))
    check('Claude got its frame back when it stopped being home', bool(cl) and not cl['noBorder'], cl and cl['noBorder'])
    screen('home-chatgpt')
    action('caster')
    time.sleep(1.2)
    check('Caster reopens focused on the last choice (chatgpt)', 'focused=chatgpt' in (debug('debug-caster-state', 'DEBUG caster visible=') or ''))
    widget_shot('caster')
    os.replace(OUT / 'caster.png', OUT / 'caster-reopened.png')
    r = debug('debug-caster-key:Escape', 'DEBUG caster key=')
    time.sleep(0.6)
    check('Esc closes the Caster', 'visible=False' in (debug('debug-caster-state', 'DEBUG caster visible=') or ''))

    # ---- 5. bar layout changes live
    base = debug('debug-bar', 'DEBUG bar ')
    layout = barlayout.set_enabled(barlayout.preset('home'), 'title', False)
    layout = barlayout.set_zone(layout, 'clock', 'right')
    set_settings(bar_layout=layout, bar_height=44, bar_opacity=0.8, bar_clock_format={'hour24': True, 'seconds': True, 'date': 'numeric'})
    time.sleep(2)
    after = debug('debug-bar', 'DEBUG bar ')
    zones = json.loads(after.split(' zones=')[1].split(' height=')[0])
    check('bar layout applies live (title off, clock moved right)', 'title' not in zones['left'] and 'clock' in zones['right'], zones)
    h = int(after.split('height=')[1].split()[0])
    check('bar height setting is applied', 42 <= h <= 46, h)
    data = windows()
    w = win('chatgpt', data)
    check('home window still fits under the taller bar', bool(w) and w['y'] >= 42, w and w['y'])
    print('  ', after, flush=True)
    check('date label shows text in the custom layout', "date='2" in after, after)
    widget_shot('bar')
    os.replace(OUT / 'bar.png', OUT / 'bar-custom.png')
    screen('home-custom-bar')
    set_settings(bar_layout=barlayout.preset('home'), bar_height=36, bar_opacity=1.0, bar_clock_format={'hour24': None, 'seconds': False, 'date': 'short'})
    time.sleep(1.5)
    n1 = int(debug('debug-bar', 'DEBUG bar ').split('rebuilds=')[1].split()[0])
    set_settings(caster_last='chatgpt')                      # unrelated change: no rebuild
    time.sleep(1.2)
    n2 = int(debug('debug-bar', 'DEBUG bar ').split('rebuilds=')[1].split()[0])
    check('unrelated settings do not rebuild the bar', n1 == n2, (n1, n2))

    # ---- 6. dock toggle comes back live
    set_settings(dock_enabled=True)
    ok = wait(lambda: 'dock=True' in (debug('debug-home', 'DEBUG home ') or ''), 8)
    check('turning the dock on in settings creates it live', bool(ok))
    time.sleep(1.5)
    data = windows()
    w = win('chatgpt', data)
    screen('dock-back')
    set_settings(dock_enabled=False)
    ok = wait(lambda: 'dock=False' in (debug('debug-home', 'DEBUG home ') or ''), 8)
    check('turning it off removes it again', bool(ok))

    # ---- 7. scale flag on launch
    for pid in {x['pid'] for x in windows()['windows'] if str(x.get('cls')).lower() == 'com.anthropic.claude'}:
        os.kill(pid, signal.SIGKILL)
    set_settings(ai_text_scale={'claude': 1.5, 'chatgpt': 1.25})
    time.sleep(1)
    n = len(launches('com.anthropic.Claude'))
    action('ai1')
    wait(lambda: len(launches('com.anthropic.Claude')) > n, 10)
    last = (launches('com.anthropic.Claude') or [''])[-1]
    check('launch passes --force-device-scale-factor from ai_text_scale', '--force-device-scale-factor=1.5' in last, last)
    check('launched app does not inherit LD_PRELOAD', 'ld_preload=unset' in last, last)
    n = len(launches('chatgpt'))
    for pid in {x['pid'] for x in windows()['windows'] if str(x.get('cls')).lower() == 'chatgpt'}:
        os.kill(pid, signal.SIGKILL)
    wait(lambda: len(launches('chatgpt')) > n, 25)
    last = (launches('chatgpt') or [''])[-1]
    check('ChatGPT default text scale 1.25 reaches the app', '--force-device-scale-factor=1.25' in last, last)

    # ---- 8. Classic: mode off restores frames and stops supervising
    set_settings(home_mode='off')
    time.sleep(3)
    data = windows()
    ch = win('chatgpt', data)
    check('home mode off: the former home window has its frame back', bool(ch) and not ch['noBorder'], ch)
    info = debug('debug-home', 'DEBUG home ')
    check('home mode off: supervisor stopped', info is not None and 'state=stopped' in info, info)
    n = len(launches('chatgpt'))
    for pid in {x['pid'] for x in data['windows'] if str(x.get('cls')).lower() == 'chatgpt'}:
        os.kill(pid, signal.SIGKILL)
    time.sleep(8)
    check('home mode off: a closed app is NOT relaunched', len(launches('chatgpt')) == n, launches('chatgpt')[n:])
finally:
    shell.terminate()
    try:
        shell.wait(10)
    except subprocess.TimeoutExpired:
        shell.kill()
    subprocess.run(['sh', '-c', 'true'])

print('CLAUDE-OS SHELL RIG: %d failure(s)' % len(failures), failures, flush=True)
sys.exit(1 if failures else 0)
