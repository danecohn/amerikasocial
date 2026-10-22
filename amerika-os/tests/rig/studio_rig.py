"""Shared helpers for the Amerika Studio rig scripts (run through tests/rig/studio-rig.sh, never on the real session).

Everything is throwaway: fake secret-tool, fake launchers, a private bridge port. Screenshots go to dist/studio/."""
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/os'))
sys.path.insert(0, str(ROOT / 'src/os/studio'))

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

Gtk.init()   # connect to the rig compositor BEFORE XDG_RUNTIME_DIR is repointed

FAKE_KEY = 'sk-ant-test-FAKE-rig-0123456789'
OUT = Path(os.environ.get('STUDIO_SHOTS') or ROOT / 'dist/studio')
OUT.mkdir(parents=True, exist_ok=True)
T = Path(os.environ.get('T') or '/tmp/studio-rig')
RUN = T / 'run'
RUN.mkdir(parents=True, exist_ok=True)
BIN = T / 'fakebin'
BIN.mkdir(parents=True, exist_ok=True)
for name in ('amerika-render', 'amerika-sprite'):          # two "installed" apps so the tiles show both states
    f = BIN / name
    f.write_text('#!/bin/sh\nexit 0\n')
    f.chmod(0o755)
os.environ.update({'XDG_RUNTIME_DIR': str(RUN), 'AMERIKA_STUDIO_SECRET_TOOL': str(ROOT / 'tests/rig/agent_fake_secret_tool.py'),
                   'FAKE_SECRET_DIR': str(T / 'secrets'), 'AMERIKA_STUDIO_PORT': '18893', 'AMERIKA_STUDIO_NO_SYSTEMD': '1',
                   'AMERIKA_SHARE': str(ROOT / 'src/os/amerika'), 'AMERIKA_ICONS': str(ROOT / 'src/os/icons'),
                   'AMERIKA_STUDIO_SHARE': str(ROOT / 'src/os/studio'), 'AMERIKA_STUDIO_WEB': str(ROOT / 'src/os/studio/web'),
                   'PATH': f'{BIN}:{os.environ["PATH"]}'})

from amerika import common as acommon  # noqa: E402

acommon.RUNTIME = RUN / 'amerika'
acommon.CONTROL_SOCKET = acommon.RUNTIME / 'control.sock'


def spin(predicate, timeout=8, what=''):
    deadline = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('timed out waiting for ' + (what or str(predicate)))


def settle(seconds=0.6):
    deadline = time.monotonic() + seconds
    ctx = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def shot(widget, name):
    from amerika.shell.app import save_widget
    settle(0.5)
    ok = save_widget(widget, OUT / name)
    print(('saved ' if ok else 'COULD NOT SAVE ') + name, flush=True)
    assert ok, name
    return OUT / name


def widget_texts(widget):
    out = []

    def walk(w):
        if isinstance(w, Gtk.Editable):
            out.append(w.get_text())
        if isinstance(w, Gtk.Label):
            out.append(w.get_text())
        child = w.get_first_child()
        while child:
            walk(child)
            child = child.get_next_sibling()
    walk(widget)
    return out


def kill_bridge():
    """Stop only the bridge this rig started (exact PID from its pid file)."""
    pidfile = RUN / 'amerika/studio-bridge.pid'
    try:
        os.kill(int(pidfile.read_text().strip()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
