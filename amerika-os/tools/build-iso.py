#!/usr/bin/env python3
"""Prepare an inspectable ARM64 live-build workspace. Dry-run never executes lb/root actions.

The output is development infrastructure, not a tested installation image.
Use a disposable Ubuntu ARM64 build VM for the privileged build step.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def plan(repo,output):
    repo=Path(repo).resolve();output=Path(output).resolve()
    if output==ROOT or ROOT in output.parents and 'dist' not in output.relative_to(ROOT).parts:
        raise ValueError('Use a separate build workspace, or a directory under dist/.')
    required=['dists/stable/InRelease','amerika-archive-keyring.gpg','manifest.json']
    for name in required:
        if not (repo/name).is_file():raise ValueError('Signed local APT repository missing '+name)
    manifest=json.loads((repo/'manifest.json').read_text())
    return {'architecture':'arm64','distribution':'stonking','base':'Ubuntu 26.10','repository':str(repo),
            'repository_fingerprint':manifest['fingerprint'],'repository_manifest_sha256':hashlib.sha256((repo/'manifest.json').read_bytes()).hexdigest(),
            'repository_url':'http://127.0.0.1:8765','output':str(output),'packages':['amerika-desktop-minimal','casper','linux-image-generic','systemd-sysv'],
            'bootloader':'grub-efi','installer':'none (installer integration and hardware verification are pending)',
            'commands':[
                ['lb','config','--mode','ubuntu','--distribution','stonking','--architectures','arm64','--binary-images','iso',
                 '--bootloaders','grub-efi','--initramfs','casper','--debian-installer','false',
                 '--archive-areas','main restricted universe multiverse','--linux-flavours','generic',
                 '--mirror-bootstrap','http://ports.ubuntu.com/ubuntu-ports/','--mirror-chroot','http://ports.ubuntu.com/ubuntu-ports/',
                 '--apt-secure','true'],['lb','build']],
            'limitations':['No ISO has been booted or installed.','Generic ARM64 kernel is not proof of Snapdragon Surface support.',
                           'Secure Boot and installer are not validated.','The hosted repository remains paused; this uses a local signed snapshot.']}


def prepare(spec):
    output=Path(spec['output'])
    if output.exists() and any(output.iterdir()):raise ValueError('The build directory must be empty.')
    output.mkdir(parents=True,exist_ok=True)
    (output/'amerika-iso-plan.json').write_text(json.dumps(spec,indent=2)+'\n')
    config=output/'config';(config/'package-lists').mkdir(parents=True)
    (config/'package-lists/amerika.list.chroot').write_text('\n'.join(spec['packages'])+'\n')
    # Serve the signed snapshot from the disposable builder host. A chroot
    # shares its host's network, so this works before includes.chroot is copied.
    # live-build imports the supplied public key into the build chroot only.
    archives=config/'archives';archives.mkdir()
    (archives/'amerika.list.chroot').write_text('deb '+spec['repository_url']+' stable main\n')
    public=Path(spec['repository'])/'amerika-archive-keyring.asc'
    if not public.is_file():raise ValueError('Armored public repository key is required to prepare the builder.')
    shutil.copy2(public,archives/'amerika.key.chroot')
    (output/'README').write_text('Development live-build workspace. Review amerika-iso-plan.json.\n'
          'In the disposable builder, serve the signed snapshot on localhost port 8765 before lb runs:\n'
          'python3 -m http.server 8765 --bind 127.0.0.1 --directory '+spec['repository']+'\n'
          'Review and run the plan commands there. There is no installer in this image yet.\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',default=str(ROOT/'dist/apt'))
    ap.add_argument('--output',default=str(ROOT/'dist/iso-work'))
    ap.add_argument('--dry-run',action='store_true');ap.add_argument('--prepare',action='store_true')
    args=ap.parse_args();spec=plan(args.repo,args.output)
    # This helper deliberately never invokes a privileged build or disk tool.
    if args.prepare:prepare(spec)
    print(json.dumps(spec,indent=2))


if __name__=='__main__':main()
