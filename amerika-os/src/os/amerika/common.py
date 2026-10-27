"""Paths, settings storage, logging and small helpers shared by the shell, settings app and MCP server."""
import json
import os
import tempfile
import time
from pathlib import Path

APP_NAME = 'AltStack Desktop'


def _dir(env, fallback):
    return Path(os.environ.get(env) or Path.home() / fallback)


CONFIG = _dir('XDG_CONFIG_HOME', '.config') / 'amerika-os'
STATE = _dir('XDG_STATE_HOME', '.local/state') / 'amerika-os'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR') or f'/tmp/amerika-{os.getuid()}') / 'amerika'
SHARE = Path(os.environ.get('AMERIKA_SHARE', '/usr/share/amerika-os'))
CONTROL_SOCKET = RUNTIME / 'control.sock'

DEFAULTS = {
    'accent': '#ff2e63',
    'secondary': '#19e3ff',
    'wallpaper': 'horizon',
    'dock_size': 56,
    'dock_position': 'bottom',
    'ui_style': 'retro',
    'dock_pinned': ['com.anthropic.Claude', 'chatgpt', 'amerika-agent', 'amerika-social', 'amerika-venture', 'amerika-files',
                    'amerika-terminal', 'amerika-office', 'amerika-software', 'amerika-settings'],
    'bar_ai_apps': ['com.anthropic.Claude', 'chatgpt'],
    'clock_24h': False,
    # what the Copilot key opens: caster (the Claude/ChatGPT chooser), claude, chatgpt, agent (Amerika Agent) or ask (a picker)
    'copilot_app': 'claude',
    # Claude-first mode (opt-in, see docs/claude-os/shell.md). Existing behaviour is the default: no home app, dock shown.
    'home_mode': 'off',            # claude | chatgpt | off
    'dock_enabled': True,
    'bar_layout': None,            # None = classic layout (shell/barlayout.py); a list of {id, enabled, zone, order}
    'bar_preset': 'classic',
    'bar_clock_format': {'hour24': None, 'seconds': False, 'date': 'short'},   # hour24 None follows clock_24h
    'bar_height': 36,
    'bar_opacity': 1.0,
    'ai_text_scale': {'chatgpt': 1.25, 'claude': 1.0},   # Electron --force-device-scale-factor, range 0.8 to 2.0
    'caster_last': 'claude',
    'app_last_used': {},
    'recent_apps': [],
    'ai': {
        # one of: ask (confirm every action), safe (read and reversible actions run, others ask), trusted (all but sensitive run)
        'mode': 'safe',
        'audit': True,
        'clients': {},
    },
}


def load_settings():
    data = json.loads(json.dumps(DEFAULTS))
    try:
        stored = json.loads((CONFIG / 'settings.json').read_text())
    except (OSError, ValueError):
        stored = {}
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return data


def save_settings(data):
    CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd,tmp = tempfile.mkstemp(dir=CONFIG,prefix='.settings-')
    try:
        with os.fdopen(fd,'w') as handle:
            handle.write(json.dumps(data,indent=2))
        os.replace(tmp,CONFIG/'settings.json')
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass


def audit(event, **fields):
    """Append one JSON line to the AI audit log (always on for AI-initiated actions)."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    line = json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'event': event, **fields}, ensure_ascii=False)
    fd = os.open(STATE / 'ai-audit.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def read_audit(limit=200):
    try:
        lines = (STATE / 'ai-audit.log').read_text(encoding='utf-8').splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out
