"""amerika-phone: use an iPhone (Secure Enclave key + Face ID, over USB) to approve sudo and admin prompts. Opt-in."""
import shutil


def register(b):
    def build():
        src = b.OS / 'phone'
        p = b.Pkg('amerika-phone', b.DE_VERSION,
                  'Amerika Phone Key: approve sudo with your iPhone\nPair an iPhone running the Amerika Key app, then approve sudo and '
                  'administrator prompts with Face ID.\nOpt-in: nothing changes until "amerika-phone enable sudo". Your password always still works.',
                  depends='python3, python3-cryptography, usbmuxd, libpam-modules, pkexec', title='Amerika Phone Key', category='Security')
        shutil.copytree(src / 'amerika_phone', p.path('/usr/lib/python3/dist-packages/amerika_phone'),
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        p.copy(src / 'bin/amerika-phone', '/usr/bin/amerika-phone', 0o755)
        p.copy(src / 'bin/amerika-phone-helper', '/usr/libexec/amerika/amerika-phone-helper', 0o755)
        p.copy(src / 'bin/amerika-phone-pam', '/usr/libexec/amerika/amerika-phone-pam', 0o755)
        p.copy(src / 'org.amerika.phone.policy', '/usr/share/polkit-1/actions/org.amerika.phone.policy')
        shutil.copytree(src / 'ios', p.path('/usr/share/amerika-phone/ios'))
        p.copy(b.ROOT / 'docs/phone/README.md', '/usr/share/doc/amerika-phone/README.md')
        # Removing the package must never leave a PAM line pointing at a missing helper.
        p.scripts['prerm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ] || [ "$1" = purge ]; then\n'
                              '  /usr/libexec/amerika/amerika-phone-helper disable >/dev/null 2>&1 || true\nfi\nexit 0\n')
        p.copyright('Amerika Phone Key, Copyright Amerika LLC, GPL-3.0-only. The iPhone app source (Swift) is under the same licence.\n')
        return p
    return {'amerika-phone': build}
