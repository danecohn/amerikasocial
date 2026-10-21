"""A tiny Wayland client over ctypes/libwayland-client for the two things GTK cannot do:

* ext_idle_notifier_v1  - idle / resume notifications (dim, screen off, lock, suspend)
* org_kde_kwin_keystate - Caps Lock / Num Lock / Scroll Lock state without keyboard focus

Plus `list_globals()` to see which protocols the compositor offers. It uses its own connection, so it never touches GDK's.
"""
import ctypes
import ctypes.util
import os

_lib = None


def _client():
    global _lib
    if _lib is None:
        path = ctypes.util.find_library('wayland-client') or 'libwayland-client.so.0'
        lib = ctypes.CDLL(path)
        lib.wl_display_connect.restype = ctypes.c_void_p
        lib.wl_display_connect.argtypes = [ctypes.c_char_p]
        lib.wl_display_disconnect.argtypes = [ctypes.c_void_p]
        lib.wl_display_get_fd.argtypes = [ctypes.c_void_p]
        lib.wl_display_roundtrip.argtypes = [ctypes.c_void_p]
        lib.wl_display_flush.argtypes = [ctypes.c_void_p]
        lib.wl_display_dispatch_pending.argtypes = [ctypes.c_void_p]
        lib.wl_display_prepare_read.argtypes = [ctypes.c_void_p]
        lib.wl_display_read_events.argtypes = [ctypes.c_void_p]
        lib.wl_display_cancel_read.argtypes = [ctypes.c_void_p]
        lib.wl_proxy_add_listener.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.wl_proxy_destroy.argtypes = [ctypes.c_void_p]
        lib.wl_proxy_marshal_flags.restype = ctypes.c_void_p
        _lib = lib
    return _lib


class WlMessage(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char_p), ('signature', ctypes.c_char_p), ('types', ctypes.POINTER(ctypes.c_void_p))]


class WlInterface(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char_p), ('version', ctypes.c_int), ('method_count', ctypes.c_int),
                ('methods', ctypes.POINTER(WlMessage)), ('event_count', ctypes.c_int), ('events', ctypes.POINTER(WlMessage))]


def _interface(name, version, methods, events):
    """Build a wl_interface. methods/events are lists of (name, signature)."""
    keep = []

    def messages(items):
        arr = (WlMessage * max(1, len(items)))()
        for i, (mname, sig) in enumerate(items):
            types = (ctypes.c_void_p * max(1, sum(1 for c in sig if c.isalpha())))()
            keep.append(types)
            arr[i].name, arr[i].signature, arr[i].types = mname.encode(), sig.encode(), ctypes.cast(types, ctypes.POINTER(ctypes.c_void_p))
        keep.append(arr)
        return arr
    meth, evs = messages(methods), messages(events)
    iface = WlInterface(name.encode(), version, len(methods), ctypes.cast(meth, ctypes.POINTER(WlMessage)), len(events),
                        ctypes.cast(evs, ctypes.POINTER(WlMessage)))
    iface._keep = keep
    return iface


_IFACES = {}


def _ifaces():
    if not _IFACES:
        _IFACES['notification'] = _interface('ext_idle_notification_v1', 1, [('destroy', '')], [('idled', ''), ('resumed', '')])
        _IFACES['notifier'] = _interface('ext_idle_notifier_v1', 1, [('destroy', ''), ('get_idle_notification', 'nuo')], [])
        _IFACES['keystate'] = _interface('org_kde_kwin_keystate', 1, [('fetchStates', '')], [('stateChanged', 'uu')])
    return _IFACES


GLOBAL_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32)
REMOVE_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)
VOID_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
STATE_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32)

KEYS = {0: 'capslock', 1: 'numlock', 2: 'scrolllock'}
LOCK_STATES = {0: 'unlocked', 1: 'latched', 2: 'locked'}


class Wayland:
    """One connection, bound to whichever of the idle notifier / keystate / seat globals exist."""

    def __init__(self, display=None):
        self.lib = _client()
        name = display or os.environ.get('WAYLAND_DISPLAY')
        self.display = self.lib.wl_display_connect(name.encode() if name else None)
        if not self.display:
            raise OSError('cannot connect to the Wayland display')
        self.globals = {}      # interface -> (name, version)
        self.proxies = {}
        self._keep = []
        self.on_idle = self.on_resume = self.on_key = None
        self._notification = None
        registry = self._marshal(self.display, 1, _registry_interface(), 1, ctypes.c_void_p(None))
        self.registry = registry
        self._cb_global = GLOBAL_CB(self._global)
        self._cb_remove = REMOVE_CB(lambda *_: None)
        listener = (ctypes.c_void_p * 2)(ctypes.cast(self._cb_global, ctypes.c_void_p), ctypes.cast(self._cb_remove, ctypes.c_void_p))
        self._keep.append(listener)
        self.lib.wl_proxy_add_listener(registry, ctypes.cast(listener, ctypes.c_void_p), None)
        self.lib.wl_display_roundtrip(self.display)

    # ---- plumbing
    def _marshal(self, proxy, opcode, iface, version, *args):
        """Variadic wl_proxy_marshal_flags. `args` are ctypes instances (c_uint32, c_char_p, c_void_p)."""
        fixed = [ctypes.c_void_p(proxy), ctypes.c_uint32(opcode), ctypes.c_void_p(ctypes.addressof(iface) if iface is not None else None),
                 ctypes.c_uint32(version), ctypes.c_uint32(0)]
        values = fixed + list(args)
        self.lib.wl_proxy_marshal_flags.argtypes = [type(v) for v in values]
        return self.lib.wl_proxy_marshal_flags(*values)

    def _global(self, _data, _registry, name, interface, version):
        self.globals[interface.decode()] = (name, version)

    def _bind(self, interface, iface_struct, version=1):
        if interface not in self.globals:
            return None
        name, have = self.globals[interface]
        return self._marshal(self.registry, 0, iface_struct, min(version, have), ctypes.c_uint32(name), ctypes.c_char_p(interface.encode()),
                             ctypes.c_uint32(min(version, have)), ctypes.c_void_p(None))

    def fileno(self):
        return self.lib.wl_display_get_fd(self.display)

    def dispatch(self):
        """Call when fileno() is readable."""
        if self.lib.wl_display_prepare_read(self.display) == 0:
            self.lib.wl_display_read_events(self.display)
        self.lib.wl_display_dispatch_pending(self.display)
        self.lib.wl_display_flush(self.display)

    def roundtrip(self):
        self.lib.wl_display_roundtrip(self.display)

    # ---- idle
    def has_idle(self):
        return 'ext_idle_notifier_v1' in self.globals and 'wl_seat' in self.globals

    def set_idle_timeout(self, milliseconds):
        """(Re)arm the idle notification; 0 disarms it. on_idle()/on_resume() are called from dispatch()."""
        ifs = _ifaces()
        if self._notification:
            self._marshal(self._notification, 0, None, 1)  # destroy request
            self.lib.wl_proxy_destroy(self._notification)
            self._notification = None
        if not milliseconds or not self.has_idle():
            self.lib.wl_display_flush(self.display)
            return False
        if 'notifier' not in self.proxies:
            self.proxies['notifier'] = self._bind('ext_idle_notifier_v1', ifs['notifier'])
            seat = self._bind('wl_seat', _seat_interface(), 1)
            self.proxies['seat'] = seat
        note = self._marshal(self.proxies['notifier'], 1, ifs['notification'], 1, ctypes.c_void_p(None), ctypes.c_uint32(int(milliseconds)),
                             ctypes.c_void_p(self.proxies['seat']))
        self._cb_idled = VOID_CB(lambda *_: self.on_idle and self.on_idle())
        self._cb_resumed = VOID_CB(lambda *_: self.on_resume and self.on_resume())
        listener = (ctypes.c_void_p * 2)(ctypes.cast(self._cb_idled, ctypes.c_void_p), ctypes.cast(self._cb_resumed, ctypes.c_void_p))
        self._keep.append(listener)
        self.lib.wl_proxy_add_listener(note, ctypes.cast(listener, ctypes.c_void_p), None)
        self._notification = note
        self.lib.wl_display_flush(self.display)
        return True

    # ---- lock keys
    def has_keystate(self):
        return 'org_kde_kwin_keystate' in self.globals

    def watch_keystate(self):
        if not self.has_keystate() or 'keystate' in self.proxies:
            return self.has_keystate()
        proxy = self._bind('org_kde_kwin_keystate', _ifaces()['keystate'])
        self.proxies['keystate'] = proxy
        self._cb_state = STATE_CB(lambda _d, _p, key, state: self.on_key and self.on_key(KEYS.get(key, str(key)), LOCK_STATES.get(state, 'unlocked')))
        listener = (ctypes.c_void_p * 1)(ctypes.cast(self._cb_state, ctypes.c_void_p))
        self._keep.append(listener)
        self.lib.wl_proxy_add_listener(proxy, ctypes.cast(listener, ctypes.c_void_p), None)
        self._marshal(proxy, 0, None, 1)   # fetchStates: reports the current state once
        self.lib.wl_display_flush(self.display)
        return True

    def close(self):
        if self.display:
            self.lib.wl_display_disconnect(self.display)
            self.display = None


def _registry_interface():
    return WlInterface.in_dll(_client(), 'wl_registry_interface')


def _seat_interface():
    return WlInterface.in_dll(_client(), 'wl_seat_interface')


_GLOBALS_CACHE = {}


def list_globals(refresh=False):
    """Set of interface names the compositor advertises (cached for the process)."""
    if refresh or 'v' not in _GLOBALS_CACHE:
        try:
            conn = Wayland()
            _GLOBALS_CACHE['v'] = set(conn.globals)
            conn.close()
        except OSError:
            _GLOBALS_CACHE['v'] = set()
    return set(_GLOBALS_CACHE['v'])
