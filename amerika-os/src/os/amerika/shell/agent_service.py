"""Amerika Agent inside the shell: live activity, install/status cache, the Agent window, Stop-switch coupling and the
"agent finished" notification. One instance lives on the Shell as `shell.agent`."""
import subprocess
import threading
import time

import gi

gi.require_version('GLib', '2.0')
from gi.repository import GLib, GObject  # noqa: E402

from ..agent import cli, model
from ..agent.activity import ActivityWatcher
from . import apps

STATUS_POLL_SECONDS = 20


class AgentService(GObject.Object):
    __gsignals__ = {'changed': (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.status = model.Status.missing()
        self.state, self.text, self.since = 'idle', '', 0.0
        self._busy_since = 0.0
        self._watcher = ActivityWatcher(self._activity)
        self._timer = 0
        self._lock = threading.Lock()
        self._stopped_by_pause = False

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        self._watcher.start()
        self.poll_status()
        self._timer = GLib.timeout_add_seconds(STATUS_POLL_SECONDS, lambda: (self.poll_status(), True)[1])
        if getattr(self.shell, 'broker', None) is not None:
            self.shell.broker.connect('paused-changed', lambda _b, paused: self.on_paused(paused))

    def poll_status(self):
        if not cli.available():
            self._set_status(model.Status.missing())
            return
        cli.in_thread(cli.status, lambda s: self._set_status(model.Status.broken(str(s)) if isinstance(s, Exception) else s))

    def _set_status(self, status):
        with self._lock:
            self.status = status
        self.emit('changed')

    # ------------------------------------------------------------------ queries
    @property
    def installed(self):
        return self.status.installed

    @property
    def paused(self):
        broker = getattr(self.shell, 'broker', None)
        return bool(broker and broker.paused)

    def chip(self):
        """(label, css state, visible) for the bar chip."""
        return model.chip_view(self.state, self.text, self.paused, self.installed)

    # ------------------------------------------------------------------ activity + long-task notification
    def _activity(self, state, text, since):
        prev_state, prev_since = self.state, self._busy_since
        self.state, self.text, self.since = state, text, since
        if state in ('thinking', 'tool'):
            if prev_state not in ('thinking', 'tool'):
                self._busy_since = since or time.time()
        elif model.finished_long_task(prev_state, prev_since, state):
            self._notify_finished(state, text)
            self._busy_since = 0.0
        else:
            self._busy_since = 0.0
        self.emit('changed')

    def _notify_finished(self, state, text):
        notifications = getattr(self.shell, 'notifications', None)
        if notifications is None or self.paused:
            return
        if state == 'error':
            title, body = 'Amerika Agent hit a problem', text or 'Open the Agent window to see what happened.'
        else:
            title, body = 'Amerika Agent finished', 'Open the Agent window to see the result.'
        notifications.notify('Amerika Agent', 0, 'amerika-ai', title, body, ai=True)

    # ------------------------------------------------------------------ Stop switch
    def on_paused(self, paused):
        """The global Stop switch pauses every AI action; it must stop the agent engine too."""
        if paused:
            self._stopped_by_pause = True
            self._run_quiet(lambda: cli.control('stop'))
        elif self._stopped_by_pause:
            self._stopped_by_pause = False
            if self.status.autostart:
                self._run_quiet(lambda: cli.control('start'))
        self.emit('changed')

    def _run_quiet(self, fn):
        if cli.available():
            cli.in_thread(fn, lambda _r: self.poll_status())

    # ------------------------------------------------------------------ window
    def open_window(self, start=False):
        """Bring the Agent window forward, starting it when needed (Windows+A, bar chip, dock, Copilot key)."""
        if not start and (self.shell.windows.windows_for('amerika-agent') or apps.lookup('amerika-agent')):
            self.shell.activate_app('amerika-agent')
            return
        try:  # no desktop entry (development) or a start request: run the window directly
            subprocess.Popen(['amerika-agent-window'] + (['--start'] if start else []), stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True, env=cli._env())
        except OSError as error:
            print('could not start the Agent window:', error, flush=True)

    def stop_for_exit(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self._watcher.stop()
