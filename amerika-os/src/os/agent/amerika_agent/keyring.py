"""Secret Service access through `secret-tool` (libsecret-tools).

Secrets are stored with the attributes  service=amerika-agent  name=<secret name>.
The value only ever travels over a pipe: `store` reads it from stdin, `lookup` writes it to stdout. It is never put
in argv, in the environment, or in a file.
"""
import re
import subprocess

from . import common
from .common import AgentError

SERVICE = 'amerika-agent'
LABELS = {'anthropic': 'Amerika Agent: Anthropic API key', 'openai': 'Amerika Agent: OpenAI API key',
          common.GATEWAY_TOKEN: 'Amerika Agent: gateway token'}
_NAME_RE = common.SECRET_NAME_RE


def check_name(name):
    if not isinstance(name, str) or not _NAME_RE.match(name) or name not in common.SECRET_NAMES:
        raise AgentError(f'unknown secret name {name!r}')
    return name


def _tool(*args, stdin=None):
    try:
        return subprocess.run([common.SECRET_TOOL, *args], input=stdin, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        raise AgentError('secret-tool is not installed (package libsecret-tools). The keyring cannot be used without it.')
    except subprocess.TimeoutExpired:
        raise AgentError('the keyring did not answer in time (is the login keyring unlocked?)')


def clean_value(raw):
    """A pasted key: no surrounding whitespace, no embedded newlines or control characters."""
    value = raw.strip()
    if not value:
        raise AgentError('empty value: nothing stored')
    if re.search(r'[\x00-\x1f\x7f\s]', value):
        raise AgentError('the value contains whitespace or control characters; paste only the key')
    if len(value) > 4096:
        raise AgentError('the value is unreasonably long')
    return value


def store(name, value):
    check_name(name)
    value = clean_value(value)
    r = _tool('store', f'--label={LABELS.get(name, "Amerika Agent: " + name)}', 'service', SERVICE, 'name', name, stdin=value)
    if r.returncode != 0:
        raise AgentError('the keyring refused the value; check that the login keyring is unlocked')


def lookup(name):
    """The stored value, or None when absent. Raises AgentError when the keyring itself fails."""
    check_name(name)
    r = _tool('lookup', 'service', SERVICE, 'name', name)
    if r.returncode == 0 and r.stdout:
        return r.stdout.rstrip('\n')
    if r.returncode in (0, 1) and not r.stderr.strip():
        return None   # secret-tool exits 1 with no output when nothing matches
    raise AgentError('the keyring could not be read; check that the login keyring is unlocked')


def present(name):
    """True when a value is stored (the value itself is dropped immediately)."""
    try:
        return bool(lookup(name))
    except AgentError:
        return False


def clear(name):
    check_name(name)
    r = _tool('clear', 'service', SERVICE, 'name', name)
    if r.returncode not in (0, 1):
        raise AgentError('the keyring could not remove the value')


def ensure_gateway_token():
    """Create the per-user gateway token on first use. Returns True when a new one was made."""
    import secrets
    if lookup(common.GATEWAY_TOKEN):
        return False
    store(common.GATEWAY_TOKEN, secrets.token_urlsafe(32))
    return True
