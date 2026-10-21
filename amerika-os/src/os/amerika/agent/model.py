"""Pure logic of the Amerika Agent UI (no GTK, no subprocesses): status parsing, the Settings state machine, the bar chip,
launcher trigger parsing, loopback checks and secret scrubbing. Everything here is unit tested."""
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit

MODES = ('ask', 'safe', 'trusted')
PROVIDERS = ('anthropic', 'openai')
PROVIDER_NAMES = {'anthropic': 'Anthropic (Claude)', 'openai': 'OpenAI'}
ACTIVITY_STATES = ('idle', 'thinking', 'tool', 'error')
STALE_AFTER = 30 * 60  # an activity file that says "busy" for half an hour is a dead engine, not a busy one
LONG_TASK_SECONDS = 20
OPENCLAW_URL = 'https://github.com/openclaw/openclaw'


# --------------------------------------------------------------------------- status
class Status:
    def __init__(self, installed=False, engine='openclaw', engine_version='', running=False, url='', port=0,
                 providers=None, model=None, mode='ask', channels=(), autostart=False, error=''):
        self.installed = bool(installed)
        self.engine = engine
        self.engine_version = engine_version
        self.running = bool(running)
        self.url = url
        self.port = port
        self.providers = {p: bool((providers or {}).get(p)) for p in PROVIDERS}
        self.model = model
        self.mode = mode if mode in MODES else 'ask'
        self.channels = tuple(channels)
        self.autostart = bool(autostart)
        self.error = error

    @classmethod
    def missing(cls):
        return cls(installed=False)

    @classmethod
    def broken(cls, error):
        """Installed but `status` failed (engine crashed, bad install): the UI shows the error and offers diagnostics."""
        return cls(installed=True, error=error)

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict):
            raise ValueError('status must be an object')
        gw = data.get('gateway') if isinstance(data.get('gateway'), dict) else {}
        channels = [str(c) for c in data.get('channels') or [] if isinstance(c, str)]
        port = gw.get('port')
        return cls(installed=data.get('installed', False), engine=str(data.get('engine') or 'openclaw'),
                   engine_version=str(data.get('engine_version') or ''), running=gw.get('running', False),
                   url=str(gw.get('url') or ''), port=port if isinstance(port, int) and not isinstance(port, bool) else 0,
                   providers=data.get('providers') if isinstance(data.get('providers'), dict) else {},
                   model=data.get('model') if isinstance(data.get('model'), str) else None,
                   mode=data.get('mode'), channels=channels, autostart=data.get('autostart', False))

    @property
    def has_key(self):
        return any(self.providers.values())

    def listen_text(self):
        if self.url:
            return self.url.replace('http://', '').replace('https://', '').rstrip('/')
        return f'127.0.0.1:{self.port}' if self.port else ''


def public_status(status, activity_state='idle', activity_text=''):
    """What the agent.status tool may reveal: no keys, no tokens, no URLs."""
    return {'installed': status.installed, 'engine': status.engine, 'engine_version': status.engine_version,
            'gateway_running': status.running, 'providers_configured': dict(status.providers), 'model': status.model,
            'mode': status.mode, 'autostart': status.autostart, 'channels_enabled': list(status.channels),
            'activity': {'state': activity_state, 'text': activity_text}, 'error': status.error or None}


# --------------------------------------------------------------------------- Settings page state machine
def page_view(status, busy=False):
    """What the Settings page shows for a status. `busy` is True while a CLI command is running."""
    if not status.installed:
        return {'mode': 'not-installed', 'onboarding': False, 'controls': False, 'start': False, 'stop': False, 'restart': False,
                'open_window': False, 'keys': False, 'models': {}, 'gateway': 'NOT INSTALLED', 'tone': 'off'}
    broken = bool(status.error)
    view = {
        'mode': 'broken' if broken else ('running' if status.running else 'stopped'),
        'onboarding': not broken and not status.has_key,
        'controls': True,
        'start': not busy and not status.running,
        'stop': not busy and status.running,
        'restart': not busy and status.running,
        'open_window': True,
        'keys': True,
        'models': {p: status.providers[p] for p in PROVIDERS},
        'gateway': 'ERROR' if broken else ('RUNNING' if status.running else 'STOPPED'),
        'tone': 'error' if broken else ('on' if status.running else 'off'),
    }
    return view


def key_text(has_key):
    return 'Key saved in your keyring' if has_key else 'No key saved'


class Onboarding:
    """The guided 3-step card: provider, key, permission mode."""
    STEPS = ('provider', 'key', 'mode')

    def __init__(self):
        self.step = 0
        self.provider = None
        self.done = False

    @property
    def name(self):
        return self.STEPS[self.step]

    def choose_provider(self, provider):
        if provider not in PROVIDERS:
            raise ValueError('unknown provider')
        self.provider = provider
        self.step = 1

    def key_saved(self):
        if self.provider is None:
            raise ValueError('choose a provider first')
        self.step = 2

    def back(self):
        self.step = max(0, self.step - 1)

    def finish(self):
        if self.step != 2:
            raise ValueError('not at the last step')
        self.done = True


def parse_channels(text, enabled_names=()):
    """`channels list` output (JSON, or one channel per line, name first) -> [(name, enabled)]. `enabled_names` wins."""
    names = []
    text = (text or '').strip()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        data = [{'name': k, 'enabled': v} for k, v in data.items()]
    if isinstance(data, list):
        for item in data:
            name = item if isinstance(item, str) else (item.get('name') if isinstance(item, dict) else None)
            if isinstance(name, str) and valid_channel_name(name):
                names.append(name)
    else:
        for line in text.splitlines():
            parts = line.replace('\t', ' ').split()
            if parts and valid_channel_name(parts[0]):
                names.append(parts[0])
    seen, out = set(), []
    for name in names + [n for n in enabled_names if valid_channel_name(n)]:
        if name not in seen:
            seen.add(name)
            out.append((name, name in enabled_names))
    return out


def valid_channel_name(name):
    return isinstance(name, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', name.lower()) is not None


CHANNEL_RISK = ('Channels let people message your agent from outside this computer. Anyone who can reach this channel can try to '
                'make the agent act, and the agent can run tools that read and change your files. Turn on only channels you control, '
                'keep permissions on "Ask every time", and turn it off again when you stop using it.')


# --------------------------------------------------------------------------- activity chip
def parse_activity(text, now=None):
    """activity file text -> (state, text, since). Unknown or stale input becomes idle."""
    now = time.time() if now is None else now
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        return 'idle', '', 0.0
    state = data.get('state') if data.get('state') in ACTIVITY_STATES else 'idle'
    since = data.get('since')
    since = float(since) if isinstance(since, (int, float)) and not isinstance(since, bool) else 0.0
    body = data.get('text') if isinstance(data.get('text'), str) else ''
    body = ' '.join(body.split())[:80]
    if state in ('thinking', 'tool') and since and now - since > STALE_AFTER:
        return 'idle', '', since
    return state, body, since


def chip_view(state, text, paused=False, installed=True):
    """(label, css state, visible) for the bar chip."""
    if not installed:
        return '', 'idle', False
    if paused:
        return 'AGENT · PAUSED', 'paused', True
    label = {'idle': 'AGENT · IDLE', 'thinking': 'AGENT · THINKING', 'error': 'AGENT · PROBLEM'}.get(state)
    if state == 'tool':
        label = 'AGENT · ' + (text or 'WORKING')
    label = (label or 'AGENT · IDLE').upper()
    return (label[:34] + '…' if len(label) > 34 else label), state if state in ACTIVITY_STATES else 'idle', True


def finished_long_task(prev_state, prev_since, state, now=None):
    """True when the agent just went from busy to idle after a long task (so the shell can notify)."""
    now = time.time() if now is None else now
    return prev_state in ('thinking', 'tool') and state in ('idle', 'error') and prev_since and now - prev_since >= LONG_TASK_SECONDS


# --------------------------------------------------------------------------- launcher
_TRIGGER = re.compile(r'^\s*(?:\?+|ask\b[:,]?)\s*(.*)$', re.I | re.S)


def parse_ask(text):
    """Return (question, explicit) for launcher input. Explicit when it starts with ? or "ask"; implicit when it reads like a
    question (ends with ? and has a space). (None, False) when it is just a search."""
    text = (text or '').strip()
    if not text:
        return None, False
    m = _TRIGGER.match(text)
    if m:
        q = m.group(1).strip()
        return (q or None), True
    if text.endswith('?') and ' ' in text:
        return text, False
    return None, False


# --------------------------------------------------------------------------- Agent window
def is_loopback_url(url):
    """True only for http(s)/ws(s) URLs whose host is a loopback address or localhost. Everything else is refused."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme not in ('http', 'https', 'ws', 'wss') or not host:
        return False
    if parts.username or parts.password:
        return False
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_gateway_url(url, port):
    """Only this gateway's exact HTTP origin; no credentials, aliases or other local services."""
    try:
        parts = urlsplit(url)
        return (isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65535
                and parts.scheme == 'http' and parts.hostname == '127.0.0.1'
                and parts.port == port and parts.netloc == f'127.0.0.1:{port}')
    except (ValueError, TypeError):
        return False


def window_state(status, starting=False):
    """What the Agent window shows: not-installed | stopped | starting | broken | live."""
    if not status.installed:
        return 'not-installed'
    if status.error:
        return 'broken'
    if status.running:
        return 'live'
    return 'starting' if starting else 'stopped'


def header_text(status, state, text, paused=False):
    if not status.installed:
        return 'Not installed'
    if paused:
        return 'Paused'
    if not status.running:
        return 'Stopped'
    return {'idle': 'Ready', 'thinking': 'Thinking…', 'tool': text or 'Working…', 'error': text or 'Something went wrong'}.get(state, 'Ready')


# --------------------------------------------------------------------------- secrets
def scrub(text, secrets):
    """Remove every secret (and its trimmed form) from text. Used on all CLI output before it can be shown or logged."""
    text = text or ''
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, '***')
    return text
