"""Wallpaper layer (the desktop itself)."""
import os
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402

from .. import common
from . import layer

WALLPAPERS = ('horizon', 'grid', 'dusk')


def wallpaper_path(name):
    for base in (Path(os.environ.get('AMERIKA_WALLPAPERS', '')), Path('/usr/share/backgrounds/amerika'), common.SHARE / 'wallpapers'):
        for ext in ('png', 'jpg'):
            p = base / f'{name}.{ext}'
            if p.is_file():
                return p
    return None


class Desktop(Gtk.Window):
    def __init__(self, app, settings):
        super().__init__(application=app, title='Amerika Desktop')
        self.add_css_class('am-desktop')
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.set_child(self.picture)
        layer.setup(self, 'background', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, namespace='amerika-desktop')
        self.apply(settings)

    def apply(self, settings):
        path = wallpaper_path(settings.get('wallpaper', 'horizon'))
        if path:
            self.picture.set_filename(str(path))
