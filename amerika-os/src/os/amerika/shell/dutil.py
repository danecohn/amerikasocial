"""Small widget and data helpers shared by the desktop-parity modules (switcher, overview, clipboard, ...)."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import apps

_ICON_CACHE = {}


def label(text, css=None, xalign=0.0, **kw):
    lab = Gtk.Label(label=text, xalign=xalign, **kw)
    for name in (css or '').split():
        lab.add_css_class(name)
    return lab


def clear(box):
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def app_info_for_window(win):
    """DesktopAppInfo for a bridge window dict (by desktop file name, then WM class), or None."""
    key = (str(win.get('desktopFile', '')), str(win.get('cls', '')))
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    info = None
    for name in key:
        if name:
            info = apps.lookup(name)
            if info:
                break
    if info is None and key[1]:
        wanted = key[1].lower()
        for candidate in apps.all_apps():
            if wanted in apps.identity(candidate):
                info = candidate
                break
    _ICON_CACHE[key] = info
    return info


def window_icon(win, size):
    info = app_info_for_window(win)
    if info is not None:
        return apps.icon_image(info, size)
    return apps.icon_image((win.get('cls') or 'application-x-executable').lower(), size)


def app_key(win):
    """Identity used for grouping windows by application."""
    return (str(win.get('desktopFile') or win.get('cls') or win.get('id'))).removesuffix('.desktop').lower()


def monitor_by_name(name):
    display = Gdk.Display.get_default()
    monitors = display.get_monitors()
    for i in range(monitors.get_n_items()):
        mon = monitors.get_item(i)
        if name and mon.get_connector() == name:
            return mon
    return monitors.get_item(0) if monitors.get_n_items() else None


def save_texture(texture, path):
    texture.save_to_png(str(path))
