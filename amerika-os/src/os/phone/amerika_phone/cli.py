"""amerika-phone: pair an iPhone and choose which prompts it can approve. Root actions run through pkexec."""
import argparse
import json
import os
import pwd
import shutil
import socket
import subprocess
import sys

from . import auth, protocol, store, usbmux

HELPER = '/usr/libexec/amerika/amerika-phone-helper'
PAM_LINE = 'auth      sufficient   pam_exec.so quiet /usr/libexec/amerika/amerika-phone-pam'
MARK = '# amerika-phone-key'
TARGETS = {'sudo': '/etc/pam.d/sudo', 'polkit': '/etc/pam.d/polkit-1'}
BACKUP = '/var/lib/amerika-os/phone'


def invoking_user():
    uid = os.environ.get('PKEXEC_UID')
    if uid and uid.isdigit():
        return pwd.getpwuid(int(uid)).pw_name
    return os.environ.get('SUDO_USER') or pwd.getpwuid(os.getuid()).pw_name


def pam_state(path):
    try:
        return MARK in open(path).read()
    except OSError:
        return False


def pam_enable(path, name, backup=BACKUP):
    text = open(path).read()
    if MARK in text:
        return False
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines) if l.strip().startswith('@include common-auth')
                or (l.split()[:1] == ['auth'])), None)
    if idx is None:
        raise RuntimeError(f'{path}: no auth stack found; leaving it unchanged')
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(path, os.path.join(backup, name + '.orig'))
    lines[idx:idx] = [MARK, PAM_LINE]
    tmp = path + '.amerika-new'
    with open(tmp, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    return True


def pam_disable(path):
    try:
        lines = open(path).read().splitlines()
    except OSError:
        return False
    kept = [l for l in lines if l.strip() != MARK and l.strip() != PAM_LINE.strip() and 'amerika-phone-pam' not in l]
    if len(kept) == len(lines):
        return False
    tmp = path + '.amerika-new'
    with open(tmp, 'w') as f:
        f.write('\n'.join(kept) + '\n')
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    return True


def cmd_status(args):
    user = invoking_user()
    phones = store.load(user)
    try:
        connected = len(usbmux.list_devices())
    except usbmux.MuxError:
        connected = -1
    out = {'user': user, 'phones': [{'name': p['name'], 'fingerprint': protocol.fingerprint(p['pubkey'])} for p in phones],
           'usb_phones_connected': connected, 'enabled': {k: pam_state(v) for k, v in TARGETS.items()}}
    if args.json:
        print(json.dumps(out))
    else:
        print(f'User: {user}')
        print('Paired phones:', ', '.join(f"{p['name']} ({p['fingerprint']})" for p in out['phones']) or 'none')
        print('Phone connected over USB:', 'usbmuxd not running' if connected < 0 else connected)
        for k, v in out['enabled'].items():
            print(f'Approves {k} prompts:', 'yes' if v else 'no')
    return 0


def cmd_pair(args):
    user = invoking_user()

    def confirm(code, name):
        print(f'The phone "{name}" shows this code: {code}')
        return input('Does the phone show exactly this code? [y/N] ').strip().lower() == 'y'
    print('Open the Amerika Key app on the iPhone, keep it unlocked, and approve with Face ID…')
    name, pub = auth.pair(user, socket.gethostname(), confirm=confirm)
    store.add(user, name, pub)
    print(f'Paired {name} ({protocol.fingerprint(pub)}) for {user}. Next: amerika-phone enable sudo')
    return 0


def cmd_remove(args):
    n = store.remove(invoking_user(), args.fingerprint, protocol)
    print(f'Removed {n} phone(s).')
    return 0 if n else 1


def cmd_enable(args):
    user = invoking_user()
    if not store.load(user):
        print('Pair a phone first: amerika-phone pair', file=sys.stderr)
        return 1
    for target in args.targets:
        changed = pam_enable(TARGETS[target], target)
        print(f'{target}: ' + ('enabled' if changed else 'already enabled'))
    print('Your password still works everywhere; the phone is tried first when it is plugged in.')
    print('Test it in a NEW terminal while keeping this one open:  sudo -k && sudo true')
    return 0


def cmd_disable(args):
    for target in (args.targets or list(TARGETS)):
        print(f'{target}: ' + ('disabled' if pam_disable(TARGETS[target]) else 'was not enabled'))
    return 0


def cmd_test(args):
    user = invoking_user()
    phones = store.load(user)
    ok = auth.request_approval(user, 'sudo', socket.gethostname(), phones, notify=print)
    print('Approved.' if ok else 'Not approved.')
    return 0 if ok else 1


def needs_root(fn):
    def run(args):
        if os.geteuid() != 0:
            os.execvp('pkexec', ['pkexec', HELPER, *sys.argv[1:]])
        return fn(args)
    return run


def main(argv=None):
    ap = argparse.ArgumentParser(prog='amerika-phone', description='Use an iPhone (Face ID) to approve sudo and admin prompts.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status'); p.add_argument('--json', action='store_true'); p.set_defaults(fn=cmd_status)
    sub.add_parser('pair').set_defaults(fn=needs_root(cmd_pair))
    p = sub.add_parser('remove'); p.add_argument('fingerprint'); p.set_defaults(fn=needs_root(cmd_remove))
    p = sub.add_parser('enable'); p.add_argument('targets', nargs='+', choices=sorted(TARGETS)); p.set_defaults(fn=needs_root(cmd_enable))
    p = sub.add_parser('disable'); p.add_argument('targets', nargs='*', choices=sorted(TARGETS)); p.set_defaults(fn=needs_root(cmd_disable))
    sub.add_parser('test').set_defaults(fn=cmd_test)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (RuntimeError, usbmux.MuxError, ValueError, KeyboardInterrupt, EOFError) as exc:
        print(f'amerika-phone: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
