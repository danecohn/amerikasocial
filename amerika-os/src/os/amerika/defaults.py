"""Default applications, file associations (xdg-mime) and autostart entries (~/.config/autostart)."""
import re
from pathlib import Path

from . import sysutil

ROLES = [
    ('browser', 'Web browser', 'x-scheme-handler/https', ['x-scheme-handler/http', 'x-scheme-handler/https', 'text/html']),
    ('mail', 'Email', 'x-scheme-handler/mailto', ['x-scheme-handler/mailto']),
    ('files', 'File manager', 'inode/directory', ['inode/directory']),
    ('text', 'Text editor', 'text/plain', ['text/plain', 'text/markdown']),
    ('pdf', 'Documents (PDF)', 'application/pdf', ['application/pdf']),
    ('image', 'Images', 'image/png', ['image/png', 'image/jpeg', 'image/webp', 'image/gif']),
    ('video', 'Video', 'video/mp4', ['video/mp4', 'video/x-matroska', 'video/webm']),
    ('music', 'Music', 'audio/mpeg', ['audio/mpeg', 'audio/flac', 'audio/ogg']),
]
MIME_OK = re.compile(r'^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+*-]*$|^x-scheme-handler/[a-z0-9.+-]+$')
DESKTOP_OK = re.compile(r'^[A-Za-z0-9._+-]{1,120}\.desktop$')


def check_mime(mime):
    if not MIME_OK.match(mime or ''):
        raise ValueError('That is not a valid file type (example: text/plain).')
    return mime


def default_for(mime):
    res = sysutil.run(['xdg-mime', 'query', 'default', check_mime(mime)])
    return res.out if res.code == 0 else ''


def handlers_for(mime):
    """[(desktop_id, display name)] of apps that can open this type (Gio; replaced by a fake in tests)."""
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio
    return [(a.get_id(), a.get_display_name()) for a in Gio.AppInfo.get_all_for_type(mime)]


def set_default(mime, desktop_id):
    check_mime(mime)
    if not DESKTOP_OK.match(desktop_id or ''):
        raise ValueError('Invalid application.')
    return sysutil.run(['xdg-mime', 'default', desktop_id, mime]).code == 0


def set_role(role, desktop_id):
    mimes = next((m for r, _n, _p, m in ROLES if r == role), None)
    if mimes is None:
        raise ValueError('Unknown role.')
    return all(set_default(m, desktop_id) for m in mimes)


def roles():
    out = []
    for rid, name, probe, mimes in ROLES:
        cur = default_for(probe)
        out.append({'id': rid, 'name': name, 'mime': probe, 'mimes': mimes, 'default': cur, 'options': handlers_for(probe)})
    return out


def mime_for_name(filename):
    import mimetypes
    guess = mimetypes.guess_type(filename)[0]
    if guess:
        return guess
    return 'text/plain' if filename.lower().endswith(('.md', '.txt', '.log')) else ''


# ---------------------------------------------------------------- autostart
def autostart_dir():
    return sysutil.config_home() / 'autostart'


SYSTEM_AUTOSTART = [Path('/etc/xdg/autostart')]


def _parse(path):
    data = {}
    try:
        in_entry = False
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('['):
                in_entry = line.strip() == '[Desktop Entry]'
            elif in_entry and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                data.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return data


def autostart_entries():
    """User and system autostart entries. A user file with Hidden=true (or X-GNOME-Autostart-enabled=false) disables a system entry."""
    user = {}
    d = autostart_dir()
    if d.is_dir():
        for p in sorted(d.glob('*.desktop')):
            user[p.name] = _parse(p)
    entries, seen = [], set()
    for name, data in user.items():
        entries.append(_entry(name, data, 'user'))
        seen.add(name)
    for base in SYSTEM_AUTOSTART:
        if base.is_dir():
            for p in sorted(base.glob('*.desktop')):
                if p.name in seen:
                    continue
                data = _parse(p)
                if data.get('OnlyShowIn') and 'Amerika' not in data['OnlyShowIn'] and 'KDE' not in data['OnlyShowIn']:
                    continue
                entries.append(_entry(p.name, data, 'system'))
    return sorted(entries, key=lambda e: e['name'].lower())


def _entry(filename, data, source):
    disabled = data.get('Hidden', '').lower() == 'true' or data.get('X-GNOME-Autostart-enabled', '').lower() == 'false'
    return {'file': filename, 'name': data.get('Name') or filename.removesuffix('.desktop'), 'exec': data.get('Exec', ''),
            'comment': data.get('Comment', ''), 'enabled': not disabled, 'source': source}


def _write_entry(filename, name, exec_line, hidden=False, comment=''):
    d = autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    lines = ['[Desktop Entry]', 'Type=Application', f'Name={name}', f'Exec={exec_line}', 'X-Amerika-Autostart=true']
    if comment:
        lines.append(f'Comment={comment}')
    if hidden:
        lines.append('Hidden=true')
    (d / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def check_exec(cmd):
    if not cmd or '\n' in cmd or '\r' in cmd or len(cmd) > 500:
        raise ValueError('Enter a command on a single line.')
    return cmd.strip()


def add_autostart(name, command):
    name = (name or '').strip()
    if not name or re.search(r'[\x00-\x1f]', name) or len(name) > 80:
        raise ValueError('Enter a name.')
    command = check_exec(command)
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'app'
    filename = f'amerika-{slug}.desktop'
    _write_entry(filename, name, command)
    return filename


def add_app(desktop_id, name, exec_line):
    if not DESKTOP_OK.match(desktop_id):
        raise ValueError('Invalid application.')
    _write_entry(desktop_id, name, check_exec(exec_line))
    return desktop_id


def set_autostart_enabled(filename, enabled):
    if not DESKTOP_OK.match(filename or ''):
        raise ValueError('Invalid entry.')
    entries = {e['file']: e for e in autostart_entries()}
    e = entries.get(filename)
    if not e:
        raise ValueError('No such startup entry.')
    path = autostart_dir() / filename
    if path.exists():
        text = path.read_text(encoding='utf-8')
        text = re.sub(r'(?m)^Hidden=.*\n?', '', text).rstrip('\n') + '\n'
        if not enabled:
            text += 'Hidden=true\n'
        path.write_text(text, encoding='utf-8')
    else:  # override a system entry with a user copy
        _write_entry(filename, e['name'], e['exec'], hidden=not enabled, comment=e['comment'])
    return enabled


def remove_autostart(filename):
    """Delete a user entry. System entries cannot be deleted, only disabled."""
    if not DESKTOP_OK.match(filename or ''):
        raise ValueError('Invalid entry.')
    path = autostart_dir() / filename
    if not path.exists():
        raise ValueError('Only entries you added can be removed; turn system entries off instead.')
    path.unlink()
    return True
