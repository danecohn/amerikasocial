#!/usr/bin/env python3
"""Stage dist/apt into an Amerika Social checkout.

Small packages and all repository metadata are copied into <social>/apt-repo and ship in the Social image.
Packages over the size limit stay out of git and are served as redirects to a GitHub release asset; APT still
verifies their SHA-256 against the signed Packages index, so the host never has to be trusted.
"""
import json
import shutil
import sys
from pathlib import Path

LIMIT = 5 * 1024 * 1024
RELEASE = 'os-2.0.0'
BASE = 'https://github.com/danecohn/amerikasocial/releases/download/'
root = Path(__file__).resolve().parent.parent
social = Path(sys.argv[1])
dest = social / 'apt-repo'
previous = json.loads((dest / 'pool-redirects.json').read_text()) if (dest / 'pool-redirects.json').exists() else {}
if dest.exists():
    shutil.rmtree(dest)
shutil.copytree(root / 'dist/apt', dest, ignore=lambda d, names: [n for n in names if n.endswith('.deb')
                                                                  and (Path(d) / n).stat().st_size > LIMIT])
redirects, big = {}, []
for deb in sorted((root / 'dist/apt/pool').rglob('*.deb')):
    if deb.stat().st_size > LIMIT:
        if deb.name in previous:  # unchanged file already attached to an earlier release
            redirects[deb.name] = {**previous[deb.name], 'size': deb.stat().st_size}
        else:
            redirects[deb.name] = {'url': BASE + RELEASE + '/' + deb.name, 'size': deb.stat().st_size}
            big.append(str(deb))
(dest / 'pool-redirects.json').write_text(json.dumps(redirects, indent=2) + '\n')
(root / 'dist/release-assets.txt').write_text('\n'.join(big) + '\n')
print('staged', dest, 'redirected:', ', '.join(redirects))
