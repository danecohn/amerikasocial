"""A tiny stand-in for the Claude / ChatGPT desktop apps: one GTK window whose Wayland app_id is the class given as argv[1].

Env: FAKE_AI_LOG (file to append "launch <class> pid=<pid> ld_preload=<set|unset> args=<...>" to, one line per start),
FAKE_AI_EXIT_AFTER (seconds after which the window closes and the process exits, 0 = never),
FAKE_AI_SIZE (WxH default window size, default 760x520).
"""
import os
import sys

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

cls = sys.argv[1]
args = sys.argv[2:]
log = os.environ.get('FAKE_AI_LOG')
if log:
    with open(log, 'a') as fh:
        fh.write('launch %s pid=%d ld_preload=%s args=%s\n' % (cls, os.getpid(), 'set' if os.environ.get('LD_PRELOAD') else 'unset', ' '.join(args)))
GLib.set_prgname(cls)
w, h = (int(x) for x in os.environ.get('FAKE_AI_SIZE', '760x520').split('x'))


def activate(app):
    win = Gtk.ApplicationWindow(application=app, title='Fake %s' % cls)
    win.set_default_size(w, h)
    label = Gtk.Label(label='FAKE %s' % cls.upper())
    label.add_css_class('title-1')
    win.set_child(label)
    win.present()
    after = float(os.environ.get('FAKE_AI_EXIT_AFTER', '0'))
    if after > 0:
        GLib.timeout_add(int(after * 1000), lambda: (app.quit(), False)[1])


app = Gtk.Application(application_id=cls if '.' in cls else None)
app.connect('activate', activate)
sys.exit(app.run([sys.argv[0]]))
