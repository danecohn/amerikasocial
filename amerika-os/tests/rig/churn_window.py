"""A window whose title keeps changing, like an Electron app updating its title: floods the window bridge with updates."""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk
n = [0]
def act(app):
    w = Gtk.ApplicationWindow(application=app, title='Churn 0'); w.set_default_size(500, 300); w.set_child(Gtk.Label(label='churn')); w.present()
    def tick():
        n[0] += 1; w.set_title(f'Churn {n[0]}'); return True
    GLib.timeout_add(150, tick)
    GLib.timeout_add_seconds(40, app.quit)
a = Gtk.Application(application_id='org.amerika.Churn'); a.connect('activate', act); a.run([])
