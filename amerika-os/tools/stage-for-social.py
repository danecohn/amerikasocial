#!/usr/bin/env python3
"""Stage a signed APT snapshot; large packages become checksum-matched release redirects.

This only writes a checkout/staging folder. It never uploads, pushes or deploys.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

LIMIT=5*1024*1024
BASE='https://github.com/danecohn/amerikasocial/releases/download/'
ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def stage(social,repo,release):
    repo=Path(repo).resolve();dest=Path(social).resolve()/'apt-repo'
    if repo==dest or repo in dest.parents or dest in repo.parents:raise ValueError('Source and destination repositories must be separate.')
    if not (repo/'dists/stable/InRelease').is_file():raise ValueError('The source must be a signed repository.')
    previous=json.loads((dest/'pool-redirects.json').read_text()) if (dest/'pool-redirects.json').exists() else {}
    manifest=json.loads((dest/'manifest.json').read_text()).get('packages',{}) if (dest/'manifest.json').exists() else {}
    if dest.exists():shutil.rmtree(dest)
    shutil.copytree(repo,dest,ignore=lambda directory,names:[name for name in names if name.endswith('.deb') and (Path(directory)/name).stat().st_size>LIMIT])
    redirects,big={},[]
    for deb in sorted((repo/'pool').rglob('*.deb')):
        if deb.stat().st_size<=LIMIT:continue
        sha=digest(deb);old=previous.get(deb.name,{})
        oldsha=old.get('sha256') or manifest.get(deb.name,{}).get('sha256')
        if old.get('size')==deb.stat().st_size and oldsha==sha:
            url=old['url']
        else:
            url=BASE+release+'/'+deb.name.replace('~','.')
            big.append(str(deb))
        redirects[deb.name]={'url':url,'size':deb.stat().st_size,'sha256':sha}
    (dest/'pool-redirects.json').write_text(json.dumps(redirects,indent=2)+'\n')
    assets=repo.parent/'release-assets.txt';assets.write_text('\n'.join(big)+'\n')
    return {'destination':str(dest),'release':release,'new_assets':big,'uploaded':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('social');ap.add_argument('--repo',default=str(ROOT/'dist/apt'))
    ap.add_argument('--release',default='os-3.1.0');args=ap.parse_args()
    if '/' in args.release or not args.release.startswith('os-'):ap.error('Use an os-... release tag without slashes.')
    print(json.dumps(stage(args.social,args.repo,args.release),indent=2))


if __name__=='__main__':main()
