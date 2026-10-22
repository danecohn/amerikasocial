"""The dock: pinned apps (the AI apps first), running windows, always visible."""
import os

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
        self.position = shell.settings.get('dock_position', 'bottom')
        if self.position not in ('bottom', 'right', 'left'):
            self.position = 'bottom'
        edge = {'bottom': ('bottom',), 'right': ('right',), 'left': ('left',)}[self.position]
        layer.setup(self, 'top', anchors=edge, margins={self.position: 10 if self.position == 'bottom' else 14}, exclusive='auto',
                    keyboard=os.environ.get('AMERIKA_DOCK_KEYBOARD', 'on_demand'), namespace='amerika-dock')
        self.vertical = self.position != 'bottom'
        self.box = Gtk.Box(spacing=2 if not self.vertical else 6, orientation=Gtk.Orientation.VERTICAL if self.vertical else Gtk.Orientation.HORIZONTAL)
        self.box.add_css_class('am-dock-box')
        if self.vertical:
            self.add_css_class('vertical')
            self.box.add_css_class('vertical')
        self.set_child(self.box)
        shell.windows.connect('changed', lambda *_: self.rebuild())
        self.rebuild()

    def _pinned(self):
        return self.shell.settings.get('dock_pinned', [])

    def _layout(self):
        """What the dock should show: (entries, extra running apps). Entries are (id, info, running windows)."""
        ai_ids = set(self.shell.settings.get('bar_ai_apps', [])) | {'amerika-agent'}  # agent-ui: the agent sits in the AI group
        shown, entries, extra = set(), [], []
        for desktop_id in self._pinned():
            info = apps.lookup(desktop_id)
            if info:
                entries.append((desktop_id, info, bool(self.shell.windows.windows_for(desktop_id))))
                shown.add(desktop_id.lower())
        for w in self.shell.windows.app_windows():
            key = str(w.get('desktopFile') or w.get('cls') or '').removesuffix('.desktop')
            if not key or key.lower() in shown:
                continue
            info = apps.lookup(key) or apps.lookup(str(w.get('cls', '')))
            if info:
                extra.append((key, info, True))
                shown.add(key.lower())
        return entries, extra, ai_ids

    def rebuild(self, force=False):
        """Rebuild only when something the dock shows has changed, and never under an open menu."""
        entries, extra, ai_ids = self._layout()
        size = int(self.shell.settings.get('dock_size', 56))
        signature = (size, self.position, tuple((i, r) for i, _, r in entries), tuple(k for k, _, _ in extra), tuple(sorted(ai_ids)))
        if not force and signature == getattr(self, '_signature', None):
            return
        menu = getattr(self, '_open_menu', None)
        if menu is not None and menu.get_mapped() and not force:
            self._rebuild_pending = True
            return
        self._signature = signature
        self._rebuilds = getattr(self, '_rebuilds', 0) + 1
        child = self.box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.box.remove(child)
            child = nxt
        sep_after = 0
        for i, (desktop_id, _info, _running) in enumerate(entries):
            if desktop_id in ai_ids:
                sep_after = i + 1
        for i, (desktop_id, info, _running) in enumerate(entries):
            self.box.append(self._item(desktop_id, info, size, ai=desktop_id in ai_ids))
            if sep_after and i + 1 == sep_after and i + 1 < len(entries):
                sep = Gtk.Box()
                sep.add_css_class('am-dock-sep')
                if self.vertical:
                    sep.add_css_class('vertical')
                self.box.append(sep)
        if extra:
            sep = Gtk.Box()
            sep.add_css_class('am-dock-sep')
            if self.vertical:
                sep.add_css_class('vertical')
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
        pop.set_position({'right': Gtk.PositionType.LEFT, 'left': Gtk.PositionType.RIGHT}.get(self.position, Gtk.PositionType.TOP))
        pop.set_autohide(True)
        pop.set_parent(button)
        self._open_menu = pop
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
        self._opened_at = GLib.get_monotonic_time()
        pop.connect('closed', lambda p: self._menu_closed(p))
        pop.popup()

    def _menu_closed(self, pop):
        self._closed_after_ms = (GLib.get_monotonic_time() - self._opened_at) // 1000
        GLib.idle_add(pop.unparent)
        self._open_menu = None
        if getattr(self, '_rebuild_pending', False):
            self._rebuild_pending = False
            GLib.idle_add(self.rebuild)

    def debug_menu(self):
        """Test hook: open the context menu of the first dock item as a right click would."""
        button = self.box.get_first_child()
        while button and not isinstance(button, Gtk.Button):
            button = button.get_next_sibling()
        if button:
            self._closed_after_ms = None
            self._menu(button, 'amerika-files', apps.lookup('amerika-files') or apps.lookup('chatgpt'), [])

    def _pin(self, desktop_id, pin):
        pinned = list(self._pinned())
        if pin and desktop_id not in pinned:
            pinned.append(desktop_id)
        if not pin and desktop_id in pinned:
            pinned.remove(desktop_id)
        self.shell.settings['dock_pinned'] = pinned
        common.save_settings(self.shell.settings)
        self.rebuild(force=True)
