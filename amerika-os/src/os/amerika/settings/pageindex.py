"""Static description of every Settings page and of the individual settings inside them.

No GTK here: `amerika-settings --list` (for the agent), the search box, Ctrl+K quick-jump and the tests all read this.
A page's id is its deep-link name: `amerika-settings network`.
"""
import json

GROUPS = [('connect', 'CONNECTIONS'), ('devices', 'DEVICES'), ('personal', 'PERSONAL'), ('security', 'SECURITY'),
          ('system', 'SYSTEM'), ('ai', 'AI')]

# id, title, group, icon, one-line summary, keywords
PAGE_INFO = [
    ('network', 'Network', 'connect', 'amerika-wifi-symbolic', 'Wi-Fi, wired, VPN, hotspot, proxy and DNS',
     'wifi wi-fi wireless ethernet lan vpn wireguard openvpn hotspot airplane flight proxy dns internet ssid'),
    ('bluetooth', 'Bluetooth', 'connect', 'amerika-bluetooth-symbolic', 'Pair and manage Bluetooth devices',
     'bluetooth pair headphones speaker mouse keyboard discoverable battery'),
    ('sharing', 'Sharing & remote desktop', 'connect', 'amerika-network-symbolic', 'Remote desktop, SSH and file sharing status',
     'sharing remote desktop rdp vnc ssh samba screen share krdp'),
    ('display', 'Displays', 'devices', 'amerika-brightness-symbolic', 'Resolution, scale, rotation, arrangement, night light',
     'display monitor screen resolution refresh rate scale fractional rotation arrange primary night light hdr colour color brightness'),
    ('sound', 'Sound', 'devices', 'amerika-volume-symbolic', 'Output, input, per-app volume and profiles',
     'sound audio volume speaker microphone output input balance pipewire profile test tone mute'),
    ('input', 'Keyboard & mouse', 'devices', 'input-keyboard-symbolic', 'Layouts, repeat rate, touchpad, mouse, tablet',
     'keyboard layout language compose key repeat touchpad trackpad tap natural scroll mouse pointer speed gesture tablet pen copilot key'),
    ('shortcuts', 'Shortcuts', 'devices', 'input-keyboard-symbolic', 'Global keyboard shortcuts',
     'shortcut hotkey keybinding meta super key launcher tile conflict'),
    ('printers', 'Printers', 'devices', 'printer-symbolic', 'Printers and print jobs',
     'printer print cups scanner queue job default'),
    ('power', 'Power', 'devices', 'amerika-battery-symbolic', 'Battery, power profile, lid and idle actions',
     'power battery profile performance saver lid suspend idle sleep charge threshold screen off'),
    ('appearance', 'Appearance', 'personal', 'amerika-eye-symbolic', 'Accent, theme, wallpaper, fonts, dock and bar',
     'appearance accent colour color theme dark light wallpaper background font icon cursor animation transparency dock bar autohide'),
    ('notifications', 'Notifications', 'personal', 'amerika-bell-symbolic', 'Do not disturb and per-app notifications',
     'notification dnd do not disturb banner sound schedule quiet'),
    ('accessibility', 'Accessibility', 'personal', 'preferences-desktop-accessibility-symbolic', 'Text size, contrast, motion, keys, screen reader, zoom',
     'accessibility large text high contrast reduce motion sticky keys slow keys bounce keys screen reader orca magnifier zoom'),
    ('language', 'Language & region', 'personal', 'preferences-desktop-locale-symbolic', 'Language and formats',
     'language locale region format number currency measurement units translation'),
    ('datetime', 'Date & time', 'personal', 'preferences-system-time-symbolic', 'Time zone, automatic time, 12/24 hour',
     'date time clock timezone time zone ntp automatic 24 hour 12 hour'),
    ('defaults', 'Default apps & startup', 'personal', 'amerika-grid-symbolic', 'Default applications, file types and autostart',
     'default apps browser mail file association mime autostart startup login items open with'),
    ('users', 'Users', 'security', 'system-users-symbolic', 'Your account, picture and password',
     'user account name picture avatar password users login'),
    ('privacy', 'Privacy & security', 'security', 'amerika-shield-symbolic', 'Camera, microphone, location, screen lock, firewall',
     'privacy security camera microphone location permission screen lock timeout recent files firewall ufw'),
    ('updates', 'Updates', 'system', 'software-update-available-symbolic', 'System and Amerika software updates',
     'update upgrade apt software repository amerika repo packages'),
    ('storage', 'Storage', 'system', 'drive-harddisk-symbolic', 'Disk usage',
     'storage disk space usage drive partition free cache'),
    ('login', 'Login screen', 'system', 'amerika-lock-symbolic', 'Login screen and boot screen',
     'login screen sddm boot splash plymouth'),
    ('about', 'About', 'system', 'amerika-settings-symbolic', 'This computer, versions, copy system info',
     'about system info hardware cpu memory gpu firmware version kernel serial copy'),
    ('ai', 'AI & Assistants', 'ai', 'amerika-ai-symbolic', 'Claude, ChatGPT and permissions',
     'ai assistant claude chatgpt copilot permissions audit mcp'),
    ('agent', 'Amerika Agent', 'ai', 'amerika-ai-symbolic', 'The built-in agent: API keys, model, permissions, channels',
     'agent amerika agent openclaw api key anthropic openai claude gpt model gateway autostart channels telegram discord diagnostics doctor'),
]

# Individual settings, for search: (page id, title, extra keywords)
ITEMS = [
    ('network', 'Wi-Fi', 'wireless networks join scan'), ('network', 'Hidden network', 'join hidden ssid'),
    ('network', 'VPN', 'wireguard openvpn import'), ('network', 'Hotspot', 'share internet access point'),
    ('network', 'Airplane mode', 'flight radios'), ('network', 'Proxy', 'http socks pac manual'), ('network', 'DNS', 'resolver nameserver cloudflare quad9'),
    ('network', 'Wired connection', 'ethernet cable ip'),
    ('bluetooth', 'Bluetooth power', 'adapter on off'), ('bluetooth', 'Discoverable', 'visible pairing'),
    ('sound', 'Output device', 'speakers headphones'), ('sound', 'Input device', 'microphone'), ('sound', 'App volumes', 'per application'),
    ('sound', 'Balance', 'left right'), ('sound', 'Test tone', 'speaker test'),
    ('display', 'Resolution', 'mode'), ('display', 'Refresh rate', 'hz'), ('display', 'Scale', 'fractional dpi'),
    ('display', 'Rotation', 'orientation portrait'), ('display', 'Arrangement', 'position multiple monitors'), ('display', 'Night light', 'blue light warm schedule'),
    ('display', 'Brightness', 'backlight'), ('display', 'HDR', 'colour wide gamut'),
    ('input', 'Keyboard layouts', 'xkb language switch'), ('input', 'Compose key', 'special characters'), ('input', 'Copilot key', 'ai key'),
    ('input', 'Key repeat', 'delay rate'), ('input', 'Touchpad', 'tap to click natural scrolling speed'), ('input', 'Mouse', 'pointer acceleration left handed'),
    ('input', 'Tablet', 'pen stylus'),
    ('shortcuts', 'Global shortcuts', 'meta space launcher'),
    ('appearance', 'Accent colour', 'highlight'), ('appearance', 'Dark mode', 'light theme'), ('appearance', 'Wallpaper', 'background image'),
    ('appearance', 'Fonts', 'typeface size'), ('appearance', 'Icon theme', 'icons'), ('appearance', 'Cursor size', 'pointer'),
    ('appearance', 'Animations', 'effects speed'), ('appearance', 'Transparency', 'blur'), ('appearance', 'Dock', 'position size autohide'), ('appearance', 'Top bar', 'clock seconds'),
    ('notifications', 'Do not disturb', 'dnd quiet'), ('notifications', 'Do not disturb schedule', 'night'),
    ('accessibility', 'Large text', 'text size scaling'), ('accessibility', 'High contrast', 'contrast'), ('accessibility', 'Reduce motion', 'animations'),
    ('accessibility', 'Sticky keys', 'modifier'), ('accessibility', 'Slow keys', ''), ('accessibility', 'Bounce keys', ''),
    ('accessibility', 'Screen reader', 'orca'), ('accessibility', 'Magnifier', 'zoom'),
    ('privacy', 'Camera access', ''), ('privacy', 'Microphone access', ''), ('privacy', 'Location', 'gps'), ('privacy', 'Screen lock', 'timeout lock'),
    ('privacy', 'Recent files', 'history clear'), ('privacy', 'Firewall', 'ufw'),
    ('power', 'Power profile', 'balanced performance saver'), ('power', 'Lid close action', 'suspend'), ('power', 'Battery charge limit', 'threshold'),
    ('datetime', 'Automatic time', 'ntp'), ('datetime', 'Time zone', 'region city'), ('datetime', '24-hour clock', '12 hour am pm'),
    ('language', 'Language', 'locale'), ('language', 'Formats', 'region numbers dates'),
    ('users', 'Account name', 'real name'), ('users', 'Picture', 'avatar'), ('users', 'Change password', 'passwd'),
    ('defaults', 'Web browser', 'default'), ('defaults', 'Email', 'default mail'), ('defaults', 'File associations', 'mime open with'), ('defaults', 'Startup apps', 'autostart login'),
    ('printers', 'Printers', 'cups'), ('printers', 'Print queue', 'jobs'),
    ('sharing', 'Remote desktop', 'rdp krdp'), ('sharing', 'SSH', 'remote login'), ('sharing', 'File sharing', 'samba'),
    ('updates', 'Software updates', 'apt upgrade'), ('updates', 'Amerika repository', 'amerika repo'),
    ('about', 'System information', 'cpu memory gpu'), ('about', 'Copy system info', 'clipboard'),
    ('storage', 'Disk usage', 'space'),
    ('login', 'Login screen', 'sddm'), ('login', 'Boot screen', 'plymouth'),
    ('ai', 'Permissions', 'ask safe trusted'), ('ai', 'Activity log', 'audit'),
    ('agent', 'API key', 'anthropic openai keyring secret token'), ('agent', 'Agent model', 'claude gpt provider'),
    ('agent', 'Agent channels', 'telegram discord slack messaging'), ('agent', 'Agent diagnostics', 'doctor check'),
]

GROUP_NAME = dict(GROUPS)


def pages():
    return [{'id': i, 'title': t, 'group': g, 'icon': ic, 'summary': s, 'keywords': k.split()} for i, t, g, ic, s, k in PAGE_INFO]


def page_ids():
    return [p[0] for p in PAGE_INFO]


def list_json():
    """The payload of `amerika-settings --list` (stable keys, for the agent)."""
    return json.dumps({'pages': [{'id': p['id'], 'title': p['title'], 'group': GROUP_NAME[p['group']].title(), 'summary': p['summary']}
                                 for p in pages()]}, indent=2)


def resolve(name):
    """Map a user/agent-supplied page name (id, title, prefix) to a page id, or None."""
    name = (name or '').strip().lower().replace('_', '-')
    if not name:
        return None
    ids = page_ids()
    if name in ids:
        return name
    aliases = {'wifi': 'network', 'wi-fi': 'network', 'keyboard': 'input', 'mouse': 'input', 'touchpad': 'input', 'displays': 'display',
               'screen': 'display', 'audio': 'sound', 'volume': 'sound', 'wallpaper': 'appearance', 'theme': 'appearance',
               'security': 'privacy', 'time': 'datetime', 'date': 'datetime', 'locale': 'language', 'region': 'language',
               'apps': 'defaults', 'startup': 'defaults', 'autostart': 'defaults', 'remote': 'sharing', 'battery': 'power',
               'software': 'updates', 'accounts': 'users', 'user': 'users', 'printer': 'printers', 'a11y': 'accessibility',
               'disk': 'storage', 'system': 'about', 'notification': 'notifications'}
    if name in aliases:
        return aliases[name]
    for p in PAGE_INFO:
        if p[1].lower() == name or p[1].lower().startswith(name):
            return p[0]
    return None
