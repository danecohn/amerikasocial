"""Paths, settings storage, logging and small helpers shared by the shell, settings app and MCP server."""
import json
import os
import time
from pathlib import Path

APP_NAME = 'Amerika OS'


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
    'dock_pinned': ['com.anthropic.Claude', 'chatgpt', 'amerika-social', 'amerika-venture', 'amerika-files',
                    'amerika-terminal', 'amerika-office', 'amerika-software', 'amerika-settings'],
    'bar_ai_apps': ['com.anthropic.Claude', 'chatgpt'],
    'clock_24h': False,
    # what the Copilot key opens: claude, chatgpt or ask (a picker)
    'copilot_app': 'claude',
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
    CONFIG.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG / 'settings.json.tmp'
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(CONFIG / 'settings.json')


def audit(event, **fields):
    """Append one JSON line to the AI audit log (always on for AI-initiated actions)."""
    STATE.mkdir(parents=True, exist_ok=True)
    line = json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'event': event, **fields}, ensure_ascii=False)
    with open(STATE / 'ai-audit.log', 'a', encoding='utf-8') as handle:
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
