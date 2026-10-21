"""Startup screen: shown from the moment the compositor is up until the shell reports that its bar and dock are on screen."""
import os
import sys
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import common, theme
from .shell import layer
from .shell.desktop import wallpaper_path

READY_FILE = common.RUNTIME / 'shell-ready'
MESSAGES = ['STARTING THE SHELL', 'LOADING YOUR APPS', 'WARMING UP THE HORIZON', 'ALMOST THERE']
MAX_SECONDS = 25


class Splash(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, title='Amerika startup')
        self.add_css_class('am-splash')
        layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, namespace='amerika-splash')
        root = Gtk.Overlay()
        self.set_child(root)
        pic = Gtk.Picture()
        pic.set_content_fit(Gtk.ContentFit.COVER)
        path = wallpaper_path(common.load_settings().get('wallpaper', 'horizon'))
        if path:
            pic.set_filename(str(path))
        root.set_child(pic)
        veil = Gtk.Box()
        veil.add_css_class('am-splash-veil')
        root.add_overlay(veil)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        root.add_overlay(col)
        logo = Gtk.Image.new_from_icon_name('amerika-home')
        logo.set_pixel_size(150)
        col.append(logo)
        word = Gtk.Label(label='AMERIKA OS')
        word.add_css_class('am-splash-word')
        col.append(word)
        self.status = Gtk.Label(label=MESSAGES[0])
        self.status.add_css_class('am-splash-status')
        col.append(self.status)
        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class('am-splash-bar')
        self.bar.set_size_request(320, -1)
        col.append(self.bar)
        self.content = col
        self.started = time.monotonic()
        self.fading_out = False
        self.set_opacity(0.0)
        self.present()
        GLib.timeout_add(16, self._fade_in)
        GLib.timeout_add(90, self._pulse)
        GLib.timeout_add(1400, self._message)
        GLib.timeout_add(200, self._check_ready)

    def _fade_in(self):
        o = min(1.0, self.get_opacity() + 0.06)
        self.set_opacity(o)
        return o < 1.0

    def _pulse(self):
        self.bar.pulse()
        return not self.fading_out

    def _message(self):
        i = (MESSAGES.index(self.status.get_text()) + 1) % len(MESSAGES) if self.status.get_text() in MESSAGES else 0
        self.status.set_text(MESSAGES[i])
        return not self.fading_out

    def _check_ready(self):
        waited = time.monotonic() - self.started
        if (READY_FILE.exists() and waited > 1.6) or waited > MAX_SECONDS:
            GLib.timeout_add(500 if waited <= MAX_SECONDS else 0, self._fade_out)
            return False
        return True

    def _fade_out(self):
        self.fading_out = True
        self.status.set_text('READY')

        def step():
            o = max(0.0, self.get_opacity() - 0.05)
            self.set_opacity(o)
            if o <= 0.0:
                self.get_application().quit()
                return False
            return True
        GLib.timeout_add(16, step)
        return False


class SplashApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.amerika.Splash')

    def do_activate(self):
        display = Gdk.Display.get_default()
        dev_icons = os.environ.get('AMERIKA_ICONS')
        icons = Gtk.IconTheme.get_for_display(display)
        if dev_icons:
            icons.set_search_path([dev_icons] + list(icons.get_search_path() or []))
        Gtk.Settings.get_default().set_property('gtk-icon-theme-name', 'AmerikaOS')
        theme.apply(common.load_settings().get('accent', '#ff2e63'), common.load_settings().get('secondary', '#19e3ff'))
        Splash(self)
        shots = os.environ.get('AMERIKA_SPLASH_SHOT')
        if shots:
            from .shell.app import save_widget
            GLib.timeout_add(1800, lambda: (save_widget(self.get_windows()[0], __import__('pathlib').Path(shots)), False)[1])
        self.hold()


def main():
    os.environ.pop('LD_PRELOAD', None)
    return SplashApp().run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
