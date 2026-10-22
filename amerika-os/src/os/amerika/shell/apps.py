"""Application lookup and launching (desktop entries), plus icon helpers."""
import os
import re
import shlex
import subprocess
import threading

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


FIELD_CODE = re.compile(r'%[a-zA-Z]')


def build_command(exec_line, scale=None, uris=None, flag='--force-device-scale-factor'):
    """argv for a .desktop Exec line: field codes (%U %f %i ...) removed, %% turned into %, the URIs appended, and, when `scale`
    is given, the Electron scale flag inserted right after the program (and any `env VAR=x` prefix). A flag already present
    in the line is replaced, never duplicated."""
    parts = shlex.split(exec_line.replace('%%', '\x00'))
    argv = [FIELD_CODE.sub('', p).replace('\x00', '%') for p in parts]
    argv = [a for a, p in zip(argv, parts) if a or not FIELD_CODE.fullmatch(p)]
    if scale is not None:
        argv = [a for a in argv if not a.startswith(flag + '=')]
        at = 0
        if argv and argv[0].rsplit('/', 1)[-1] == 'env':
            at = 1
            while at < len(argv) and ('=' in argv[at] or argv[at].startswith('-')):
                at += 1
        at += 1 if at < len(argv) else 0
        argv.insert(at, '%s=%s' % (flag, ('%.2f' % float(scale)).rstrip('0').rstrip('.')))
    return argv + [str(u) for u in (uris or [])]


def clean_env():
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)
    return env


def launch(info, uris=None, scale='auto'):
    """Start an app. The AI apps get the Electron scale flag from settings['ai_text_scale'] (scale='auto'; None = never).
    Everything else, and every desktop action, goes through the sanitised GIO launch context as before."""
    try:
        if scale == 'auto':
            scale = _auto_scale(info)
        if scale is not None and info.get_commandline():
            argv = build_command(info.get_commandline(), scale, uris)
            proc = subprocess.Popen(argv, env=clean_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
            threading.Thread(target=proc.wait, daemon=True).start()   # reap the child
            return True
        return info.launch(uris or [], launch_context())
    except Exception as error:  # noqa: BLE001 - GLib errors vary; never crash the shell on a bad desktop file
        print('launch failed:', info.get_id(), error, flush=True)
        return False


def _auto_scale(info):
    from .. import common
    from . import home
    return home.scale_for_desktop_id(common.load_settings(), info.get_id())


def launch_action(info, action):
    try:
        info.launch_action(action, launch_context())
        return True
    except Exception as error:  # noqa: BLE001
        print('launch action failed:', info.get_id(), action, error, flush=True)
        return False


# launcher categories: the first matching freedesktop category decides the group
CATEGORY_GROUPS = [('Internet', ('Network', 'WebBrowser', 'Email', 'Chat', 'InstantMessaging', 'FileTransfer')),
                   ('Office', ('Office', 'WordProcessor', 'Spreadsheet', 'Presentation', 'Calendar', 'Finance')),
                   ('Media', ('AudioVideo', 'Audio', 'Video', 'Player', 'Graphics', 'Photography', 'Music')),
                   ('Games', ('Game',)),
                   ('Develop', ('Development', 'IDE', 'Debugger', 'TerminalEmulator')),
                   ('System', ('System', 'Settings', 'Monitor', 'PackageManager', 'Security', 'Printing')),
                   ('Utilities', ('Utility', 'Accessibility', 'Archiving', 'FileManager', 'TextEditor'))]


def group_of(categories):
    """Launcher group for a desktop entry's Categories string; 'Other' when nothing matches."""
    cats = {c for c in (categories or '').split(';') if c}
    for name, members in CATEGORY_GROUPS:
        if cats & set(members):
            return name
    return 'Other'


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
