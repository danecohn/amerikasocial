#!/usr/bin/env python3
"""Build a cosmetic Studio overlay; never rewrite installed apps, user projects or credentials."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/os'
TARGET=ROOT/'src/makos/compat'
NAMES={'Amerika Studio':'Studio','Amerika Render':'Render','Amerika Engine':'Engine','Amerika Sprite':'Sprite','AmerikaBox':'AltStack Box','AltStack Desktop':'MakOS'}


def prepare():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    def copy(src,dest):
        shutil.copytree(src,TARGET/dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    copy(SOURCE/'studio/amerika_studio','python/amerika_studio')
    copy(SOURCE/'engine/amerika_engine','python/amerika_engine')
    copy(SOURCE/'studio/web','studio-web')
    copy(SOURCE/'sprite/app','sprite')
    copy(SOURCE/'box/app','box')
    for name in ('addons','templates'):
        copy(SOURCE/'engine'/name,'engine/'+name)
    copy(SOURCE/'render/amerika_render','render/scripts/addons/amerika_render')
    copy(SOURCE/'render/startup','render/startup')
    copy(SOURCE/'render/theme','render/theme')
    (TARGET/'render').mkdir(exist_ok=True)
    shutil.copy2(SOURCE/'render/data/startup.blend',TARGET/'render/startup.blend')
    # Original generated MakOS artwork instead of the old branded splash.
    from PIL import Image,ImageDraw,ImageFont
    splash=Image.new('RGB',(640,360),'#e5e9ee')
    draw=ImageDraw.Draw(splash)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',36)
    draw.text((255,125),'Render',fill='#425a70',font=font)
    draw.text((180,195),'Powered by Blender',fill='#6c8193',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20))
    splash.save(TARGET/'render/splash.png')
    for path in TARGET.rglob('*'):
        if path.is_file() and path.suffix in ('.py','.gd','.cfg','.html','.css','.js','.json','.toml','.xml','.md'):
            text=path.read_text()
            for a,b in NAMES.items():
                text=text.replace(a,b)
            path.write_text(text)
    # Theme the GTK host in MakOS without touching original Studio settings or engine configuration.
    path=TARGET/'python/amerika_studio/ui.py'
    text=path.read_text()
    text=text.replace('    display = Gdk.Display.get_default()', '''    if os.environ.get('MAKOS_SESSION') == '1':
        from makos.ui import install_theme
        install_theme()
        return
    display = Gdk.Display.get_default()''',1)
    path.write_text(text)
    # Each cosmetic overlay retains the original notices and third-party licence files.
    for app in ('box','sprite','render','engine','studio'):
        dest=TARGET/'notices'/app
        dest.mkdir(parents=True,exist_ok=True)
        for path in (SOURCE/app).glob('*'):
            if path.is_file() and any(s in path.name.upper() for s in ('LICENSE','COPYING','NOTICE')):
                shutil.copy2(path,dest/path.name)
    print('Prepared original Studio cosmetics at',TARGET)

if __name__=='__main__':prepare()
