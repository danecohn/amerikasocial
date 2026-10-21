"""Full-screen launcher: app grid, search, and one-key hand-off to the AI apps."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import apps, layer


class Launcher(Gtk.Window):
    def __init__(self, shell):
        super().__init__(application=shell, title='Amerika Launcher')
        self.shell = shell
        self.add_css_class('am-overlay')
        layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, keyboard='exclusive',
                    namespace='amerika-launcher')
        outer = Gtk.CenterBox()
        self.set_child(outer)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        panel.add_css_class('am-panel')
        panel.set_size_request(860, 620)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(panel, f'set_margin_{m}')(0)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(inner, f'set_margin_{m}')(22)
        panel.append(inner)
        outer.set_center_widget(panel)

        title = Gtk.Label(label='ASK  ·  OPEN  ·  SEARCH', xalign=0)
        title.add_css_class('am-label')
        inner.append(title)
        self.entry = Gtk.SearchEntry()
        self.entry.add_css_class('am-search')
        self.entry.set_placeholder_text('Search apps, or ask Claude or ChatGPT…')
        self.entry.connect('search-changed', lambda *_: self._refresh())
        self.entry.connect('activate', lambda *_: self._activate_first())
        inner.append(self.entry)

        self.ask_box = Gtk.Box(spacing=10)
        inner.append(self.ask_box)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=4,
                                homogeneous=True, row_spacing=4, column_spacing=4)
        scroller.set_child(self.flow)
        inner.append(scroller)

        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._key)
        self.add_controller(keys)
        # click outside the panel closes
        click = Gtk.GestureClick()
        click.connect('pressed', lambda g, n, x, y: self._outside(panel, x, y))
        outer.add_controller(click)
        self._apps = []
        self.connect('notify::visible', lambda *_: self._shown())

    def _outside(self, panel, x, y):
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is None or not (picked is panel or picked.is_ancestor(panel)):
            self.hide()

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _shown(self):
        if self.get_visible():
            self._apps = apps.all_apps()
            self.entry.set_text('')
            self._refresh()
            self.entry.grab_focus()

    def _refresh(self):
        text = self.entry.get_text().strip().lower()
        child = self.flow.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.flow.remove(child)
            child = nxt
        child = self.ask_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.ask_box.remove(child)
            child = nxt
        if text:
            for desktop_id in self.shell.settings.get('bar_ai_apps', []):
                info = apps.lookup(desktop_id)
                if info:
                    b = Gtk.Button()
                    b.add_css_class('am-ask')
                    row = Gtk.Box(spacing=8)
                    row.append(apps.icon_image(info, 22))
                    row.append(Gtk.Label(label=f'Ask {info.get_display_name()}'))
                    b.set_child(row)
                    b.connect('clicked', lambda _b, d=desktop_id: self._ask(d))
                    self.ask_box.append(b)
        self._shown_apps = []
        for info in self._apps:
            hay = (info.get_display_name() + ' ' + (info.get_generic_name() or '') + ' ' + ' '.join(info.get_keywords() or [])).lower()
            if text and text not in hay:
                continue
            self._shown_apps.append(info)
            b = Gtk.Button()
            b.add_css_class('am-app')
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            col.append(apps.icon_image(info, 56))
            lab = Gtk.Label(label=info.get_display_name(), wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=14)
            lab.add_css_class('am-sub')
            col.append(lab)
            b.set_child(col)
            b.connect('clicked', lambda _b, i=info: self._open(i))
            self.flow.append(b)

    def _open(self, info):
        self.hide()
        apps.launch(info)

    def _ask(self, desktop_id):
        text = self.entry.get_text().strip()
        self.hide()
        self.shell.hand_off_to_ai(desktop_id, text)

    def _activate_first(self):
        if self._shown_apps and self.entry.get_text().strip():
            self._open(self._shown_apps[0])
