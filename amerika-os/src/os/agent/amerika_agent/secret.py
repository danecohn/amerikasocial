"""amerika-agent-secret: the exec SecretRef helper OpenClaw runs to read credentials from the login keyring.

    amerika-agent-secret get <name> [--force]   print one value to a machine pipe; terminal output is always refused
    amerika-agent-secret resolve                OpenClaw exec-provider protocol: JSON request on stdin, JSON reply on stdout

Only the fixed set of names in common.SECRET_NAMES can be read. Nothing is logged.
"""
import json
import sys

from . import keyring
from .common import AgentError, SECRET_NAMES


def resolve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if stdout.isatty():
        print('amerika-agent-secret: terminal output is refused', file=sys.stderr)
        return 3
    try:
        raw = stdin.read(16385)
        if len(raw) > 16384:
            raise ValueError('request too large')
        request = json.loads(raw)
        if not isinstance(request, dict) or type(request.get('protocolVersion')) is not int or request['protocolVersion'] != 1:
            raise ValueError('version')
        ids = request.get('ids')
        if (not isinstance(ids, list) or len(ids) > len(SECRET_NAMES)
                or any(not isinstance(ident, str) or ident not in SECRET_NAMES for ident in ids)):
            raise ValueError('ids')
    except ValueError:
        print('amerika-agent-secret: bad request', file=sys.stderr)
        return 2
    values, errors = {}, {}
    for ident in ids:
        try:
            value = keyring.lookup(ident) if isinstance(ident, str) else None
        except AgentError:
            errors[str(ident)] = {'code': 'UNAVAILABLE'}
            continue
        if value:
            values[ident] = value
        else:
            errors[str(ident)] = {'code': 'NOT_FOUND'}
    stdout.write(json.dumps({'protocolVersion': 1, 'values': values, 'errors': errors}))
    return 0


def get(name, force=False, stdout=None):
    stdout = stdout or sys.stdout
    if stdout.isatty():
        print('amerika-agent-secret: refusing to print a secret to a terminal (only machine pipes are supported)', file=sys.stderr)
        return 3
    try:
        value = keyring.lookup(name)
    except AgentError as error:
        print(f'amerika-agent-secret: {error}', file=sys.stderr)
        return 2
    if not value:
        print(f'amerika-agent-secret: no value stored for {name}', file=sys.stderr)
        return 1
    stdout.write(value)
    stdout.flush()
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 1 and argv[0] == 'resolve' and len(argv) == 1:
        return resolve()
    if len(argv) >= 2 and argv[0] == 'get' and (len(argv) == 2 or (len(argv) == 3 and argv[2] == '--force')):
        return get(argv[1], force=len(argv) == 3)
    print('usage: amerika-agent-secret get <name> [--force] | resolve', file=sys.stderr)
    return 64


if __name__ == '__main__':
    sys.exit(main())
