"""Ubuntu flavour assets and seed-derived metapackages. No boot/login switching."""
import gzip
import json
import re
import shutil

META_DEPENDS=['amerika-branding','amerika-defaults','amerika-updates']
META_RECOMMENDS=['amerika-doc']


def read_seed(path):
    fields={};section=None
    for raw in path.read_text().splitlines():
        text=raw.strip()
        if not text or text.startswith('#'):continue
        if text.startswith('* '):
            package=text[2:].strip()
            if section not in ('Depends','Recommends','Suggests') or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*',package):
                raise ValueError('Invalid seed entry: '+raw)
            fields.setdefault(section,[]).append(package)
        elif ':' in text:
            section,value=text.split(':',1);fields.setdefault(section,value.strip() or [])
    return fields


def register(b):
    flavor=b.ROOT/'flavor'
    def package(name,description,**kwargs):
        p=b.Pkg(name,b.DE_VERSION,description,**kwargs)
        p.copyright('Copyright AltStack LLC, GPL-3.0-only.\nUbuntu remains Ubuntu; this package supplies Amerika desktop flavour assets.\n')
        return p

    def branding():
        p=package('amerika-branding','Amerika desktop flavour branding\nArtwork and sounds for the Amerika session. Keeps Ubuntu system identity intact.')
        for folder in ('sounds','grub-theme'):
            shutil.copytree(flavor/'branding'/folder,p.path('/usr/share/amerika-os/'+folder))
        p.copy(flavor/'branding/amerika-wallpapers.xml','/usr/share/gnome-background-properties/amerika-wallpapers.xml')
        p.copy(flavor/'branding/50-amerika-motd','/etc/update-motd.d/50-amerika',0o755)
        p.file('/usr/share/amerika-os/flavour',
               f'NAME="AltStack Desktop"\nVERSION="{b.DE_VERSION}"\nBASE="Ubuntu"\nBASE_VERSION_ID="26.10"\n'
               'ARCHITECTURE="arm64"\nCHANNEL="stable"\nSUPPORT_URL="https://altstack.io/downloads/os"\n'
               'STATUS="Independent development flavour; not an official Ubuntu flavour"\n')
        return p

    def defaults():
        p=package('amerika-defaults','Amerika session application defaults\nDefault colours, portals, fonts and file associations. Existing user settings take precedence.',
                  depends='dconf-cli, dconf-gsettings-backend, fontconfig, xdg-desktop-portal, xdg-desktop-portal-gtk, xdg-desktop-portal-kde')
        p.copy(flavor/'defaults/dconf-profile-amerika','/etc/dconf/profile/amerika')
        p.copy(flavor/'defaults/dconf/00-amerika','/etc/dconf/db/amerika.d/00-amerika')
        p.copy(flavor/'defaults/amerika-portals.conf','/usr/share/xdg-desktop-portal/amerika-portals.conf')
        p.copy(flavor/'defaults/amerika-mimeapps.list','/etc/xdg/amerika-mimeapps.list')
        p.copy(flavor/'defaults/amerika-xdg-terminals.list','/etc/xdg/amerika-xdg-terminals.list')
        for name in ('fonts.conf','session-env.sh'):p.copy(flavor/'defaults'/name,'/usr/share/amerika-os/'+name)
        p.copy(flavor/'defaults/amerika-apply-defaults','/usr/bin/amerika-apply-defaults',0o755)
        # Rebuild this package's dconf database; never select a boot or login theme.
        p.scripts['postinst']='#!/bin/sh\nset -e\nif command -v dconf >/dev/null 2>&1; then dconf update; fi\nexit 0\n'
        p.scripts['postrm']=p.scripts['postinst']
        return p

    def updates():
        p=package('amerika-updates','Amerika signed update channels\nStable by default; testing requires an explicit opt-in. Ubuntu security origins stay enabled.',depends='apt, unattended-upgrades')
        p.copy(flavor/'updates/52amerika-unattended-upgrades','/etc/apt/apt.conf.d/52amerika-unattended-upgrades')
        p.copy(flavor/'updates/amerika.pref','/etc/apt/preferences.d/amerika')
        p.copy(flavor/'updates/amerika-testing.sources','/etc/apt/sources.list.d/amerika-testing.sources')
        p.copy(flavor/'updates/amerika-channel','/usr/sbin/amerika-channel',0o755)
        p.file('/etc/amerika-os/channel','stable\n')
        return p

    def docs():
        p=package('amerika-doc','Amerika desktop manuals and recovery documentation',section='doc')
        for source in (flavor/'man').glob('*.[178]'):
            dest=p.path('/usr/share/man/man'+source.suffix[1:]+'/'+source.name+'.gz')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
        for source in (b.ROOT/'docs').glob('*.md'):p.copy(source,'/usr/share/doc/amerika-doc/'+source.name)
        return p

    result={'amerika-branding':branding,'amerika-defaults':defaults,'amerika-updates':updates,'amerika-doc':docs}
    for seed,name in (('standard','amerika-standard'),('desktop-minimal','amerika-desktop-minimal'),('desktop-full','amerika-desktop-full')):
        def meta(seed=seed,name=name):
            fields=read_seed(flavor/'seeds'/seed)
            p=package(name,fields['Task-Description'],section='metapackages',
                      depends=', '.join(fields.get('Depends',[])),recommends=', '.join(fields.get('Recommends',[])))
            p.copy(flavor/'seeds'/seed,'/usr/share/amerika-os/seeds/'+seed)
            return p
        result[name]=meta
    return result
