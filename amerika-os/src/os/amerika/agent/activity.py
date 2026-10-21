"""Watches $XDG_RUNTIME_DIR/amerika/agent-activity.json: Gio.FileMonitor for instant updates, a slow poll as fallback
(file monitors miss atomic renames on some filesystems and the file may appear after we start)."""
import os

import gi

gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib  # noqa: E402

from . import cli, model

POLL_SECONDS = 2


class ActivityWatcher:
    """Calls `callback(state, text, since)` on the main loop whenever the activity changes (and once at start)."""

    def __init__(self, callback, path=None):
        self.callback = callback
        self.path = path or cli.activity_path()
        self.current = ('idle', '', 0.0)
        self._monitor = None
        self._timer = 0
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._monitor = Gio.File.new_for_path(str(self.path.parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect('changed', self._changed)
        except (OSError, GLib.Error):
            self._monitor = None
        self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.read(force=True)

    def stop(self):
        self._started = False
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        if self._monitor:
            self._monitor.cancel()
            self._monitor = None

    def _changed(self, _monitor, file, other, _event):
        names = {file.get_basename() if file else None, other.get_basename() if other else None}
        if self.path.name in names:
            self.read()

    def _poll(self):
        if not self._started:
            return False
        self.read()
        return True

    def read(self, force=False):
        try:
            text = self.path.read_text()
        except OSError:
            text = ''
        value = model.parse_activity(text) if text else ('idle', '', 0.0)
        if force or value != self.current:
            self.current = value
            self.callback(*value)
