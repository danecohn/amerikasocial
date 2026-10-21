"""Thin, safe wrapper around the `amerika-agent` command line.

Rules enforced here (see docs/agent/UI.md):
* API keys travel on stdin only: never argv, never environment, never a file, never a log line.
* Every string that comes back from the CLI is scrubbed of the secret that was just sent before anyone can display it.
* All calls are blocking; callers run them in worker threads (see `in_thread`), never on the GTK main loop.
"""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from . import model

BIN_ENV = 'AMERIKA_AGENT_BIN'
PACKAGE = 'amerika-agent'
PROVIDERS = ('anthropic', 'openai')


class CliMissing(Exception):
    """The amerika-agent command is not installed."""


def binary():
    """Absolute path of the CLI, or None. AMERIKA_AGENT_BIN overrides (tests, development)."""
    override = os.environ.get(BIN_ENV)
    if override:
        return override if os.access(override, os.X_OK) else None
    return shutil.which('amerika-agent')


def available():
    return binary() is not None


def _env():
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)  # the shell's layer-shell preload must not leak into the CLI or the engine
    return env


class Result:
    def __init__(self, code, out, err):
        self.code, self.out, self.err = code, out, err

    @property
    def ok(self):
        return self.code == 0

    @property
    def message(self):
        """A one-line human message from stderr or stdout."""
        text = (self.err or self.out or '').strip()
        return text.splitlines()[-1][:300] if text else ''


def run(args, stdin=None, timeout=25, secrets=()):
    """Run `amerika-agent <args>`; `stdin` (str) is written to the child's stdin. Never raises for a failing command;
    raises CliMissing when the CLI does not exist. Output is scrubbed of every string in `secrets`."""
    exe = binary()
    if not exe:
        raise CliMissing(PACKAGE)
    try:
        proc = subprocess.run([exe, *args], input=stdin, capture_output=True, text=True, timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        return Result(124, '', 'The command took too long.')
    except OSError as error:
        return Result(127, '', str(error))
    return Result(proc.returncode, model.scrub(proc.stdout, secrets), model.scrub(proc.stderr, secrets))


def status():
    """Current Status (never raises). Not installed / unreadable output give Status.missing()."""
    try:
        res = run(['status', '--json'], timeout=15)
    except CliMissing:
        return model.Status.missing()
    if not res.ok:
        return model.Status.broken(res.message or 'status failed')
    try:
        return model.Status.from_json(json.loads(res.out))
    except ValueError:
        return model.Status.broken('unreadable status output')


def set_key(provider, key):
    """Store `key` in the keyring via `amerika-agent key set <provider>` (stdin only). Returns (ok, message)."""
    if provider not in PROVIDERS:
        return False, 'Unknown provider.'
    key = (key or '').strip()
    if not key:
        return False, 'Paste a key first.'
    try:
        res = run(['key', 'set', provider], stdin=key + '\n', secrets=(key,))
    except CliMissing:
        return False, 'Amerika Agent is not installed.'
    finally:
        key = None  # drop our reference; the caller already cleared the entry widget
    return res.ok, ('' if res.ok else (res.message or 'The key could not be saved.'))


def clear_key(provider):
    return _simple(['key', 'clear', provider]) if provider in PROVIDERS else (False, 'Unknown provider.')


def _simple(args, timeout=40):
    try:
        res = run(args, timeout=timeout)
    except CliMissing:
        return False, 'Amerika Agent is not installed.'
    return res.ok, res.message


def control(action):
    """start | stop | restart | enable | disable"""
    if action not in ('start', 'stop', 'restart', 'enable', 'disable'):
        return False, 'Unknown action.'
    return _simple([action], timeout=60)


def config_set(name, value):
    if name not in ('model', 'mode', 'autostart'):
        return False, 'Unknown setting.'
    if name == 'mode' and value not in model.MODES:
        return False, 'Unknown mode.'
    if name == 'autostart':
        value = 'true' if value in (True, 'true', 'on', '1') else 'false'
    return _simple(['config', 'set', name, str(value)])


def models(provider):
    """Model ids offered by a provider (one per line). Empty list on any failure."""
    if provider not in PROVIDERS:
        return []
    try:
        res = run(['models', '--provider', provider, '--json'], timeout=60)
    except CliMissing:
        return []
    if not res.ok:
        return []
    try:
        entries = json.loads(res.out).get(provider, [])
        return [item['id'] for item in entries if isinstance(item, dict) and isinstance(item.get('id'), str)]
    except (ValueError, AttributeError):
        # Older development CLIs offered bare identifiers, without headings or descriptions.
        return [line.strip() for line in res.out.splitlines()
                if line.strip() and len(line.split()) == 1 and not line.strip().endswith(':')]


def dashboard_url():
    """The one-time Control UI pairing URL. Held in memory only; never log or persist it."""
    try:
        res = run(['dashboard-url', '--bootstrap'], timeout=45)
    except CliMissing:
        return None
    url = res.out.strip().splitlines()[0].strip() if res.ok and res.out.strip() else None
    return url


def doctor():
    try:
        res = run(['doctor'], timeout=90)
    except CliMissing:
        return 'Amerika Agent is not installed.'
    return (res.out + ('\n' + res.err if res.err.strip() else '')).strip() or '(no output)'


def channels(enabled_names=()):
    """[(name, enabled)] from `channels list`; `enabled_names` (from status) is the authority on enabled state."""
    try:
        res = run(['channels', 'list'], timeout=20)
    except CliMissing:
        return []
    return model.parse_channels(res.out, enabled_names) if res.ok else []


def channel_set(name, on):
    if not model.valid_channel_name(name):
        return False, 'Unknown channel.'
    return _simple(['channels', 'enable' if on else 'disable', name])


class AskHandle:
    """A running `amerika-agent ask`: streams stdout lines to `on_line`, then calls `on_done(code, error_text)`."""

    def __init__(self, text, on_line, on_done):
        self._proc = None
        self._cancelled = False
        self._thread = threading.Thread(target=self._run, args=(text, on_line, on_done), daemon=True)
        self._thread.start()

    def _run(self, text, on_line, on_done):
        exe = binary()
        if not exe:
            on_done(127, 'Amerika Agent is not installed.')
            return
        try:
            self._proc = subprocess.Popen([exe, 'ask'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                          env=_env(), stdin=subprocess.PIPE)
            errors = []
            def drain_errors():
                while True:
                    chunk = self._proc.stderr.read(1024)
                    if not chunk:
                        break
                    errors.append(chunk)
                    if len(errors) > 8:
                        errors.pop(0)
            error_reader = threading.Thread(target=drain_errors, daemon=True)
            error_reader.start()
            self._proc.stdin.write(text)
            self._proc.stdin.close()
            for line in self._proc.stdout:
                if self._cancelled:
                    break
                on_line(line.rstrip('\n'))
            self._proc.wait(timeout=5 if self._cancelled else 600)
            error_reader.join(timeout=1)
            err = ''.join(errors) if not self._cancelled else ''
        except (OSError, subprocess.TimeoutExpired) as error:
            on_done(1, str(error))
            return
        finally:
            for pipe in (self._proc.stdout, self._proc.stderr) if self._proc else ():
                if pipe is not None:
                    pipe.close()
        if not self._cancelled:
            on_done(self._proc.returncode, err.strip()[-300:])

    def cancel(self):
        self._cancelled = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass


def in_thread(work, done=None):
    """Run work() off the main loop; deliver its result to done(result) on the GTK main loop."""
    from gi.repository import GLib

    def run_it():
        try:
            result = work()
        except Exception as error:  # noqa: BLE001 - a UI helper must never kill its thread silently
            result = error
        if done:
            GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=run_it, daemon=True).start()


def activity_path():
    base = Path(os.environ.get('XDG_RUNTIME_DIR') or f'/tmp/amerika-{os.getuid()}')
    return base / 'amerika' / 'agent-activity.json'
