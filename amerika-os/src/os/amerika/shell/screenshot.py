"""Screenshots, annotation and screen recording.

Capture goes through KWin's org.kde.KWin.ScreenShot2 D-Bus interface (the shell is authorised to use it by the
X-KDE-DBUS-Restricted-Interfaces line in org.amerika.Shell.desktop). Spectacle is only a fallback when that is refused.
Nothing here reads the screen unless the user pressed a capture key or the agent asked through org.amerika.Desktop.
"""
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

import cairo
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from .. import common, deskconf
from . import dutil, layer

SHOT_SERVICE, SHOT_PATH, SHOT_IFACE = 'org.kde.KWin', '/org/kde/KWin/ScreenShot2', 'org.kde.KWin.ScreenShot2'
MAX_PIXELS = 8192 * 8192
# QImage::Format values KWin may hand back -> cairo format. 6 (ARGB32_Premultiplied) is what KWin produces.
QFORMAT_TO_CAIRO = {4: cairo.FORMAT_RGB24, 6: cairo.FORMAT_ARGB32}
COLORS = {'red': (1.0, 0.18, 0.39), 'cyan': (0.1, 0.89, 1.0), 'yellow': (1.0, 0.85, 0.1), 'white': (1, 1, 1), 'black': (0, 0, 0)}


# ------------------------------------------------------------------------------------------------ raw image handling
def surface_from_raw(data, width, height, stride, qformat):
    """cairo ImageSurface from a KWin raw reply. Only the 32-bit layouts KWin produces are accepted."""
    if qformat not in QFORMAT_TO_CAIRO:
        raise ValueError(f'unsupported pixel format {qformat}')
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS or stride < width * 4:
        raise ValueError('invalid image geometry')
    if len(data) < stride * height:
        raise ValueError('truncated image data')
    buf = bytearray(data[:stride * height])
    return cairo.ImageSurface.create_for_data(buf, QFORMAT_TO_CAIRO[qformat], width, height, stride)


def texture_from_surface(surface):
    surface.flush()
    return Gdk.MemoryTexture.new(surface.get_width(), surface.get_height(), Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                 GLib.Bytes.new(bytes(surface.get_data())), surface.get_stride())


def crop_surface(surface, x, y, w, h):
    """New surface with the sub-rectangle (clamped to the image)."""
    x, y = max(0, int(x)), max(0, int(y))
    w, h = min(int(w), surface.get_width() - x), min(int(h), surface.get_height() - y)
    if w <= 0 or h <= 0:
        raise ValueError('empty crop')
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(out)
    ctx.set_source_surface(surface, -x, -y)
    ctx.paint()
    return out


def scaled_surface(surface, max_width):
    if surface.get_width() <= max_width:
        return surface
    k = max_width / surface.get_width()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, max_width, max(1, round(surface.get_height() * k)))
    ctx = cairo.Context(out)
    ctx.scale(k, k)
    ctx.set_source_surface(surface, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    return out


def png_bytes(surface):
    import io
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ KWin capture client
class CaptureError(Exception):
    pass


class KWinCapture:
    """Blocking ScreenShot2 calls (run them off the main thread, see `run_async`)."""

    def __init__(self, bus=None):
        self.bus = bus
        self.denied = False

    def _bus(self):
        if self.bus is None:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        return self.bus

    def available(self):
        try:
            owner = self._bus().call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'NameHasOwner',
                                          GLib.Variant('(s)', (SHOT_SERVICE,)), None, Gio.DBusCallFlags.NONE, 1500, None)
            return bool(owner.unpack()[0]) and not self.denied
        except GLib.Error:
            return False

    def _call(self, method, sig, args, cursor=False, decoration=False):
        options = {'native-resolution': GLib.Variant('b', True), 'include-cursor': GLib.Variant('b', bool(cursor)),
                   'include-decoration': GLib.Variant('b', bool(decoration))}
        rfd, wfd = os.pipe()
        chunks = []

        def drain():
            with os.fdopen(rfd, 'rb', closefd=True) as handle:
                chunks.append(handle.read())
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        fds = Gio.UnixFDList.new()
        index = fds.append(wfd)
        os.close(wfd)
        try:
            reply, _out = self._bus().call_with_unix_fd_list_sync(
                SHOT_SERVICE, SHOT_PATH, SHOT_IFACE, method, GLib.Variant('(' + sig + 'a{sv}h)', tuple(args) + (options, index)),
                None, Gio.DBusCallFlags.NONE, 15000, fds, None)
        except GLib.Error as error:
            for fd in fds.steal_fds():
                os.close(fd)
            reader.join(2)
            if 'NoAuthorized' in error.message:
                self.denied = True
                raise CaptureError('The shell is not authorised to capture the screen (see docs/DESKTOP-APIS.md).') from error
            raise CaptureError(error.message) from error
        for fd in fds.steal_fds():  # our copy of the pipe's write end; KWin closed its own when the image was written
            os.close(fd)
        reader.join(10)
        meta = reply.unpack()[0]
        if meta.get('type') != 'raw' or not chunks:
            raise CaptureError('unexpected reply from KWin')
        return surface_from_raw(chunks[0], int(meta['width']), int(meta['height']), int(meta['stride']), int(meta['format'])), meta

    def workspace(self, **kw):
        return self._call('CaptureWorkspace', '', (), **kw)

    def screen(self, name, **kw):
        return self._call('CaptureScreen', 's', (name,), **kw)

    def active_screen(self, **kw):
        return self._call('CaptureActiveScreen', '', (), **kw)

    def active_window(self, **kw):
        return self._call('CaptureActiveWindow', '', (), **kw)

    def window(self, handle, **kw):
        return self._call('CaptureWindow', 's', (handle,), **kw)

    def area(self, x, y, w, h, **kw):
        return self._call('CaptureArea', 'iiuu', (int(x), int(y), int(w), int(h)), **kw)

    def interactive(self, kind, **kw):
        return self._call('CaptureInteractive', 'u', (int(kind),), **kw)


def run_async(fn, callback):
    """Run fn() on a worker thread, then callback(result, error) on the GTK main loop."""
    def work():
        try:
            result, error = fn(), None
        except Exception as exc:  # noqa: BLE001 - delivered to the callback
            result, error = None, exc
        GLib.idle_add(lambda: (callback(result, error), False)[1])
    threading.Thread(target=work, daemon=True).start()


class ThumbnailCache:
    """Window thumbnails for the switcher and overview: captured through KWin, scaled to a small cache, dropped on window changes."""

    def __init__(self, capture, width=360):
        self.capture, self.width = capture, width
        self._items = {}      # id -> (stamp, texture)
        self._busy = set()

    def get(self, win_id, stamp, callback):
        item = self._items.get(win_id)
        if item and item[0] == stamp:
            callback(item[1])
            return
        if win_id in self._busy or not self.capture.available():
            if item:
                callback(item[1])
            return
        self._busy.add(win_id)

        def work():
            surface, _meta = self.capture.window(win_id)
            return texture_from_surface(scaled_surface(surface, self.width))

        def done(texture, error):
            self._busy.discard(win_id)
            if error is None and texture is not None:
                self._items[win_id] = (stamp, texture)
                callback(texture)
        run_async(work, done)

    def forget(self, alive_ids):
        for key in [k for k in self._items if k not in alive_ids]:
            del self._items[key]


# ------------------------------------------------------------------------------------------------ files
def screenshots_dir(conf=None):
    configured = (conf or {}).get('dir') or ''
    base = Path(configured).expanduser() if configured else Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                                                                or Path.home() / 'Pictures') / 'Screenshots'
    base.mkdir(parents=True, exist_ok=True)
    return base


def unique_path(folder, prefix='Screenshot', ext='png', now=None):
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(now or time.time()))
    path = Path(folder) / f'{prefix}_{stamp}.{ext}'
    n = 1
    while path.exists():
        n += 1
        path = Path(folder) / f'{prefix}_{stamp}_{n}.{ext}'
    return path


def agent_dir():
    """Private directory for captures requested by the agent (0700), pruned to the newest 20."""
    d = common.RUNTIME / 'shots'
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    old = sorted(d.glob('agent-*.png'), key=lambda p: p.stat().st_mtime)[:-20]
    for p in old:
        p.unlink(missing_ok=True)
    return d


# ------------------------------------------------------------------------------------------------ annotation model
class Shape:
    KINDS = ('arrow', 'rect', 'text', 'blur')

    def __init__(self, kind, x1, y1, x2=None, y2=None, color='red', text='', size=4):
        if kind not in self.KINDS:
            raise ValueError('unknown shape')
        self.kind, self.x1, self.y1 = kind, x1, y1
        self.x2, self.y2 = (x1 if x2 is None else x2), (y1 if y2 is None else y2)
        self.color, self.text, self.size = color, text, size

    def rect(self):
        return min(self.x1, self.x2), min(self.y1, self.y2), abs(self.x2 - self.x1), abs(self.y2 - self.y1)


def pixelate(ctx, base, x, y, w, h, block=14):
    """Blur by pixelation (irreversible, unlike a gaussian blur on small text)."""
    x, y = max(0, int(x)), max(0, int(y))
    w, h = min(int(w), base.get_width() - x), min(int(h), base.get_height() - y)
    if w < 2 or h < 2:
        return
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w // block), max(1, h // block))
    sc = cairo.Context(small)
    sc.scale(small.get_width() / w, small.get_height() / h)
    sc.set_source_surface(base, -x, -y)
    sc.get_source().set_filter(cairo.FILTER_BILINEAR)
    sc.paint()
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    ctx.translate(x, y)
    ctx.scale(w / small.get_width(), h / small.get_height())
    ctx.set_source_surface(small, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_NEAREST)
    ctx.paint()
    ctx.restore()


def draw_shapes(ctx, base, shapes):
    import math
    for s in shapes:
        r, g, b = COLORS.get(s.color, COLORS['red'])
        ctx.set_source_rgb(r, g, b)
        ctx.set_line_width(s.size)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        x, y, w, h = s.rect()
        if s.kind == 'rect':
            ctx.rectangle(x, y, w, h)
            ctx.stroke()
        elif s.kind == 'arrow':
            ang = math.atan2(s.y2 - s.y1, s.x2 - s.x1)
            head = max(12, s.size * 4)
            ctx.move_to(s.x1, s.y1)
            ctx.line_to(s.x2, s.y2)
            ctx.stroke()
            ctx.move_to(s.x2, s.y2)
            for off in (math.pi * 0.85, -math.pi * 0.85):
                ctx.line_to(s.x2 + head * math.cos(ang + off), s.y2 + head * math.sin(ang + off))
                ctx.move_to(s.x2, s.y2)
            ctx.stroke()
        elif s.kind == 'text' and s.text:
            ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(max(14, s.size * 5))
            ext = ctx.text_extents(s.text)
            ctx.set_source_rgba(0, 0, 0, 0.55)
            ctx.rectangle(s.x1 - 4, s.y1 - ext.height - 4, ext.width + 8, ext.height + 10)
            ctx.fill()
            ctx.set_source_rgb(r, g, b)
            ctx.move_to(s.x1, s.y1)
            ctx.show_text(s.text)
        elif s.kind == 'blur':
            pixelate(ctx, base, x, y, w, h)


def render_annotated(base, shapes):
    """New surface = base with the shapes burned in (what is saved and copied)."""
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, base.get_width(), base.get_height())
    ctx = cairo.Context(out)
    ctx.set_source_surface(base, 0, 0)
    ctx.paint()
    draw_shapes(ctx, base, shapes)
    return out


# ------------------------------------------------------------------------------------------------ recording
def detect_recording(globals_=None, which=shutil.which):
    """Which recording backends can work here. `globals_` is the set of Wayland globals when known."""
    gst = bool(which('gst-launch-1.0'))
    out = {'kwin-frames': gst, 'wf-recorder': False, 'portal': False, 'best': None}
    if which('wf-recorder') and globals_ and ({'zwlr_screencopy_manager_v1', 'ext_image_copy_capture_manager_v1'} & set(globals_)):
        out['wf-recorder'] = True
    if gst and which('pw-cli'):
        out['portal'] = False  # the PipeWire portal flow needs a portal backend that is not part of this image yet
    for name in ('wf-recorder', 'kwin-frames'):
        if out[name]:
            out['best'] = name
            break
    return out


def gst_frames_command(width, height, fps, path):
    """gst-launch argv that encodes raw BGRA frames from stdin into a WebM file."""
    if width % 2 or height % 2:
        width, height = width - width % 2, height - height % 2
    return ['gst-launch-1.0', '-q', '-e', 'fdsrc', 'fd=0', 'blocksize=%d' % (width * height * 4), '!', 'rawvideoparse',
            'format=bgra', f'width={width}', f'height={height}', f'framerate={fps}/1', '!', 'videoconvert', '!',
            'vp8enc', 'deadline=1', 'cpu-used=8', 'threads=4', 'target-bitrate=4000000', '!', 'webmmux', '!',
            'filesink', f'location={path}']


class Recorder(GObject.Object):
    """Screen recording. 'kwin-frames' polls KWin's screenshot interface and encodes with GStreamer (needs no portal, no PipeWire,
    modest frame rate); 'wf-recorder' is used only where the compositor offers wlr-screencopy."""
    __gsignals__ = {'state': (GObject.SignalFlags.RUN_FIRST, None, (bool,))}

    def __init__(self, capture, backend='auto', fps=10):
        super().__init__()
        self.capture, self.fps = capture, fps
        self.backend = backend
        self.path = None
        self.running = False
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self.error = None

    def start(self, folder, area=None, screen=None):
        """area = (x, y, w, h) in global coordinates or None for the whole `screen` (output name)."""
        if self.running:
            return None
        info = detect_recording(self._globals())
        backend = info['best'] if self.backend == 'auto' else self.backend
        if not backend or not info.get(backend):
            raise CaptureError('No screen recorder is available (needs GStreamer, or wf-recorder on a compositor that supports it).')
        self.path = unique_path(folder, 'Recording', 'webm' if backend == 'kwin-frames' else 'mp4')
        self._stop.clear()
        self.error = None
        if backend == 'wf-recorder':
            argv = ['wf-recorder', '-f', str(self.path)]
            if area:
                argv += ['-g', '%d,%d %dx%d' % area]
            self._proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self._thread = threading.Thread(target=self._frames, args=(area, screen), daemon=True)
            self._thread.start()
        self.running = True
        self.emit('state', True)
        return self.path

    @staticmethod
    def _globals():
        try:
            from .. import wl
            return wl.list_globals()
        except Exception:  # noqa: BLE001 - detection must never raise
            return set()

    def _grab(self, area, screen):
        if area:
            return self.capture.area(*area)[0]
        return self.capture.screen(screen)[0] if screen else self.capture.active_screen()[0]

    def _frames(self, area, screen):
        proc = None
        try:
            first = self._grab(area, screen)
            w, h = first.get_width(), first.get_height()
            w, h = w - w % 2, h - h % 2
            proc = subprocess.Popen(gst_frames_command(w, h, self.fps, self.path), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            self._proc = proc
            period, frame, due = 1.0 / self.fps, first, time.monotonic()
            while not self._stop.is_set():
                self._write(proc, frame, w, h)
                due += period
                delay = due - time.monotonic()
                if delay > 0:
                    self._stop.wait(delay)
                    if self._stop.is_set():
                        break
                try:
                    frame = self._grab(area, screen)
                except CaptureError:
                    pass
                lag = time.monotonic() - due
                while lag > period and not self._stop.is_set():  # capture was slow: repeat the last frame to keep real time
                    self._write(proc, frame, w, h)
                    due += period
                    lag -= period
        except (CaptureError, OSError, ValueError) as error:
            self.error = str(error)
        finally:
            if proc is not None:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            GLib.idle_add(self._finished)

    @staticmethod
    def _write(proc, surface, w, h):
        stride = surface.get_stride()
        data = bytes(surface.get_data())
        if stride == w * 4 and surface.get_width() == w and surface.get_height() == h:
            proc.stdin.write(data)
        else:
            rows = [data[y * stride:y * stride + w * 4] for y in range(h)]
            proc.stdin.write(b''.join(rows))

    def stop(self):
        if not self.running:
            return None
        self._stop.set()
        if self._proc is not None and self._thread is None:  # wf-recorder: SIGINT finalises the file
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._finished()
        return self.path

    def _finished(self):
        if self.running:
            self.running = False
            self.emit('state', False)
        return False


# ------------------------------------------------------------------------------------------------ UI: annotation editor
class Annotator(Gtk.Window):
    def __init__(self, service, surface, path):
        super().__init__(title='Annotate screenshot')
        self.service, self.base, self.path = service, surface, Path(path)
        self.shapes, self.tool, self.color, self.draft = [], 'arrow', 'red', None
        self.add_css_class('am-dialog')
        iw, ih = surface.get_width(), surface.get_height()
        k = min(1.0, 1280 / iw, 760 / ih)
        self.set_default_size(max(520, int(iw * k)), int(ih * k) + 64)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_child(root)
        bar = Gtk.Box(spacing=6)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(bar, f'set_margin_{m}')(6)
        self.tool_buttons = {}
        first = None
        for kind, text in (('arrow', 'Arrow'), ('rect', 'Rectangle'), ('text', 'Text'), ('blur', 'Blur')):
            b = Gtk.ToggleButton(label=text)
            b.add_css_class('am-secondary')
            if first is None:
                first = b
                b.set_active(True)
            else:
                b.set_group(first)
            b.connect('toggled', lambda btn, kd=kind: setattr(self, 'tool', kd) if btn.get_active() else None)
            self.tool_buttons[kind] = b
            bar.append(b)
        for name in ('red', 'cyan', 'yellow', 'white', 'black'):
            sw = Gtk.Button()
            sw.set_size_request(22, 22)
            sw.set_tooltip_text(name)
            css = Gtk.CssProvider()
            r, g, b_ = COLORS[name]
            css.load_from_string('button { background: rgb(%d,%d,%d); border-radius: 999px; min-width: 22px; min-height: 22px; '
                                 'padding: 0; border: 1px solid rgba(255,255,255,.5); }' % (r * 255, g * 255, b_ * 255))
            sw.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            sw.connect('clicked', lambda _b, n=name: setattr(self, 'color', n))
            bar.append(sw)
        spacer = Gtk.Box(hexpand=True)
        bar.append(spacer)
        for text, fn, css in (('Undo', self.undo, 'am-secondary'), ('Copy', self.copy, 'am-secondary'), ('Save', self.save, 'am-primary')):
            b = Gtk.Button(label=text)
            b.add_css_class(css)
            b.connect('clicked', lambda _b, f=fn: f())
            bar.append(b)
        root.append(bar)
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.canvas.set_draw_func(self._draw)
        drag = Gtk.GestureDrag()
        drag.connect('drag-begin', self._begin)
        drag.connect('drag-update', self._update)
        drag.connect('drag-end', self._end)
        self.canvas.add_controller(drag)
        root.append(self.canvas)
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._key)
        self.add_controller(keys)

    # canvas <-> image coordinates
    def _fit(self):
        cw, ch = max(1, self.canvas.get_width()), max(1, self.canvas.get_height())
        k = min(cw / self.base.get_width(), ch / self.base.get_height())
        ox, oy = (cw - self.base.get_width() * k) / 2, (ch - self.base.get_height() * k) / 2
        return k, ox, oy

    def _to_image(self, x, y):
        k, ox, oy = self._fit()
        return (x - ox) / k, (y - oy) / k

    def _draw(self, _area, ctx, _w, _h):
        k, ox, oy = self._fit()
        ctx.translate(ox, oy)
        ctx.scale(k, k)
        ctx.set_source_surface(self.base, 0, 0)
        ctx.paint()
        draw_shapes(ctx, self.base, self.shapes + ([self.draft] if self.draft else []))

    def _begin(self, _g, x, y):
        self._origin = self._to_image(x, y)
        if self.tool == 'text':
            self._ask_text(x, y)
            self.draft = None
            return
        self.draft = Shape(self.tool, *self._origin, color=self.color)

    def _update(self, _g, dx, dy):
        if self.draft is None:
            return
        k, _ox, _oy = self._fit()
        self.draft.x2, self.draft.y2 = self._origin[0] + dx / k, self._origin[1] + dy / k
        self.canvas.queue_draw()

    def _end(self, _g, _dx, _dy):
        if self.draft is not None:
            x, y, w, h = self.draft.rect()
            if w > 3 or h > 3:
                self.shapes.append(self.draft)
            self.draft = None
            self.canvas.queue_draw()

    def _ask_text(self, x, y):
        pop = Gtk.Popover()
        pop.set_parent(self.canvas)
        pop.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
        entry = Gtk.Entry(placeholder_text='Text, then Enter', width_chars=24)
        origin = self._origin

        def done(e):
            if e.get_text().strip():
                self.shapes.append(Shape('text', origin[0], origin[1], color=self.color, text=e.get_text().strip()))
                self.canvas.queue_draw()
            pop.popdown()
        entry.connect('activate', done)
        pop.set_child(entry)
        pop.connect('closed', lambda p: GLib.idle_add(p.unparent))
        pop.popup()
        entry.grab_focus()

    def _key(self, _c, keyval, _code, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval == Gdk.KEY_z and state & Gdk.ModifierType.CONTROL_MASK:
            self.undo()
            return True
        return False

    def undo(self):
        if self.shapes:
            self.shapes.pop()
            self.canvas.queue_draw()

    def result(self):
        return render_annotated(self.base, self.shapes)

    def save(self):
        self.result().write_to_png(str(self.path))
        self.service.copy_surface(self.result(), self.path)
        self.service.toast('Annotated screenshot saved', self.path.name)
        self.close()

    def copy(self):
        self.service.copy_surface(self.result(), None)
        self.service.toast('Copied to the clipboard', 'The annotated screenshot')


# ------------------------------------------------------------------------------------------------ UI: capture overlay
class CaptureOverlay(Gtk.Window):
    """Frozen-screen overlay: drag a region, click a window, or confirm the screen. The toolbar switches mode."""

    def __init__(self, service, frozen, screen, windows, mode='region', record=False):
        super().__init__(application=service.shell, title='Amerika Capture')
        self.service, self.frozen, self.screen, self.windows = service, frozen, screen, windows
        self.mode, self.record = mode, record
        self.sel = None          # (x, y, w, h) in widget coordinates
        self.hover = None
        self.delay = 0
        self.annotate = bool(service.conf('annotate'))
        self.add_css_class('am-capture')
        monitor = dutil.monitor_by_name(screen.get('name'))
        if layer.LS is not None and layer.available():
            layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, keyboard='exclusive',
                        namespace='amerika-capture')
            if monitor is not None:
                layer.LS.set_monitor(self, monitor)
        overlay = Gtk.Overlay()
        self.set_child(overlay)
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.canvas.set_draw_func(self._draw)
        overlay.set_child(self.canvas)
        drag = Gtk.GestureDrag()
        drag.connect('drag-begin', self._begin)
        drag.connect('drag-update', self._update)
        drag.connect('drag-end', self._end)
        self.canvas.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect('motion', self._motion)
        self.canvas.add_controller(motion)
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._key)
        self.add_controller(keys)
        overlay.add_overlay(self._toolbar())
        self.size_label = dutil.label('', 'am-mono am-capture-size')
        self.size_label.set_halign(Gtk.Align.START)
        self.size_label.set_valign(Gtk.Align.START)
        self.size_label.set_visible(False)
        overlay.add_overlay(self.size_label)

    # ---- toolbar
    def _toolbar(self):
        bar = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
        bar.add_css_class('am-panel')
        bar.add_css_class('am-capture-bar')
        bar.set_margin_bottom(54)
        first = None
        self.mode_buttons = {}
        for mode, text in (('region', 'Region'), ('window', 'Window'), ('screen', 'Screen')):
            b = Gtk.ToggleButton(label=text)
            b.add_css_class('am-secondary')
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.set_active(mode == self.mode)
            b.connect('toggled', lambda btn, m=mode: self._set_mode(m) if btn.get_active() else None)
            self.mode_buttons[mode] = b
            bar.append(b)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        rec = Gtk.ToggleButton(label='Record')
        rec.add_css_class('am-secondary')
        rec.set_active(self.record)
        rec.set_sensitive(self.service.recording_possible())
        if not rec.get_sensitive():
            rec.set_tooltip_text('No screen recorder is available on this system')
        rec.connect('toggled', lambda b: setattr(self, 'record', b.get_active()))
        self.record_button = rec
        bar.append(rec)
        ann = Gtk.CheckButton(label='Annotate')
        ann.set_active(self.annotate)
        ann.connect('toggled', lambda b: setattr(self, 'annotate', b.get_active()))
        bar.append(ann)
        delay = Gtk.DropDown.new_from_strings(['No delay', '3 s', '5 s', '10 s'])
        delay.connect('notify::selected', lambda d, _p: setattr(self, 'delay', (0, 3, 5, 10)[d.get_selected()]))
        bar.append(delay)
        go = Gtk.Button(label='Capture')
        go.add_css_class('am-primary')
        go.connect('clicked', lambda *_: self.confirm())
        bar.append(go)
        close = Gtk.Button(label='Cancel')
        close.add_css_class('am-secondary')
        close.connect('clicked', lambda *_: self.cancel())
        bar.append(close)
        return bar

    def _set_mode(self, mode):
        self.mode, self.sel = mode, None
        self.size_label.set_visible(False)
        self.canvas.queue_draw()

    # ---- geometry
    def _scale(self):
        return self.frozen.get_width() / max(1, self.canvas.get_width() or self.screen.get('w', 1))

    def _window_rects(self):
        sx, sy = self.screen.get('x', 0), self.screen.get('y', 0)
        out = []
        for w in sorted(self.windows, key=lambda w: -w.get('z', 0)):
            out.append((w, (w['x'] - sx, w['y'] - sy, w['w'], w['h'])))
        return out

    def _motion(self, _c, x, y):
        if self.mode != 'window':
            return
        hit = None
        for w, (rx, ry, rw, rh) in self._window_rects():
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                hit = w
                break
        if hit is not (self.hover or {}).get('_w'):
            self.hover = {'_w': hit} if hit else None
            self.canvas.queue_draw()

    def _begin(self, _g, x, y):
        self._origin = (x, y)
        if self.mode == 'region':
            self.sel = (x, y, 0, 0)

    def _update(self, _g, dx, dy):
        if self.mode != 'region':
            return
        x0, y0 = self._origin
        self.sel = (min(x0, x0 + dx), min(y0, y0 + dy), abs(dx), abs(dy))
        k = self._scale()
        self.size_label.set_text(f'{round(self.sel[2] * k)} x {round(self.sel[3] * k)}')
        self.size_label.set_margin_start(int(self.sel[0]))
        self.size_label.set_margin_top(max(0, int(self.sel[1]) - 26))
        self.size_label.set_visible(True)
        self.canvas.queue_draw()

    def _end(self, _g, dx, dy):
        if self.mode == 'region' and self.sel and self.sel[2] > 4 and self.sel[3] > 4:
            self.confirm()
        elif self.mode in ('window', 'screen') and abs(dx) < 4 and abs(dy) < 4:
            self.confirm()

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.cancel()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.confirm()
            return True
        return False

    def _draw(self, _a, ctx, w, h):
        k = self.frozen.get_width() / max(1, w)
        ctx.save()
        ctx.scale(1 / k, 1 / k)
        ctx.set_source_surface(self.frozen, 0, 0)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgba(0.02, 0.02, 0.06, 0.55)
        ctx.paint()
        rect = self._current_rect()
        if rect:
            x, y, rw, rh = rect
            ctx.save()
            ctx.rectangle(x, y, rw, rh)
            ctx.clip()
            ctx.scale(1 / k, 1 / k)
            ctx.set_source_surface(self.frozen, 0, 0)
            ctx.paint()
            ctx.restore()
            ctx.set_source_rgb(*COLORS['cyan'])
            ctx.set_line_width(2)
            ctx.rectangle(x, y, rw, rh)
            ctx.stroke()
        if self.mode == 'screen':
            ctx.set_source_rgb(*COLORS['cyan'])
            ctx.set_line_width(4)
            ctx.rectangle(2, 2, w - 4, h - 4)
            ctx.stroke()

    def _current_rect(self):
        if self.mode == 'region':
            return self.sel
        if self.mode == 'window' and self.hover:
            for w, r in self._window_rects():
                if w is self.hover['_w']:
                    return r
        return None

    # ---- result
    def confirm(self):
        k = self._scale()
        if self.mode == 'region':
            if not self.sel or self.sel[2] < 4 or self.sel[3] < 4:
                return
            x, y, w, h = self.sel
            crop = (round(x * k), round(y * k), round(w * k), round(h * k))
            payload = {'mode': 'region', 'crop': crop, 'area': (self.screen['x'] + round(x), self.screen['y'] + round(y), round(w), round(h))}
        elif self.mode == 'window':
            target = (self.hover or {}).get('_w')
            if not target:
                return
            sx, sy = self.screen.get('x', 0), self.screen.get('y', 0)
            payload = {'mode': 'window', 'window': target, 'crop': (round((target['x'] - sx) * k), round((target['y'] - sy) * k),
                                                                  round(target['w'] * k), round(target['h'] * k)),
                       'area': (target['x'], target['y'], target['w'], target['h'])}
        else:
            payload = {'mode': 'screen', 'crop': None, 'area': None}
        payload.update(record=self.record, annotate=self.annotate, delay=self.delay, frozen=self.frozen, screen=self.screen)
        self.service.overlay_done(payload)
        self.close()

    def cancel(self):
        self.service.overlay_cancelled()
        self.close()


# ------------------------------------------------------------------------------------------------ service
class ScreenshotService(GObject.Object):
    def __init__(self, shell, bus=None):
        super().__init__()
        self.shell = shell
        self.capture = KWinCapture(bus)
        self.thumbs = ThumbnailCache(self.capture)
        self.recorder = Recorder(self.capture)
        self.recorder.connect('state', self._recording_state)
        self.overlay = None
        self.editor = None
        self._last = None
        self._busy = False

    # ---- settings
    def conf(self, key=None):
        data = deskconf.get('screenshot', self.shell.settings) or {}
        return data if key is None else data.get(key)

    def recording_possible(self):
        return bool(detect_recording(Recorder._globals())['best'])

    # ---- entry points (keys, hot corners, the bar)
    def start(self, mode='region'):
        if self.overlay is not None or self._busy:
            return
        if self.recorder.running and mode == 'record':
            return self.stop_recording()
        if not self.capture.available():
            return self._fallback(mode)
        windows = [w for w in self.shell.windows.app_windows()
                   if not w.get('minimized') and self.shell.windows.state.get('current') in (w.get('desktops') or [self.shell.windows.state.get('current')])
                   or w.get('allDesktops')]
        state = self.shell.windows.state
        screens = state.get('screens') or []
        name = state.get('activeScreen') or (screens[0]['name'] if screens else '')
        screen = next((s for s in screens if s['name'] == name), screens[0] if screens else {'name': name, 'x': 0, 'y': 0, 'w': 1920, 'h': 1080})

        def grab():
            return self.capture.screen(screen['name'], cursor=bool(self.conf('include_cursor')))[0] if screen.get('name') else \
                self.capture.active_screen()[0]

        def shown(surface, error):
            if error is not None:
                return self.toast('Screenshot failed', str(error))
            if mode == 'screen' and not self.conf('delay'):
                return self.finish(surface, None, 'screen')
            self.overlay = CaptureOverlay(self, surface, screen, windows, mode='region' if mode == 'record' else mode,
                                          record=(mode == 'record'))
            self.overlay.present()
        self._busy = True
        run_async(grab, lambda r, e: (setattr(self, '_busy', False), shown(r, e)))

    def _fallback(self, mode):
        if shutil.which('spectacle'):
            flag = {'region': '-r', 'window': '-a', 'screen': '-f'}.get(mode, '-r')
            subprocess.Popen(['spectacle', '-b', '-n', flag], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.toast('Screenshots are not available', 'The shell is not authorised to capture the screen and Spectacle is not installed.')

    def overlay_cancelled(self):
        self.overlay = None

    def overlay_done(self, p):
        self.overlay = None
        if p['record']:
            return self.start_recording(p['area'], p['screen'])

        def after_delay():
            self._busy = True
            run_async(lambda: self._final_image(p), lambda r, e: (setattr(self, '_busy', False), self._got(r, e, p)))
            return False
        if p['delay']:
            self.toast('Capturing in %d seconds' % p['delay'], '')
            GLib.timeout_add_seconds(p['delay'], after_delay)
        else:
            GLib.idle_add(after_delay)

    def _final_image(self, p):
        if p['delay']:   # the screen may have changed: take a fresh picture of the same place
            if p['mode'] == 'screen':
                return self.capture.screen(p['screen']['name'])[0]
            if p['area']:
                return self.capture.area(*p['area'])[0]
        if p['mode'] == 'window' and p.get('window'):
            try:
                return self.capture.window(p['window']['id'], decoration=True)[0]
            except CaptureError:
                pass
        if p['crop'] is None:
            return p['frozen']
        return crop_surface(p['frozen'], *p['crop'])

    def _got(self, surface, error, p):
        if error is not None:
            return self.toast('Screenshot failed', str(error))
        self.finish(surface, p, p['mode'])

    # ---- saving
    def finish(self, surface, payload, kind):
        folder = screenshots_dir(self.conf())
        path = unique_path(folder)
        surface.write_to_png(str(path))
        os.chmod(path, 0o600)
        if self.conf('copy'):
            self.copy_surface(surface, path)
        self._last = (surface, path)
        if payload and payload.get('annotate'):
            return self.annotate(surface, path)
        if self.conf('notify'):
            self.toast('Screenshot saved', path.name, actions=['copy', 'Copy', 'annotate', 'Annotate', 'folder', 'Show in folder'],
                       handler=self._action)
        return path

    def _action(self, action):
        if not self._last:
            return
        surface, path = self._last
        if action == 'copy':
            self.copy_surface(surface, path, force=True)
        elif action == 'annotate':
            self.annotate(surface, path)
        elif action == 'folder':
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(str(path.parent)).get_uri(), dutil_context())

    def annotate(self, surface, path):
        self.editor = Annotator(self, surface, path)
        self.editor.present()

    def copy_surface(self, surface, path, force=False):
        """Put the image on the clipboard: wl-copy (works without keyboard focus) or GDK."""
        data = png_bytes(surface)
        if shutil.which('wl-copy'):
            try:
                subprocess.run(['wl-copy', '-t', 'image/png'], input=data, timeout=5, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except (OSError, subprocess.SubprocessError):
                pass
        Gdk.Display.get_default().get_clipboard().set_texture(texture_from_surface(surface))
        return True

    # ---- recording
    def start_recording(self, area, screen):
        try:
            path = self.recorder.start(screenshots_dir(self.conf()), area=area, screen=(screen or {}).get('name'))
        except CaptureError as error:
            return self.toast('Cannot record', str(error))
        self.toast('Recording started', 'Press Meta+Shift+R to stop. ' + (path.name if path else ''))

    def stop_recording(self):
        path = self.recorder.stop()
        return path

    def toggle_recording(self):
        if self.recorder.running:
            self.stop_recording()
        else:
            self.start('record')

    def _recording_state(self, _rec, running):
        bar = getattr(self.shell, 'bar', None)
        chip = getattr(bar, 'record_chip', None)
        if chip is not None:
            chip.set_visible(running)
        if not running and self.recorder.path and Path(self.recorder.path).exists():
            note = self.recorder.error or Path(self.recorder.path).name
            self.toast('Recording saved' if not self.recorder.error else 'Recording ended', note,
                       actions=['folder', 'Show in folder'],
                       handler=lambda a: Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(str(Path(self.recorder.path).parent)).get_uri(),
                                                                          dutil_context()))

    # ---- notifications
    def toast(self, summary, body, actions=(), handler=None):
        notes = getattr(self.shell, 'notifications', None)
        if notes is not None:
            notes.notify('Screenshot', 0, 'camera-photo', summary, body, list(actions), {}, 8000, on_action=handler)

    # ---- the agent's entry point (org.amerika.Desktop.Screenshot); never opens UI, never takes caller-chosen paths
    def agent_capture(self, request):
        kind = request.get('kind', 'screen')
        try:
            if kind == 'workspace':
                surface = self.capture.workspace()[0]
            elif kind == 'active-window':
                surface = self.capture.active_window(decoration=True)[0]
            elif kind == 'window':
                surface = self.capture.window(str(request['id']), decoration=True)[0]
            elif kind == 'area':
                x, y, w, h = (int(request[k]) for k in ('x', 'y', 'w', 'h'))
                if not (0 < w <= 16384 and 0 < h <= 16384):
                    raise ValueError('invalid area')
                surface = self.capture.area(x, y, w, h)[0]
            elif kind == 'screen':
                surface = self.capture.screen(request['screen'])[0] if request.get('screen') else self.capture.active_screen()[0]
            else:
                raise ValueError('kind must be screen, workspace, active-window, window or area')
            surface = scaled_surface(surface, int(request.get('max_width', 2560)))
        except (CaptureError, ValueError, KeyError) as error:
            return {'error': str(error)}
        path = unique_path(agent_dir(), 'agent', 'png')
        surface.write_to_png(str(path))
        os.chmod(path, 0o600)
        return {'path': str(path), 'width': surface.get_width(), 'height': surface.get_height()}


def dutil_context():
    from . import apps
    return apps.launch_context()


def agent_request(service, text):
    """JSON in, JSON out (used by the D-Bus method so tests can call it directly)."""
    try:
        request = json.loads(text)
        if not isinstance(request, dict):
            raise ValueError
    except ValueError:
        return json.dumps({'error': 'request must be a JSON object'})
    return json.dumps(service.agent_capture(request))
