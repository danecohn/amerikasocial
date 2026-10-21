"""Receive non-content lifecycle events from the packaged OpenClaw plugin.

The private socket accepts only this user's peers. The public-to-shell snapshot
contains fixed labels, never model text, tool arguments, errors or credentials.
"""
import json
import os
import re
import signal
import socket
import stat
import struct
import time

from . import common

PHASES = {'run-start', 'run-end', 'tool-start', 'tool-end', 'error', 'stopped'}
KEY = re.compile(r'^[a-zA-Z0-9:_.-]{1,128}$')
LABELS = {'idle': '', 'thinking': 'Working on your task', 'tool': 'Using a tool',
          'error': 'A task needs attention; open Amerika Agent'}


class Activity:
    def __init__(self, paths, clock=time.time):
        self.paths, self.clock = paths, clock
        self.runs = {}
        self.since = clock()
        self.state = 'idle'

    def update(self, event):
        if not isinstance(event, dict) or set(event) - {'phase', 'key'}:
            return False
        phase, key = event.get('phase'), event.get('key', 'main')
        if phase not in PHASES or not isinstance(key, str) or not KEY.fullmatch(key):
            return False
        if phase == 'stopped':
            self.runs.clear()
        elif phase == 'run-start':
            if key not in self.runs and len(self.runs) >= 256:
                return False
            self.runs[key] = 0
        elif phase == 'tool-start':
            self.runs[key] = min(self.runs.get(key, 0) + 1, 64)
        elif phase == 'tool-end':
            if key in self.runs:
                self.runs[key] = max(0, self.runs[key] - 1)
        elif phase in ('run-end', 'error'):
            self.runs.pop(key, None)
        state = 'tool' if any(self.runs.values()) else 'thinking' if self.runs else 'error' if phase == 'error' else 'idle'
        if state != self.state:
            self.since = self.clock()
        self.state = state
        self.write()
        return True

    def write(self):
        common.atomic_write(self.paths.activity_file, json.dumps({
            'state': self.state, 'text': LABELS[self.state], 'since': self.since}) + '\n')


def notify_ready():
    address = os.environ.get('NOTIFY_SOCKET')
    if address:
        if address.startswith('@'):
            address = '\0' + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notifier:
            notifier.connect(address)
            notifier.sendall(b'READY=1')


def main(paths, once=False):
    paths.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = paths.runtime_dir.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise common.AgentError('the Agent runtime directory is not a private owned directory')
    os.chmod(paths.runtime_dir, 0o700)
    model = Activity(paths)
    model.write()
    if once:
        return 0
    if paths.activity_socket.exists() or paths.activity_socket.is_symlink():
        old = paths.activity_socket.lstat()
        if not stat.S_ISSOCK(old.st_mode) or old.st_uid != os.getuid():
            raise common.AgentError('refusing to replace an unsafe activity socket path')
        with socket.socket(socket.AF_UNIX) as probe:
            try:
                probe.connect(str(paths.activity_socket))
            except (ConnectionRefusedError, FileNotFoundError):
                paths.activity_socket.unlink(missing_ok=True)
            else:
                raise common.AgentError('the activity bridge is already running')
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    old_handlers = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(paths.activity_socket))
            os.chmod(paths.activity_socket, 0o600)
            server.listen(8)
            server.settimeout(.5)
            notify_ready()
            while running:
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(.5)
                    _pid, uid, _gid = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        continue
                    data = b''
                    try:
                        while len(data) <= 2048 and not data.endswith(b'\n'):
                            chunk = conn.recv(2049 - len(data))
                            if not chunk:
                                break
                            data += chunk
                        if len(data) <= 2048:
                            model.update(json.loads(data))
                    except (socket.timeout, UnicodeError, ValueError):
                        pass
    finally:
        paths.activity_socket.unlink(missing_ok=True)
        model.update({'phase': 'stopped'})
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
    return 0
