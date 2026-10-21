"""The AI broker: lets the Claude and ChatGPT apps operate the system, under the user's control.

* A Unix socket in $XDG_RUNTIME_DIR/amerika/ (0700 directory, 0600 socket, same-user peers only) takes tool calls
  from the `amerika-mcp` server that the AI apps launch.
* Every call is checked against the permission mode, may need the user's approval, and is always written to the
  audit log. The shell shows what is happening in the bar and offers a Stop switch that pauses all AI actions.
"""
import json
import os
import socket
import struct
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import gi

gi.require_version('GLib', '2.0')
from gi.repository import GLib, GObject  # noqa: E402

from .. import common
from .tools import Tools

MODES = ('ask', 'safe', 'trusted')
CLIENT_NAMES = {'claude': 'Claude', 'chatgpt': 'ChatGPT'}
APPROVAL_TIMEOUT = 90


class Broker(GObject.Object):
    __gsignals__ = {'activity': (GObject.SignalFlags.RUN_FIRST, None, (str, str, bool)),
                    'paused-changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,))}

    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.tools = Tools(shell)
        self.paused = False
        self._active = {}
        self._server = None
        self._pending = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ policy
    def mode_for(self, client):
        ai = self.shell.settings['ai']
        entry = ai.get('clients', {}).get(client, {})
        mode = entry.get('mode') or ai.get('mode', 'safe')
        return mode if mode in MODES else 'safe'

    def client_enabled(self, client):
        return self.shell.settings['ai'].get('clients', {}).get(client, {}).get('enabled', True)

    def decision(self, client, tool_name):
        """'allow', 'ask' or 'deny' for this client and tool."""
        if self.paused or not self.client_enabled(client):
            return 'deny'
        risk = self.tools.risk(tool_name)
        mode = self.mode_for(client)
        grants = self.shell.settings['ai'].get('clients', {}).get(client, {}).get('always', [])
        if risk == 'read':
            return 'allow'
        if risk == 'critical':
            return 'ask'
        if tool_name in grants and mode != 'ask':
            return 'allow'
        if risk == 'act':
            return 'ask' if mode == 'ask' else 'allow'
        return 'allow' if (mode == 'trusted' and risk == 'sensitive') else 'ask'

    # ------------------------------------------------------------------ main-loop helper
    @staticmethod
    def on_main(fn, *args):
        fut = Future()

        def run():
            try:
                fut.set_result(fn(*args))
            except Exception as error:  # noqa: BLE001 - relayed to the caller thread
                fut.set_exception(error)
            return False
        GLib.idle_add(run)
        return fut

    # ------------------------------------------------------------------ calls
    def handle(self, client, name, args):
        """Runs in a connection thread. Returns (ok, payload)."""
        started = time.time()
        label = CLIENT_NAMES.get(client, client.title())
        if name not in self.tools.table:
            return False, 'unknown tool'
        decision = self.decision(client, name)
        shown = {k: (v if not isinstance(v, str) or len(v) < 200 else v[:200] + '…') for k, v in (args or {}).items()}
        if decision == 'deny':
            common.audit('denied', client=client, tool=name, args=shown, reason='paused or disabled')
            return False, 'AI actions are paused or disabled for this app in Amerika Settings.'
        if decision == 'ask':
            try:
                inner = self.on_main(self.shell.ask_approval, client, name, args or {}, self.tools.risk(name)).result()
                verdict = inner.result(timeout=APPROVAL_TIMEOUT + 5)
            except Exception:  # noqa: BLE001 - timeout or shutdown counts as a refusal
                verdict = 'deny'
            if verdict == 'never' or verdict == 'deny':
                common.audit('denied', client=client, tool=name, args=shown, reason='user declined')
                return False, 'The user declined this action.'
            if verdict == 'always':
                self.on_main(self.grant_always, client, name).result()
        self.on_main(self._begin, client, label, name).result()
        try:
            result = self.on_main(self.tools.call, name, args or {}).result()
            if isinstance(result, Future):  # tools that need the main loop to finish (e.g. the clipboard)
                result = result.result(timeout=10)
            common.audit('call', client=client, tool=name, args=shown, ok=True, ms=round((time.time() - started) * 1000))
            return True, result
        except Exception as error:  # noqa: BLE001
            common.audit('call', client=client, tool=name, args=shown, ok=False, error=str(error)[:300])
            return False, str(error)
        finally:
            self.on_main(self._end, client)

    def grant_always(self, client, name):
        s = self.shell.settings['ai']
        entry = s.setdefault('clients', {}).setdefault(client, {})
        entry.setdefault('always', [])
        if name not in entry['always'] and self.tools.risk(name) != 'critical':
            entry['always'].append(name)
            common.save_settings(self.shell.settings)

    def _begin(self, client, label, tool):
        self._active[client] = time.time()
        self.emit('activity', label, tool, True)

    def _end(self, client):
        def done():
            if time.time() - self._active.get(client, 0) >= 3.5:
                self._active.pop(client, None)
                if not self._active:
                    self.emit('activity', '', '', False)
            return False
        GLib.timeout_add(4000, done)

    # ------------------------------------------------------------------ stop / resume
    def stop_all(self):
        self.set_paused(not self.paused)

    def set_paused(self, paused):
        self.paused = bool(paused)
        if self.paused:
            self.shell.cancel_approvals()
            common.audit('paused')
        else:
            common.audit('resumed')
        self.emit('paused-changed', self.paused)

    # ------------------------------------------------------------------ socket server
    def start(self):
        common.RUNTIME.mkdir(parents=True, exist_ok=True)
        os.chmod(common.RUNTIME, 0o700)
        path = common.CONTROL_SOCKET
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(path))
        os.chmod(path, 0o600)
        self._server.listen(8)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
            _pid, uid, _gid = struct.unpack('3i', creds)
            if uid != os.getuid():
                conn.close()
                continue
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        with conn, conn.makefile('rwb') as stream:
            for raw in stream:
                try:
                    req = json.loads(raw)
                    rid = req.get('id')
                    method = req.get('method')
                    client = str(req.get('client', 'unknown'))[:32]
                    if not client.replace('-', '').replace('_', '').isalnum():
                        client = 'unknown'
                    if method == 'list':
                        resp = {'id': rid, 'ok': True, 'result': self.tools.describe()}
                    elif method == 'call':
                        ok, payload = self.handle(client, str(req.get('tool', '')), req.get('args') or {})
                        resp = {'id': rid, 'ok': ok, 'result' if ok else 'error': payload}
                    elif method == 'status':
                        resp = {'id': rid, 'ok': True, 'result': {'paused': self.paused, 'mode': self.mode_for(client)}}
                    else:
                        resp = {'id': rid, 'ok': False, 'error': 'unknown method'}
                except Exception as error:  # noqa: BLE001
                    resp = {'id': None, 'ok': False, 'error': f'bad request: {error}'}
                stream.write((json.dumps(resp, ensure_ascii=False) + '\n').encode())
                stream.flush()
