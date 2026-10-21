"""The system-control tools exposed to the AI apps. Each tool has a risk class that the broker enforces:

  read       no side effects
  act        changes the desktop or settings in a reversible way
  sensitive  can lose data, expose private data, run code or change power state (always asks unless the user trusts it)
  critical   power off / reboot / delete: asks every time, in every mode
"""
import json
import os
import re
import signal
import subprocess
import threading
from concurrent.futures import Future
from pathlib import Path

from .. import common, system

HOME = Path.home()


def _schema(props=None, required=()):
    return {'type': 'object', 'properties': props or {}, 'required': list(required), 'additionalProperties': False}


S = {'type': 'string'}
N = {'type': 'number'}
I = {'type': 'integer'}
B = {'type': 'boolean'}


# agent-ui: places inside $HOME that tools may never read (secrets) or write (they would let an agent widen its own powers).
NO_READ = ('.ssh', '.gnupg', '.aws', '.netrc', '.password-store', '.openclaw', '.local/share/keyrings', '.config/amerika-agent',
           '.local/share/amerika-os/agent-window', '.config', '.local/share/keyrings', '.codex', '.claude', '.config/Claude', '.local/state/amerika-agent')
NO_WRITE = NO_READ + ('.config/amerika-os', '.local/state/amerika-os', '.config/autostart', '.config/systemd', '.config/environment.d',
                      '.bashrc', '.bash_profile', '.bash_login', '.bash_logout', '.profile', '.zshrc', '.zprofile', '.zshenv', '.local/bin',
                      '.config/Claude', '.codex', '.claude', '.local/share/amerika-agent', '.local/lib', '.local/share/applications', '.local/share/dbus-1', '.local/share/systemd')


def _protected(path, names):
    rel = path.relative_to(HOME).as_posix() if path != HOME else ''
    return any(rel == n or rel.startswith(n + '/') for n in names)


def _safe_path(raw, must_exist=True, access='list'):
    """Resolve a path inside $HOME. access: 'list' (names only), 'read' or 'write' (the latter two refuse protected places)."""
    path = Path(os.path.expanduser(str(raw))).resolve()
    if not (path == HOME or HOME in path.parents):
        raise ValueError('only files inside your home folder are available')
    if access in ('read', 'write') and _protected(path, NO_WRITE if access == 'write' else NO_READ):
        raise ValueError('this location is protected (keys, logins or Amerika settings); the user must handle it themselves')
    if must_exist and not path.exists():
        raise ValueError('no such file or folder')
    return path


class Tools:
    """Registry. `shell` is the running Shell application (windows, notifications, settings, launcher...)."""

    def __init__(self, shell):
        self.shell = shell
        self.table = {}
        self._commands = {}
        self._command_lock = threading.Lock()
        reg = self._register
        # --- read
        reg('system.info', 'read', 'Operating system, kernel, host name and uptime.', _schema(), self.system_info)
        reg('system.status', 'read', 'Battery, network, volume, brightness, power profile and displays.', _schema(), self.system_status)
        reg('apps.list', 'read', 'Installed applications (id, name, description). Use the id with apps.launch.',
            _schema({'query': S}), self.apps_list)
        reg('windows.list', 'read', 'Open windows with id, title, app, position, size and state.', _schema(), self.windows_list)
        reg('desktops.list', 'read', 'Virtual desktops and the current one.', _schema(), self.desktops_list)
        reg('notifications.list', 'read', 'Recent desktop notifications.', _schema({'limit': I}), self.notifications_list)
        reg('settings.get', 'read', 'Amerika OS preferences (accent, wallpaper, dock, AI mode).', _schema(), self.settings_get)
        reg('files.list', 'read', 'List a folder inside the home directory.', _schema({'path': S}, ['path']), self.files_list)
        # agent-ui: status of the built-in agent. There is deliberately no tool that lets an agent ask, start or message an agent.
        reg('agent.status', 'read', 'Whether Amerika Agent is installed and running, its model and permission mode (never any key).',
            _schema(), self.agent_status)
        # --- act
        reg('apps.launch', 'act', 'Start an application by its id from apps.list.', _schema({'id': S}, ['id']), self.apps_launch)
        reg('windows.focus', 'act', 'Bring a window to the front.', _schema({'id': S}, ['id']), self.win('activate'))
        reg('windows.minimize', 'act', 'Minimize a window.', _schema({'id': S}, ['id']), self.win('minimize'))
        reg('windows.maximize', 'act', 'Maximize a window.', _schema({'id': S}, ['id']), self.win('maximize'))
        reg('windows.restore', 'act', 'Restore a window from maximized, minimized or fullscreen.', _schema({'id': S}, ['id']), self.win('restore'))
        reg('windows.fullscreen', 'act', 'Set or clear fullscreen on a window.', _schema({'id': S, 'on': B}, ['id']), self.windows_fullscreen)
        reg('windows.tile', 'act', 'Snap a window to the left, right, top or bottom half of the screen.',
            _schema({'id': S, 'side': {'type': 'string', 'enum': ['left', 'right', 'top', 'bottom']}}, ['id', 'side']), self.windows_tile)
        reg('windows.move_resize', 'act', 'Move and/or resize a window (pixels).',
            _schema({'id': S, 'x': I, 'y': I, 'w': I, 'h': I}, ['id']), self.windows_move_resize)
        reg('windows.to_desktop', 'act', 'Move a window to a virtual desktop number.', _schema({'id': S, 'desktop': I}, ['id', 'desktop']), self.windows_to_desktop)
        reg('desktops.switch', 'act', 'Switch to a virtual desktop number.', _schema({'desktop': I}, ['desktop']), self.desktops_switch)
        reg('audio.set_volume', 'act', 'Set the output volume (0-150 percent).', _schema({'percent': I}, ['percent']), self.audio_set_volume)
        reg('audio.set_mute', 'act', 'Mute or unmute the output.', _schema({'muted': B}, ['muted']), self.audio_set_mute)
        reg('display.set_brightness', 'act', 'Set screen brightness (1-100 percent).', _schema({'percent': I}, ['percent']), self.display_set_brightness)
        reg('display.set_scale', 'act', 'Set the scale of a display (0.5-4).', _schema({'output': S, 'scale': N}, ['output', 'scale']), self.display_set_scale)
        reg('network.set_wifi', 'act', 'Turn Wi-Fi on or off.', _schema({'on': B}, ['on']), self.network_set_wifi)
        reg('power.set_profile', 'act', 'Set the power profile: power-saver, balanced or performance.',
            _schema({'profile': {'type': 'string', 'enum': ['power-saver', 'balanced', 'performance']}}, ['profile']), self.power_set_profile)
        reg('notifications.send', 'act', 'Show a desktop notification.', _schema({'title': S, 'body': S}, ['title']), self.notifications_send)
        reg('notifications.set_dnd', 'act', 'Turn Do Not Disturb on or off.', _schema({'on': B}, ['on']), self.notifications_dnd)
        reg('settings.set', 'act', 'Change an Amerika OS preference: accent, secondary, wallpaper (horizon, grid, dusk), dock_size (32-96), clock_24h, copilot_app (claude, chatgpt, agent, ask).',
            _schema({'key': {'type': 'string', 'enum': ['accent', 'secondary', 'wallpaper', 'dock_size', 'clock_24h', 'copilot_app']}, 'value': {}}, ['key', 'value']),
            self.settings_set)
        reg('shell.show_launcher', 'act', 'Open or close the launcher.', _schema(), self.show_launcher)
        reg('clipboard.set', 'act', 'Put text on the clipboard.', _schema({'text': S}, ['text']), self.clipboard_set)
        reg('power.lock', 'act', 'Lock the screen.', _schema(), self.power_lock)
        # --- sensitive
        reg('windows.close', 'sensitive', 'Close a window (unsaved work in it may be lost).', _schema({'id': S}, ['id']), self.win('close'))
        reg('screenshot.take', 'sensitive', 'Capture the whole screen (or the active window) to a PNG in Amerika\'s private folder and return its path and size. The screen may show private data.',
            _schema({'target': {'type': 'string', 'enum': ['screen', 'window']}}), self.screenshot_take)
        reg('clipboard.get', 'sensitive', 'Read the clipboard text (it may contain private data).', _schema(), self.clipboard_get)
        reg('files.read', 'sensitive', 'Read a text file inside the home directory (up to 200 KB).', _schema({'path': S}, ['path']), self.files_read)
        reg('files.write', 'sensitive', 'Write a text file inside the home directory (creates or overwrites).',
            _schema({'path': S, 'text': S}, ['path', 'text']), self.files_write)
        reg('power.suspend', 'critical', 'Suspend the computer.', _schema(), lambda a: (system.power_action('suspend'), {'ok': True})[1])
        # --- critical
        reg('power.reboot', 'critical', 'Restart the computer.', _schema(), lambda a: (system.power_action('reboot'), {'ok': True})[1])
        reg('power.poweroff', 'critical', 'Shut the computer down.', _schema(), lambda a: (system.power_action('poweroff'), {'ok': True})[1])
        # agent-ui: shell.run is critical: it asks every time, in every mode, and can never be granted "always"
        reg('shell.run', 'critical', 'Run a shell command as you (30 s limit, output truncated). The user sees the exact command and is asked every time.',
            _schema({'command': S}, ['command']), self.shell_run)
        reg('files.delete', 'critical', 'Move a file inside the home directory to the trash.', _schema({'path': S}, ['path']), self.files_delete)

    # ------------------------------------------------------------------ registry
    def _register(self, name, risk, description, schema, handler):
        self.table[name] = {'risk': risk, 'description': description, 'schema': schema, 'handler': handler}

    def describe(self):
        return [{'name': n, 'description': f"[{t['risk']}] {t['description']}", 'inputSchema': t['schema']} for n, t in self.table.items()]

    def risk(self, name):
        return self.table[name]['risk']

    @staticmethod
    def validate(tool, args):
        schema = tool['schema']
        if not isinstance(args, dict):
            raise ValueError('arguments must be an object')
        for key in schema.get('required', []):
            if key not in args:
                raise ValueError(f'missing argument: {key}')
        for key in args:
            if key not in schema['properties']:
                raise ValueError(f'unknown argument: {key}')
        for key, value in args.items():
            kind = schema['properties'][key].get('type')
            ok = {'string': isinstance(value, str), 'integer': isinstance(value, int) and not isinstance(value, bool),
                  'number': isinstance(value, (int, float)) and not isinstance(value, bool), 'boolean': isinstance(value, bool), None: True}[kind]
            if not ok:
                raise ValueError(f'{key} must be {kind}')
            if schema['properties'][key].get('enum') and value not in schema['properties'][key]['enum']:
                raise ValueError(f'{key} must be one of {schema["properties"][key]["enum"]}')
            if isinstance(value, str) and len(value) > 100_000:
                raise ValueError(f'{key} is too long')

    def call(self, name, args):
        tool = self.table[name]
        self.validate(tool, args)
        return tool['handler'](args)

    # ------------------------------------------------------------------ handlers
    def system_info(self, a):
        return system.os_info()

    def system_status(self, a):
        return {'battery': system.battery(), 'network': system.network(), 'volume': system.volume(),
                'brightness': system.brightness(), 'power_profile': system.power_profile(), 'displays': system.displays()}

    def apps_list(self, a):
        from ..shell import apps
        q = a.get('query', '').lower()
        out = []
        for info in apps.all_apps():
            name = info.get_display_name()
            if q and q not in name.lower() and q not in (info.get_description() or '').lower() and q not in info.get_id().lower():
                continue
            out.append({'id': info.get_id().removesuffix('.desktop'), 'name': name, 'description': info.get_description() or ''})
        return {'apps': out[:300]}

    def apps_launch(self, a):
        from ..shell import apps
        info = apps.lookup(a['id'])
        if not info:
            raise ValueError('unknown application id (see apps.list)')
        apps.launch(info)
        return {'launched': info.get_display_name()}

    def windows_list(self, a):
        return {'windows': [{k: w[k] for k in ('id', 'caption', 'cls', 'x', 'y', 'w', 'h', 'active', 'minimized', 'fullscreen', 'desktops')}
                            for w in self.shell.windows.app_windows()], 'screens': self.shell.windows.state.get('screens', [])}

    def _check_window(self, win_id):
        if not any(w['id'] == str(win_id) for w in self.shell.windows.app_windows()):
            raise ValueError('no such window (see windows.list)')

    def win(self, action):
        def run(a):
            self._check_window(a['id'])
            self.shell.windows.command(action, a['id'])
            return {'ok': True}
        return run

    def windows_fullscreen(self, a):
        self._check_window(a['id'])
        self.shell.windows.command('fullscreen', a['id'], on=a.get('on', True))
        return {'ok': True}

    def windows_tile(self, a):
        self._check_window(a['id'])
        self.shell.windows.command('tile', a['id'], side=a['side'])
        return {'ok': True}

    def windows_move_resize(self, a):
        self._check_window(a['id'])
        self.shell.windows.command('move_resize', a['id'], **{k: a[k] for k in ('x', 'y', 'w', 'h') if k in a})
        return {'ok': True}

    def windows_to_desktop(self, a):
        self._check_window(a['id'])
        self.shell.windows.command('to_desktop', a['id'], desktop=a['desktop'])
        return {'ok': True}

    def desktops_list(self, a):
        return {'desktops': self.shell.windows.state.get('desktops', []), 'current': self.shell.windows.state.get('current', 1)}

    def desktops_switch(self, a):
        self.shell.windows.switch_desktop(a['desktop'])
        return {'ok': True}

    def audio_set_volume(self, a):
        return system.set_volume(a['percent'])

    def audio_set_mute(self, a):
        return system.set_mute(a['muted'])

    def display_set_brightness(self, a):
        return system.set_brightness(a['percent'])

    def display_set_scale(self, a):
        return {'displays': system.set_display_scale(a['output'], a['scale'])}

    def network_set_wifi(self, a):
        return {'wifi_enabled': system.set_wifi(a['on'])}

    def power_set_profile(self, a):
        return {'profile': system.set_power_profile(a['profile'])}

    def notifications_list(self, a):
        n = max(1, min(100, int(a.get('limit', 20))))
        return {'notifications': [{k: h[k] for k in ('id', 'app', 'summary', 'body', 'time')} for h in self.shell.notifications.history[:n]]}

    def notifications_send(self, a):
        nid = self.shell.notifications.notify('AI', 0, '', a['title'], a.get('body', ''), ai=True)
        return {'id': nid}

    def notifications_dnd(self, a):
        self.shell.notifications.set_dnd(a['on'])
        return {'dnd': self.shell.notifications.dnd}

    def settings_get(self, a):
        s = self.shell.settings
        return {k: s.get(k) for k in ('accent', 'secondary', 'wallpaper', 'dock_size', 'clock_24h', 'copilot_app', 'dock_pinned')} | {'ai_mode': s['ai']['mode']}

    def settings_set(self, a):
        key, value = a['key'], a['value']
        from ..settings.api import validate
        validate(key, value)
        self.shell.update_setting(key, value)
        return {'ok': True, key: value}

    def agent_status(self, a):
        from ..agent import cli, model
        svc = getattr(self.shell, 'agent', None)
        if svc is not None and getattr(svc, 'status', None) is not None:
            return model.public_status(svc.status, svc.state, svc.text)
        fut = Future()

        def work():
            try:
                fut.set_result(model.public_status(cli.status()))
            except Exception as error:  # noqa: BLE001 - relayed to the caller
                fut.set_exception(error)
        threading.Thread(target=work, daemon=True).start()
        return fut

    def screenshot_take(self, a):
        from ..agent import screen
        fut = Future()

        def work():
            try:
                fut.set_result(screen.capture(a.get('target', 'screen')))
            except Exception as error:  # noqa: BLE001 - relayed to the caller
                fut.set_exception(error)
        threading.Thread(target=work, daemon=True).start()
        return fut

    def show_launcher(self, a):
        self.shell.toggle_launcher()
        return {'ok': True}

    def clipboard_set(self, a):
        self.shell.clipboard_set(a['text'])
        return {'ok': True}

    def clipboard_get(self, a):
        fut = Future()
        self.shell.clipboard_get(lambda text: fut.set_result({'text': text}))
        return fut

    def power_lock(self, a):
        system.lock_session()
        return {'ok': True}

    def files_list(self, a):
        path = _safe_path(a['path'])
        if not path.is_dir():
            raise ValueError('not a folder')
        entries = []
        for p in sorted(path.iterdir())[:500]:
            try:
                entries.append({'name': p.name, 'dir': p.is_dir(), 'size': p.stat().st_size if p.is_file() else None})
            except OSError:
                continue
        return {'path': str(path), 'entries': entries}

    def files_read(self, a):
        path = _safe_path(a['path'], access='read')
        if not path.is_file():
            raise ValueError('not a file')
        data = path.read_bytes()[:200_000]
        return {'path': str(path), 'text': data.decode('utf-8', 'replace'), 'truncated': path.stat().st_size > 200_000}

    def files_write(self, a):
        path = _safe_path(a['path'], must_exist=False, access='write')
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.amerika-tmp')
        tmp.write_text(a['text'], encoding='utf-8')
        tmp.replace(path)
        return {'path': str(path), 'bytes': len(a['text'].encode())}

    def files_delete(self, a):
        path = _safe_path(a['path'], access='write')
        code = subprocess.run(['gio', 'trash', '--', str(path)], capture_output=True, timeout=15).returncode
        if code:
            raise ValueError('could not move to trash')
        return {'trashed': str(path)}

    @staticmethod
    def _signal_command(proc, sig):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass

    def cancel_commands(self):
        """Stop only process groups this broker created; never block the GTK loop."""
        with self._command_lock:
            for proc, cancelled in self._commands.items():
                cancelled.set()
                self._signal_command(proc, signal.SIGTERM)

    def shell_run(self, a):
        # The broker calls this on GTK's thread. Move communicate/wait to a
        # worker so the Stop button remains usable throughout a long command.
        env = dict(os.environ)
        for key in ('LD_PRELOAD', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                    'OPENCLAW_GATEWAY_TOKEN', 'OPENCLAW_GATEWAY_PASSWORD'):
            env.pop(key, None)
        proc = subprocess.Popen(['/bin/sh', '-c', a['command']], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, cwd=str(HOME), env=env, start_new_session=True)
        cancelled = threading.Event()
        future = Future()
        with self._command_lock:
            self._commands[proc] = cancelled

        def work():
            import time
            deadline = time.monotonic() + 30
            try:
                while True:
                    try:
                        stdout, stderr = proc.communicate(timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        if cancelled.is_set() or time.monotonic() >= deadline:
                            self._signal_command(proc, signal.SIGKILL)
                            proc.communicate()
                            raise ValueError('The command was stopped.' if cancelled.is_set()
                                             else 'The command took longer than 30 seconds.')
                if cancelled.is_set():
                    raise ValueError('The command was stopped.')
                future.set_result({'exit_code': proc.returncode, 'stdout': stdout[-20000:], 'stderr': stderr[-8000:]})
            except Exception as error:
                future.set_exception(error)
            finally:
                with self._command_lock:
                    self._commands.pop(proc, None)
        threading.Thread(target=work, daemon=True).start()
        return future
