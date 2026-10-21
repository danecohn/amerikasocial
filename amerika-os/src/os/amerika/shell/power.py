"""Power menu dialog."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from .. import system
from . import layer


class PowerDialog(Gtk.Window):
    def __init__(self, shell):
        super().__init__(application=shell, title='Power')
        self.add_css_class('am-overlay')
        layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, keyboard='exclusive',
                    namespace='amerika-power')
        outer = Gtk.CenterBox()
        self.set_child(outer)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        card.add_css_class('am-panel')
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(inner, f'set_margin_{m}')(24)
        card.append(inner)
        outer.set_center_widget(card)
        title = Gtk.Label(label='POWER', xalign=0)
        title.add_css_class('am-label')
        inner.append(title)
        row = Gtk.Box(spacing=10)
        for label, fn, css in (('Sleep', lambda: system.power_action('suspend'), 'am-secondary'),
                               ('Restart', lambda: system.power_action('reboot'), 'am-secondary'),
                               ('Shut down', lambda: system.power_action('poweroff'), 'am-primary'),
                               ('Cancel', None, 'am-secondary')):
            b = Gtk.Button(label=label)
            b.add_css_class(css)
            b.connect('clicked', lambda _b, f=fn: (self.destroy(), f() if f else None))
            row.append(b)
        inner.append(row)
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', lambda c, k, *_: (self.destroy(), True)[1] if k == Gdk.KEY_Escape else False)
        self.add_controller(keys)
        self.present()
