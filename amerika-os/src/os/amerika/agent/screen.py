"""Screenshots for the agent tool `screenshot.take`: KWin's org.kde.KWin.ScreenShot2 over D-Bus (no Spectacle).

KWin only serves ScreenShot2 to clients that declare it in their desktop file (X-KDE-DBUS-Restricted-Interfaces, see
org.amerika.Shell.desktop). Pixels arrive raw through a pipe; we convert them to a PNG in the shell's private state folder
(mode 0700, newest 10 kept). The tool returns the path and size, never the pixels.
"""
import os
import threading
import time

import gi

gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib  # noqa: E402

from .. import common

KEEP = 10
TARGETS = {'screen': 'CaptureWorkspace', 'window': 'CaptureActiveWindow'}
QIMAGE_FORMATS = {4: Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, 5: Gdk.MemoryFormat.B8G8R8A8, 6: Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED}
MAX_BYTES = 128 * 1024 * 1024


def shots_dir():
    d = common.STATE / 'screenshots'
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(d, 0o700)
    return d


def _prune(d):
    files = sorted(d.glob('shot-*.png'), key=lambda p: p.stat().st_mtime)
    for old in files[:-KEEP]:
        try:
            old.unlink()
        except OSError:
            pass


def capture(target='screen', bus=None):
    """Blocking (call from a worker thread). Returns {path, width, height, target}; raises ValueError with a clear message."""
    method = TARGETS.get(target)
    if method is None:
        raise ValueError('target must be screen or window')
    bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
    rfd, wfd = os.pipe()
    chunks, size = [], [0]

    def reader():
        with os.fdopen(rfd, 'rb') as handle:
            while True:
                data = handle.read(1 << 20)
                if not data:
                    return
                size[0] += len(data)
                if size[0] > MAX_BYTES:
                    return
                chunks.append(data)
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        fds = Gio.UnixFDList.new()
        fds.append(wfd)
        options = {'native-resolution': GLib.Variant('b', True), 'include-cursor': GLib.Variant('b', False)}
        if target == 'window':
            options['include-decoration'] = GLib.Variant('b', True)
        params = GLib.Variant('(a{sv}h)', (options, 0))
        try:
            reply, _ = bus.call_with_unix_fd_list_sync('org.kde.KWin', '/org/kde/KWin/ScreenShot2', 'org.kde.KWin.ScreenShot2', method,
                                                       params, GLib.VariantType.new('(a{sv})'), Gio.DBusCallFlags.NONE, 15000, fds, None)
        except GLib.Error as error:
            raise ValueError('The screen could not be captured: ' + error.message.split(':')[-1].strip()[:160]) from None
    finally:
        os.close(wfd)
    thread.join(20)
    meta = reply.unpack()[0]
    width, height, stride, fmt = (int(meta.get(k, 0)) for k in ('width', 'height', 'stride', 'format'))
    data = b''.join(chunks)
    if not (width and height and stride) or len(data) < stride * height or fmt not in QIMAGE_FORMATS:
        raise ValueError('KWin returned a screenshot in a format Amerika cannot read')
    texture = Gdk.MemoryTexture.new(width, height, QIMAGE_FORMATS[fmt], GLib.Bytes.new(data[:stride * height]), stride)
    d = shots_dir()
    path = d / f'shot-{time.strftime("%Y%m%d-%H%M%S")}.png'
    if not texture.save_to_png(str(path)):
        raise ValueError('The screenshot could not be saved')
    os.chmod(path, 0o600)
    _prune(d)
    return {'path': str(path), 'width': width, 'height': height, 'target': target}
