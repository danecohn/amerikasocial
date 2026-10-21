"""Approval prompts for AI actions: a full-screen dim with a card that names the app, the action and its details."""
import json
from concurrent.futures import Future

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ..ai.broker import CLIENT_NAMES
from . import apps, layer

RISK_TEXT = {'act': 'Changes your desktop or settings', 'sensitive': 'Could change or expose your data',
             'critical': 'Powers off, restarts or deletes'}


class Approval(Gtk.Window):
    def __init__(self, shell, client, tool, args, risk):
        super().__init__(application=shell, title='Amerika approval')
        self.future = Future()
        self.add_css_class('am-overlay')
        layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, keyboard='exclusive',
                    namespace='amerika-approval')
        label = CLIENT_NAMES.get(client, client.title())
        outer = Gtk.CenterBox()
        self.set_child(outer)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        card.add_css_class('am-panel')
        card.set_size_request(560, -1)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(inner, f'set_margin_{m}')(24)
        card.append(inner)
        outer.set_center_widget(card)

        head = Gtk.Box(spacing=12)
        for desktop_id in ('com.anthropic.Claude' if client == 'claude' else 'chatgpt',):
            info = apps.lookup(desktop_id)
            head.append(apps.icon_image(info if info else 'amerika-ai', 40))
        title = Gtk.Label(label=f'{label.upper()} WANTS TO OPERATE YOUR COMPUTER', xalign=0, wrap=True, hexpand=True)
        title.add_css_class('am-heading')
        title.set_markup(f'<span size="large" weight="heavy">{GLib.markup_escape_text(label)} wants permission</span>')
        head.append(title)
        inner.append(head)

        desc = shell.broker.tools.table[tool]['description']
        what = Gtk.Label(label=desc, xalign=0, wrap=True)
        inner.append(what)
        tag = Gtk.Label(label=f'{tool}   ·   {RISK_TEXT.get(risk, risk)}'.upper(), xalign=0)
        tag.add_css_class('am-label')
        inner.append(tag)
        if args:
            view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
            view.get_buffer().set_text(json.dumps(args, indent=2, ensure_ascii=False)[:4000])
            scroller = Gtk.ScrolledWindow(min_content_height=60, max_content_height=220, propagate_natural_height=True)
            scroller.set_child(view)
            inner.append(scroller)

        buttons = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        deny = Gtk.Button(label='Deny')
        deny.add_css_class('am-secondary')
        deny.connect('clicked', lambda *_: self.finish('deny'))
        buttons.append(deny)
        if risk != 'critical':
            always = Gtk.Button(label=f'Always allow this for {label}')
            always.add_css_class('am-secondary')
            always.connect('clicked', lambda *_: self.finish('always'))
            buttons.append(always)
        allow = Gtk.Button(label='Allow once')
        allow.add_css_class('am-primary')
        allow.connect('clicked', lambda *_: self.finish('once'))
        buttons.append(allow)
        inner.append(buttons)

        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', lambda c, k, *_: (self.finish('deny'), True)[1] if k == Gdk.KEY_Escape else False)
        self.add_controller(keys)
        GLib.timeout_add_seconds(90, lambda: (self.finish('deny'), False)[1])
        self.present()
        deny.grab_focus()

    def finish(self, verdict):
        if not self.future.done():
            self.future.set_result(verdict)
            self.destroy()
