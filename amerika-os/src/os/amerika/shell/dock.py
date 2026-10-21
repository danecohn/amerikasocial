"""The dock: pinned apps (the AI apps first), running windows, always visible."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .. import common
from . import apps, layer


class Dock(Gtk.Window):
    def __init__(self, shell):
        super().__init__(application=shell, title='Amerika Dock')
        self.shell = shell
        self.add_css_class('am-dock')
        layer.setup(self, 'top', anchors=('bottom',), margins={'bottom': 10}, exclusive='auto', namespace='amerika-dock')
        self.box = Gtk.Box(spacing=2)
        self.box.add_css_class('am-dock-box')
        self.set_child(self.box)
        shell.windows.connect('changed', lambda *_: self.rebuild())
        self.rebuild()

    def _pinned(self):
        return self.shell.settings.get('dock_pinned', [])

    def rebuild(self):
        child = self.box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.box.remove(child)
            child = nxt
        size = int(self.shell.settings.get('dock_size', 56))
        ai_ids = set(self.shell.settings.get('bar_ai_apps', []))
        shown = set()
        entries = []
        for desktop_id in self._pinned():
            info = apps.lookup(desktop_id)
            if info:
                entries.append((desktop_id, info, True))
                shown.add(desktop_id.lower())
        # running apps that are not pinned
        extra = []
        for w in self.shell.windows.app_windows():
            key = str(w.get('desktopFile') or w.get('cls') or '').removesuffix('.desktop')
            if not key or key.lower() in shown:
                continue
            info = apps.lookup(key) or apps.lookup(str(w.get('cls', '')))
            if info and key.lower() not in shown:
                extra.append((key, info, False))
                shown.add(key.lower())
        sep_after = 0
        for i, (desktop_id, info, pinned) in enumerate(entries):
            if desktop_id in ai_ids:
                sep_after = i + 1
        for i, (desktop_id, info, pinned) in enumerate(entries):
            self.box.append(self._item(desktop_id, info, size, ai=desktop_id in ai_ids))
            if sep_after and i + 1 == sep_after and i + 1 < len(entries):
                sep = Gtk.Box()
                sep.add_css_class('am-dock-sep')
                self.box.append(sep)
        if extra:
            sep = Gtk.Box()
            sep.add_css_class('am-dock-sep')
            self.box.append(sep)
            for desktop_id, info, _ in extra:
                self.box.append(self._item(desktop_id, info, size, ai=False))

    def _item(self, desktop_id, info, size, ai):
        running = self.shell.windows.windows_for(desktop_id)
        button = Gtk.Button()
        button.add_css_class('am-dock-item')
        if ai:
            button.add_css_class('am-dock-ai')
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, halign=Gtk.Align.CENTER)
        col.append(apps.icon_image(info, size))
        dot = Gtk.Box(halign=Gtk.Align.CENTER)
        dot.add_css_class('am-dock-dot')
        dot.set_opacity(1.0 if running else 0.0)
        col.append(dot)
        button.set_child(col)
        button.set_tooltip_text(info.get_display_name())
        button.connect('clicked', lambda _b: self.shell.activate_app(desktop_id))
        click = Gtk.GestureClick(button=3)
        click.connect('pressed', lambda g, n, x, y: self._menu(button, desktop_id, info, running))
        button.add_controller(click)
        return button

    def _menu(self, button, desktop_id, info, running):
        pop = Gtk.Popover()
        pop.add_css_class('am-panel')
        pop.set_parent(button)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(col, f'set_margin_{m}')(8)

        def add(title, fn):
            b = Gtk.Button(label=title)
            b.add_css_class('am-secondary')
            b.connect('clicked', lambda *_: (pop.popdown(), fn()))
            col.append(b)

        add('Open new window', lambda: apps.launch(info))
        if running:
            add('Close windows', lambda: [self.shell.windows.command('close', w['id']) for w in running])
        pinned = self._pinned()
        if desktop_id in pinned:
            add('Remove from dock', lambda: self._pin(desktop_id, False))
        else:
            add('Keep in dock', lambda: self._pin(desktop_id, True))
        pop.set_child(col)
        pop.connect('closed', lambda p: GLib.idle_add(p.unparent))
        pop.popup()

    def _pin(self, desktop_id, pin):
        pinned = list(self._pinned())
        if pin and desktop_id not in pinned:
            pinned.append(desktop_id)
        if not pin and desktop_id in pinned:
            pinned.remove(desktop_id)
        self.shell.settings['dock_pinned'] = pinned
        common.save_settings(self.shell.settings)
        self.rebuild()
