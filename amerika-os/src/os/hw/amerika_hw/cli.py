"""amerika-hw: hardware report, runtime performance mode, opt-in system tuning, benchmarks."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from . import report, tune

HELPER = '/usr/libexec/amerika/amerika-hw-helper'


def root(argv):
    if os.geteuid() != 0:
        os.execvp('pkexec', ['pkexec', HELPER, *argv])


def bench():
    if not os.environ.get('WAYLAND_DISPLAY'):
        print('Run this from the desktop (needs a display).', file=sys.stderr)
        return 1
    tools = [t for t in ('vkmark', 'glmark2-wayland') if shutil.which(t)]
    if not tools:
        print('Install the benchmarks: sudo apt install amerika-gamedev', file=sys.stderr)
        return 1
    for t in tools:
        try:
            out = subprocess.run([t], capture_output=True, text=True, timeout=300).stdout
        except subprocess.TimeoutExpired:
            out = ''
        m = re.search(r'(?:vkmark|glmark2) Score:\s*(\d+)', out)
        print(f'{t}: ' + (m.group(1) if m else 'no score'))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='amerika-hw', description='Surface Laptop 7 / Snapdragon X game-development hardware tools.')
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('report'); p.add_argument('--json', action='store_true')
    sub.add_parser('npu')
    p = sub.add_parser('perf'); p.add_argument('mode', choices=['game', 'balanced'])
    p = sub.add_parser('tune'); p.add_argument('action', choices=['apply', 'revert'])
    sub.add_parser('bench')
    args = ap.parse_args(argv)
    cmd = args.cmd or 'report'
    if cmd == 'report':
        r = report.build()
        print(json.dumps(r, indent=2) if getattr(args, 'json', False) else report.text(r))
        return 0
    if cmd == 'npu':
        n = report.npu()
        print(json.dumps(n, indent=2))
        return 0
    if cmd == 'bench':
        return bench()
    if cmd in ('perf', 'tune'):
        root([cmd, getattr(args, 'mode', None) or args.action])
        try:
            if cmd == 'perf':
                print('Performance mode:', tune.perf(args.mode), '(temporary; resets on reboot)')
            else:
                done = tune.apply() if args.action == 'apply' else tune.revert()
                print(f'{args.action}: ' + (', '.join(done) or 'nothing to do'))
        except (RuntimeError, ValueError, OSError) as exc:
            print(f'amerika-hw: {exc}', file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
