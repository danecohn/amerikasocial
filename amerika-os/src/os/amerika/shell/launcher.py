"""The Windows-key app menu: every app in a grid, search, categories, recent apps, Home/Settings/Lock/Power, and one-key
hand-off to the AI apps (Ask Claude / Ask ChatGPT, ordered by the home mode)."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import apps, home, layer
from .agent_ask import AskPanel  # agent-ui

GROUP_ORDER = [name for name, _ in apps.CATEGORY_GROUPS] + ['Other']


def ask_order(settings):
    """Desktop ids for the Ask row: the home app first when home mode is on, then the rest of the configured AI apps."""
    ids = list(settings.get('bar_ai_apps', []))
    key = home.home_key(settings)
    if key:
        first = home.APPS[key]['id']
        ids = [first] + [i for i in [home.APPS[k]['id'] for k in home.APPS] + ids if i != first]
        seen = []
        for i in ids:
            if i not in seen:
                seen.append(i)
        ids = seen
    return ids


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
        panel.set_size_request(940, 660)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(inner, f'set_margin_{m}')(22)
        panel.append(inner)
        outer.set_center_widget(panel)

        title = Gtk.Label(label='APPS  ·  ASK  ·  SEARCH', xalign=0)
        title.add_css_class('am-label')
        inner.append(title)
        self.entry = Gtk.SearchEntry()
        self.entry.add_css_class('am-search')
        self.entry.set_placeholder_text('Search apps, or ask Claude or ChatGPT…')
        self.entry.set_key_capture_widget(self)
        self.entry.connect('search-changed', lambda *_: self._refresh())
        self.entry.connect('activate', lambda *_: self._activate_first())
        inner.append(self.entry)

        self.ask_box = Gtk.Box(spacing=10)
        inner.append(self.ask_box)
        self.agent_ask = AskPanel(shell)  # agent-ui: "Ask Amerika Agent" row + streamed answer
        inner.append(self.agent_ask)

        self.chip_row = Gtk.Box(spacing=6)
        inner.append(self.chip_row)
        self.recent_label = Gtk.Label(label='RECENT', xalign=0)
        self.recent_label.add_css_class('am-recent-label')
        inner.append(self.recent_label)
        self.recent_box = Gtk.Box(spacing=4)
        inner.append(self.recent_box)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=7, min_children_per_line=4,
                                homogeneous=True, row_spacing=4, column_spacing=4)
        scroller.set_child(self.flow)
        inner.append(scroller)

        self.footer = Gtk.Box(spacing=8)
        inner.append(self.footer)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect('key-pressed', self._key)
        self.add_controller(keys)
        # click outside the panel closes
        click = Gtk.GestureClick()
        click.connect('pressed', lambda g, n, x, y: self._outside(panel, x, y))
        outer.add_controller(click)
        self._apps = []
        self._shown_apps = []
        self._category = 'All'
        self._ai_mode = False
        self.connect('notify::visible', lambda *_: self._shown())

    def _outside(self, panel, x, y):
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is None or not (picked is panel or picked.is_ancestor(panel)):
            self.hide()

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            if self.entry.get_text():
                self.entry.set_text('')
            else:
                self.hide()
            return True
        if keyval == Gdk.KEY_Down and self.entry.has_focus() and self.flow.get_first_child() is not None:
            first = self.flow.get_first_child().get_child()
            if first is not None:
                first.grab_focus()
                return True
        return False

    def present_ai(self):
        """Open with the Claude / ChatGPT choice up front (the Copilot key in 'ask' mode)."""
        self._ai_mode = True
        if self.get_visible():
            self._shown()
        else:
            self.present()

    def _shown(self):
        if not self.get_visible():
            self._ai_mode = False
            self.agent_ask.reset()  # agent-ui
        if self.get_visible():
            self._apps = apps.all_apps()
            self._category = 'All'
            self.entry.set_text('')
            self._build_footer()
            self._refresh()
            self.entry.grab_focus()

    # ------------------------------------------------------------------ pieces
    @staticmethod
    def _clear(box):
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _build_footer(self):
        self._clear(self.footer)

        def add(label, fn):
            b = Gtk.Button(label=label.upper())
            b.add_css_class('am-footer-btn')
            b.connect('clicked', lambda *_: (self.hide(), fn()))
            self.footer.append(b)
        if home.home_key(self.shell.settings):
            add('Home', self.shell.go_home)
        add('Settings', self.shell.open_settings)
        spacer = Gtk.Box(hexpand=True)
        self.footer.append(spacer)
        add('Lock', lambda: self.shell.action('lock'))
        add('Power', self.shell.confirm_power)

    def _ask_row(self, text):
        self._clear(self.ask_box)
        if not (text or self._ai_mode or home.home_key(self.shell.settings)):
            return
        for desktop_id in ask_order(self.shell.settings):
            info = apps.lookup(desktop_id)
            if not info:
                continue
            b = Gtk.Button()
            b.add_css_class('am-ask')
            row = Gtk.Box(spacing=8)
            row.append(apps.icon_image(info, 22))
            row.append(Gtk.Label(label=f'Ask {info.get_display_name()}' if (text or home.home_key(self.shell.settings)) else f'Open {info.get_display_name()}'))
            b.set_child(row)
            b.connect('clicked', lambda _b, d=desktop_id: self._ask(d))
            self.ask_box.append(b)
        if self._ai_mode and not text:  # agent-ui: the Copilot-key picker also offers Amerika Agent
            b = Gtk.Button()
            b.add_css_class('am-ask')
            row = Gtk.Box(spacing=8)
            row.append(apps.icon_image('amerika-ai', 22))
            row.append(Gtk.Label(label='Open Amerika Agent'))
            b.set_child(row)
            b.connect('clicked', lambda *_: (self.hide(), self.shell.open_agent_window()))
            self.ask_box.append(b)

    def _groups_present(self):
        present = {apps.group_of(i.get_categories()) for i in self._apps}
        return [g for g in GROUP_ORDER if g in present]

    def _chips(self, text):
        self._clear(self.chip_row)
        self.chip_row.set_visible(not text)
        for name in ['All'] + self._groups_present():
            b = Gtk.Button(label=name.upper())
            b.add_css_class('am-chip')
            if name == self._category:
                b.add_css_class('active')
            b.connect('clicked', lambda _b, n=name: self._pick_category(n))
            self.chip_row.append(b)

    def _pick_category(self, name):
        self._category = name
        self._refresh()

    def _recent(self, text):
        self._clear(self.recent_box)
        infos = [apps.lookup(i) for i in (self.shell.settings.get('recent_apps') or [])]
        infos = [i for i in infos if i][:6]
        show = bool(infos) and not text and self._category == 'All'
        self.recent_label.set_visible(show)
        self.recent_box.set_visible(show)
        if not show:
            return
        for info in infos:
            b = Gtk.Button()
            b.add_css_class('am-app')
            row = Gtk.Box(spacing=8)
            row.append(apps.icon_image(info, 28))
            row.append(Gtk.Label(label=info.get_display_name()))
            b.set_child(row)
            b.connect('clicked', lambda _b, i=info: self._open(i))
            self.recent_box.append(b)

    def _refresh(self):
        text = self.entry.get_text().strip().lower()
        self.agent_ask.update(self.entry.get_text())  # agent-ui
        self._clear(self.flow)
        self._ask_row(text)
        self._chips(text)
        self._recent(text)
        self._shown_apps = []
        for info in self._apps:
            hay = (info.get_display_name() + ' ' + (info.get_generic_name() or '') + ' ' + ' '.join(info.get_keywords() or [])).lower()
            if text and text not in hay:
                continue
            if not text and self._category != 'All' and apps.group_of(info.get_categories()) != self._category:
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
        self.shell.note_recent(info.get_id())
        apps.launch(info)

    def _ask(self, desktop_id):
        text = self.entry.get_text().strip()
        self.hide()
        self.shell.hand_off_to_ai(desktop_id, text)

    def _activate_first(self):
        if self.agent_ask.question and (self.agent_ask.explicit or not self._shown_apps):  # agent-ui
            self.agent_ask.submit()
            return
        if self._shown_apps and self.entry.get_text().strip():
            self._open(self._shown_apps[0])
