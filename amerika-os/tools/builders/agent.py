"""Build the pinned OpenClaw-backed Amerika Agent without user configuration."""
import json
import os
import shutil
from pathlib import Path

META_DEPENDS = ['amerika-agent']


def register(b):
    def build():
        source = b.OS / 'agent'
        stage = Path(os.environ.get('AMERIKA_OPENCLAW_OUT', b.ROOT.parent / 'openclaw-src/stage-amerika'))
        # Fetch verifies the package lock and the audited lifecycle/pruning stamp.
        b.sh('bash', b.ROOT / 'tools/fetch-openclaw.sh', '--out', stage)
        package = json.loads((stage / 'node_modules/openclaw/package.json').read_text())
        lock = json.loads((source / 'openclaw.lock.json').read_text())
        if package['version'] != lock['version']:
            raise RuntimeError('the staged OpenClaw version does not match the pinned version')
        p = b.Pkg('amerika-agent', b.DE_VERSION,
                  'Amerika Agent, built on OpenClaw\nThe opt-in, keyring-backed agent for AltStack Desktop. '
                  'Includes the pinned OpenClaw engine, local authenticated gateway, Settings integration and desktop tools.',
                  arch='arm64', depends='nodejs (>= 24.16), nodejs (<< 25), libsecret-tools, python3, ca-certificates, '
                  f'amerika-desktop-shell (>= {b.DE_VERSION}), gir1.2-webkit-6.0',
                  recommends='gnome-keyring, ffmpeg, libnotify-bin, geoclue-2.0', title='Amerika Agent')
        shutil.copytree(stage / 'node_modules', p.path('/opt/amerika/agent/node_modules'), symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(source / 'amerika_agent', p.path('/usr/lib/python3/dist-packages/amerika_agent'),
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('amerika-agent', 'amerika-agent-secret'):
            p.copy(source / 'bin' / name, '/usr/bin/' + name, 0o755)
        p.copy(source / 'amerika-mcp-wrapper', '/usr/libexec/amerika/amerika-mcp-wrapper', 0o755)
        p.copy(b.OS / 'bin/amerika-agent-window', '/usr/bin/amerika-agent-window', 0o755)
        p.copy(b.OS / 'applications/amerika-agent.desktop', '/usr/share/applications/amerika-agent.desktop')
        for folder in ('workspace', 'activity-plugin'):
            shutil.copytree(source / folder, p.path('/usr/share/amerika-agent/' + folder))
        for unit in (source / 'systemd').glob('*.service'):
            p.copy(unit, '/usr/lib/systemd/user/' + unit.name)
        p.copy(source / 'openclaw.lock.json', '/usr/share/doc/amerika-agent/openclaw.lock.json')
        p.copy(stage / 'node_modules/openclaw/LICENSE', '/usr/share/doc/amerika-agent/OpenClaw-MIT-LICENSE')
        p.file('/usr/share/doc/amerika-agent/NOTICE',
               'Amerika Agent is built on OpenClaw ' + lock['version'] + '.\n'
               'OpenClaw: Copyright (c) 2026 OpenClaw Foundation, MIT licence.\n'
               'Upstream: https://github.com/openclaw/openclaw\n'
               'Dependency licences and notices are retained under /opt/amerika/agent/node_modules.\n')
        p.scripts['postinst'] = '#!/bin/sh\nset -e\n# No service enable/start and no per-user configuration changes.\nexit 0\n'
        p.scripts['prerm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ] || [ "$1" = purge ]; then\n'
                             '  if command -v deb-systemd-invoke >/dev/null 2>&1; then\n'
                             '    deb-systemd-invoke --user stop amerika-agent-gateway.service amerika-agent-activity.service || true\n'
                             '  fi\nfi\nexit 0\n')
        p.copyright('Amerika integration: Copyright AltStack LLC, GPL-3.0-only.\n'
                    'See /usr/share/common-licenses/GPL-3.\n'
                    'OpenClaw and its dependencies retain their respective licences; see NOTICE and OpenClaw-MIT-LICENSE.\n')
        return p
    return {'amerika-agent': build}
