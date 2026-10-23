"""AmerikaBox: BeepBox (MIT) built for the desktop, with the Amerika Composer. Static app + launcher + Ogg helper."""
import json
import shutil
from pathlib import Path


def register(b):
    def build():
        src = b.OS / 'box'
        lock = json.loads((src / 'beepbox.lock.json').read_text())
        p = b.Pkg('amerika-box', b.DE_VERSION,
                  'AmerikaBox, a chiptune maker built on BeepBox\n'
                  'A desktop copy of BeepBox (by John Nesky, MIT licence; not affiliated) in the Amerika Studio window, with an AI composer '
                  'that writes and edits songs through BeepBox\'s own song format, WAV/MP3/MIDI export and "Export for game" loop bundles.',
                  arch='all', depends=f'amerika-studio (>= {b.DE_VERSION}), gir1.2-webkit-6.0, python3',
                  recommends='ffmpeg', title='AmerikaBox', category='Audio')
        app = p.path('/usr/share/amerika-box/app')
        shutil.copytree(src / 'app', app, ignore=shutil.ignore_patterns('*.map', '__pycache__'))
        about = app / 'amerika/about.js'
        about.write_text(about.read_text().replace('appVersion: "3.1.1"', f'appVersion: "{b.DE_VERSION}"'))
        p.copy(src / 'bin/amerika-box', '/usr/bin/amerika-box', 0o755)
        p.copy(src / 'bin/amerika-box-ogg', '/usr/bin/amerika-box-ogg', 0o755)
        p.copy(src / 'applications/amerika-box.desktop', '/usr/share/applications/amerika-box.desktop')
        # the icon amerika-box.svg ships in amerika-studio (hicolor), which this package depends on
        doc = '/usr/share/doc/amerika-box/'
        p.copy(src / 'LICENSE-BeepBox.md', doc + 'LICENSE-BeepBox.md')
        p.copy(src / 'NOTICE', doc + 'NOTICE')
        p.copy(src / 'beepbox.lock.json', doc + 'beepbox.lock.json')
        p.copy(app / 'amerika/vendor/LICENSE-lamejs.txt', doc + 'LICENSE-lamejs.txt')
        for patch in sorted((src / 'patches').glob('*.patch')):
            p.copy(patch, doc + 'patches/' + patch.name)
        p.copyright('AmerikaBox is a desktop build of BeepBox.\n\n'
                    'BeepBox: Copyright (c) 2012-2024 John Nesky and contributing authors, MIT licence.\n'
                    f'Source: {lock["upstream"]} at commit {lock["commit"]}. AmerikaBox is not affiliated with BeepBox or John Nesky.\n'
                    'The MIT licence text is in /usr/share/doc/amerika-box/LICENSE-BeepBox.md.\n\n'
                    'lamejs 1.2.0 (LAME MP3 encoder): LGPL-3.0, separate unmodified file; see NOTICE and LICENSE-lamejs.txt.\n\n'
                    'Amerika additions: Copyright AltStack LLC, GPL-3.0-only (see /usr/share/common-licenses/GPL-3).\n')
        return p
    return {'amerika-box': build}
