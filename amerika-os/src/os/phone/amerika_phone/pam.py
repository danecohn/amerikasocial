"""Entry point for pam_exec: exit 0 only after the phone approved this exact prompt; any other result exits non-zero
so the next PAM rule (the normal password) runs. Never prints secrets; refuses unknown users and bad service names."""
import os
import re
import socket
import sys

from . import auth, store, usbmux

SERVICES = {'sudo', 'sudo-i', 'polkit-1', 'su', 'su-l'}


def tty_note(text):
    try:
        with open('/dev/tty', 'w') as tty:
            tty.write(text + '\n')
    except OSError:
        pass


def main():
    user = os.environ.get('PAM_USER', '')
    service = os.environ.get('PAM_SERVICE', '')
    if os.environ.get('PAM_TYPE') not in (None, 'auth') or service not in SERVICES or not re.match(store.USER_RE, user):
        return 1
    phones = store.load(user)
    if not phones:
        return 1
    try:
        if not usbmux.list_devices():
            return 1  # no phone plugged in: fall straight through to the password
    except usbmux.MuxError:
        return 1
    ok = auth.request_approval(user, service, socket.gethostname(), phones, notify=tty_note)
    if not ok:
        tty_note('iPhone approval failed or timed out; falling back to your password.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
