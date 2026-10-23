"""Rebuild the AltStack Render splash while preserving the approved logo."""
from pathlib import Path
from PIL import Image, ImageDraw
HERE=Path(__file__).resolve().parent.parent
def icon():
    return HERE/'icons/amerika-render.svg'
def splash():
    image=Image.new('RGB',(960,540),'#e7edf3')
    logo=Image.open(HERE/'data/altstack-logo.png').convert('RGBA')
    logo.thumbnail((240,240),Image.Resampling.LANCZOS)
    image.paste(logo,((960-logo.width)//2,70),logo)
    d=ImageDraw.Draw(image);d.text((430,360),'AltStack Render',fill='#233649')
    d.text((380,460),'Powered by Blender · AltStack LLC',fill='#51677c')
    image.save(HERE/'data/splash.png')
if __name__=='__main__':
    icon();splash()
