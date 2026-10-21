"""Shared helpers for the Amerika Agent rig scripts (run through tools/kwin-rig.sh, never on the real session).

Everything runs against tests/fixtures/amerika-agent (the fake CLI) with a throwaway XDG_RUNTIME_DIR for amerika data;
screenshots go to dist/agent-ui/ (override with AGENT_SHOTS)."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/os'))

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

Gtk.init()  # connect to the rig compositor BEFORE we repoint XDG_RUNTIME_DIR (the Wayland socket lives in the old one)

FAKE_KEY = 'sk-test-FAKE-rig-0123456789'
OUT = Path(os.environ.get('AGENT_SHOTS') or ROOT / 'dist/agent-ui')
OUT.mkdir(parents=True, exist_ok=True)
T = Path(os.environ.get('T') or '/tmp/agent-rig')
RUN = T / 'run'
RUN.mkdir(parents=True, exist_ok=True)
os.environ.update({'XDG_RUNTIME_DIR': str(RUN), 'AMERIKA_AGENT_BIN': str(ROOT / 'tests/fixtures/amerika-agent'),
                   'FAKE_AGENT_STATE': str(T / 'fake-agent.json'), 'FAKE_AGENT_LOG': str(T / 'fake-calls.log'), 'FAKE_AGENT_DELAY': '0.3',
                   'AMERIKA_SHARE': str(ROOT / 'src/os/amerika'), 'AMERIKA_ICONS': str(ROOT / 'src/os/icons'),
                   'AMERIKA_WALLPAPERS': str(ROOT / 'src/os/wallpapers')})
os.environ.pop('FAKE_AGENT_FAIL', None)

from amerika import common  # noqa: E402

common.RUNTIME = RUN / 'amerika'
common.CONTROL_SOCKET = common.RUNTIME / 'control.sock'


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
    spin(lambda: False, timeout=seconds) if False else None
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
    """Every editable text and label text under a widget (used to prove a secret is nowhere in the UI)."""
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


def fake_state():
    import json
    try:
        return json.loads(Path(os.environ['FAKE_AGENT_STATE']).read_text())
    except (OSError, ValueError):
        return {}
