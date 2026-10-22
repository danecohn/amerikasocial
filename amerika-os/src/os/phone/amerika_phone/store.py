"""Registered phones: /etc/amerika/phone-auth/<user>.json (root-owned; public keys only, nothing secret)."""
import json
import os
import re
import tempfile

DIR = '/etc/amerika/phone-auth'
USER_RE = re.compile(r'^[a-z_][a-z0-9_.-]{0,31}$')


def _path(user, directory):
    if not USER_RE.match(user):
        raise ValueError('invalid user name')
    return os.path.join(directory, user + '.json')


def load(user, directory=DIR):
    try:
        with open(_path(user, directory)) as f:
            data = json.load(f)
        return [p for p in data.get('phones', []) if isinstance(p.get('pubkey'), str)]
    except (OSError, ValueError):
        return []


def save(user, phones, directory=DIR):
    os.makedirs(directory, mode=0o755, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory)
    with os.fdopen(fd, 'w') as f:
        json.dump({'version': 1, 'phones': phones}, f, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, _path(user, directory))


def add(user, name, pubkey, directory=DIR):
    phones = [p for p in load(user, directory) if p['pubkey'] != pubkey]
    phones.append({'name': name[:64], 'pubkey': pubkey})
    save(user, phones, directory)


def remove(user, fingerprint_prefix, protocol, directory=DIR):
    phones = load(user, directory)
    kept = [p for p in phones if not protocol.fingerprint(p['pubkey']).startswith(fingerprint_prefix)]
    save(user, kept, directory)
    return len(phones) - len(kept)
