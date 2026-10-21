#!/usr/bin/env python3
"""A stand-in for libsecret's `secret-tool` for tests and rigs. Stores values in $FAKE_SECRET_DIR (a throwaway directory).

Supports the subset amerika-agent uses:  store --label=L attr value ...  (value on stdin)
                                         lookup attr value ...  /  clear attr value ...
Every argv is appended to $FAKE_SECRET_DIR/argv.log so tests can prove that no secret was ever passed on a command line.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

root = Path(os.environ['FAKE_SECRET_DIR'])
root.mkdir(parents=True, exist_ok=True)
with open(root / 'argv.log', 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\n')
args = sys.argv[1:]
if not args:
    sys.exit(2)
cmd, rest = args[0], args[1:]
rest = [a for a in rest if not a.startswith('--label=')]
attrs = dict(zip(rest[0::2], rest[1::2]))
key = root / ('item-' + hashlib.sha256(json.dumps(attrs, sort_keys=True).encode()).hexdigest()[:24])
if os.environ.get('FAKE_SECRET_FAIL'):
    print('Cannot autolaunch D-Bus without X11 $DISPLAY', file=sys.stderr)
    sys.exit(1)
if cmd == 'store':
    key.write_text(sys.stdin.read())
    key.chmod(0o600)
elif cmd == 'lookup':
    if not key.exists():
        sys.exit(1)
    sys.stdout.write(key.read_text())
elif cmd == 'clear':
    key.unlink(missing_ok=True)
else:
    sys.exit(2)
