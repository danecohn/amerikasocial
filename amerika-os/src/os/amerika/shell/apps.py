"""Application lookup and launching (desktop entries), plus icon helpers."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gio, Gtk  # noqa: E402


def lookup(desktop_id):
    """Resolve a pinned id such as 'com.anthropic.Claude' or 'amerika-files' to a DesktopAppInfo, or None."""
    name = desktop_id if desktop_id.endswith('.desktop') else desktop_id + '.desktop'
    try:
        return Gio.DesktopAppInfo.new(name)
    except TypeError:  # PyGObject raises when the desktop file does not exist
        return None


def identity(info):
    """Lower-case names a window of this app may report: desktop id, WM class, executable name, display name."""
    keys = set()
    if info is None:
        return keys
    keys.add(info.get_id().removesuffix('.desktop').lower())
    wm = info.get_startup_wm_class()
    if wm:
        keys.add(wm.lower())
    exe = info.get_executable()
    if exe:
        keys.add(exe.rsplit('/', 1)[-1].lower())
    keys.add(info.get_display_name().lower())
    return keys


def all_apps():
    seen, apps = set(), []
    for info in Gio.AppInfo.get_all():
        if not info.should_show() or info.get_id() in seen:
            continue
        seen.add(info.get_id())
        apps.append(info)
    return sorted(apps, key=lambda a: a.get_display_name().lower())


def launch_context():
    """Launch environment for child apps: the shell's own LD_PRELOAD (layer-shell) must never reach them."""
    ctx = Gio.AppLaunchContext()
    ctx.unsetenv('LD_PRELOAD')
    return ctx


def launch(info, uris=None):
    try:
        return info.launch(uris or [], launch_context())
    except Exception as error:  # noqa: BLE001 - GLib errors vary; never crash the shell on a bad desktop file
        print('launch failed:', info.get_id(), error, flush=True)
        return False


def icon_image(info_or_name, size):
    image = Gtk.Image()
    image.set_pixel_size(size)
    if isinstance(info_or_name, str):
        image.set_from_icon_name(info_or_name)
    else:
        icon = info_or_name.get_icon()
        if icon:
            image.set_from_gicon(icon)
        else:
            image.set_from_icon_name('application-x-executable')
    return image
