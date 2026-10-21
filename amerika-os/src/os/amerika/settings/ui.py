"""GTK building blocks shared by every settings page (retro-futurist cards, rows, async helpers)."""
import threading

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402


def label(text, css=None, xalign=0.0, wrap=False):
    lab = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    for c in (css or '').split():
        lab.add_css_class(c)
    return lab


def card(*children, spacing=10):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    box.add_css_class('am-card')
    for c in children:
        box.append(c)
    return box


def page_box():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    for m in ('top', 'bottom', 'start', 'end'):
        getattr(box, f'set_margin_{m}')(26)
    return box


def scrolled(child):
    s = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    s.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    s.set_child(child)
    return s


def clear(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def page(title, intro=None):
    """A page body with its heading (and optional intro line). Returns the box to append cards to."""
    box = page_box()
    box.append(label(title.upper(), 'am-heading'))
    if intro:
        box.append(label(intro, 'am-sub', wrap=True))
    return box


def section(title, *children, note=None):
    """A card with an uppercase caption. Children are rows or any widget."""
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    if title:
        col.append(label(title.upper(), 'am-label'))
    for c in children:
        col.append(c)
    if note:
        col.append(label(note, 'am-sub', wrap=True))
    return card(col)


def row(title, sub=None, control=None, css='am-appname'):
    """Title (+ optional dim subtitle) on the left, a control on the right."""
    box = Gtk.Box(spacing=12)
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
    t = label(title, css, wrap=True)
    col.append(t)
    if sub:
        col.append(label(sub, 'am-sub', wrap=True))
    box.append(col)
    if control is not None:
        control.set_valign(Gtk.Align.CENTER)
        box.append(control)
    return box


def switch(active, on_change):
    sw = Gtk.Switch()
    sw.set_active(bool(active))
    sw.connect('state-set', lambda _s, on: (on_change(on), False)[1])
    return sw


def switch_row(title, sub, active, on_change):
    sw = switch(active, on_change)
    r = row(title, sub, sw)
    r.switch = sw
    return r


def dropdown(options, current, on_change):
    """options: list of (value, text). on_change(value)."""
    drop = Gtk.DropDown.new_from_strings([t for _v, t in options])
    for i, (v, _t) in enumerate(options):
        if v == current:
            drop.set_selected(i)
            break
    drop.connect('notify::selected', lambda d, _p: on_change(options[d.get_selected()][0]) if d.get_selected() < len(options) else None)
    drop.options = options
    return drop


def dropdown_row(title, sub, options, current, on_change):
    d = dropdown(options, current, on_change)
    r = row(title, sub, d)
    r.drop = d
    return r


def slider(lo, hi, step, value, on_change, width=240, digits=0):
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
    scale.set_draw_value(True)
    scale.set_digits(digits)
    scale.set_value(value)
    scale.set_size_request(width, -1)
    scale.connect('value-changed', lambda s: on_change(s.get_value()))
    return scale


def slider_row(title, sub, lo, hi, step, value, on_change, width=240, digits=0):
    s = slider(lo, hi, step, value, on_change, width, digits)
    r = row(title, sub, s)
    r.scale = s
    return r


def button(text, on_click, primary=False, danger=False):
    b = Gtk.Button(label=text)
    b.add_css_class('am-primary' if primary else 'am-secondary')
    b.connect('clicked', lambda *_: on_click())
    b.set_valign(Gtk.Align.CENTER)
    return b


def entry(text='', placeholder='', on_activate=None):
    e = Gtk.Entry()
    e.set_text(text)
    e.set_placeholder_text(placeholder)
    if on_activate:
        e.connect('activate', lambda *_: on_activate(e.get_text()))
    return e


def status_label():
    return label('', 'am-sub', wrap=True)


def pill(text, css='am-label'):
    return label(text, css)


def empty_state(text):
    return label(text, 'am-sub', wrap=True)


def async_call(fn, done=None, *args):
    """Run fn(*args) on a worker thread, then done(result) on the GTK main loop. Exceptions become None results."""
    def work():
        try:
            result = fn(*args)
        except Exception as error:  # noqa: BLE001 - a failing backend must never crash the UI
            print('settings backend error:', fn, type(error).__name__, flush=True)
            result = None
        if done:
            GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=work, daemon=True).start()


def confirm(parent, title, text, on_yes, yes_label='Continue'):
    win = Gtk.Window(transient_for=parent, modal=True, title=title, default_width=420)
    win.add_css_class('am-dialog')
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    for m in ('top', 'bottom', 'start', 'end'):
        getattr(box, f'set_margin_{m}')(20)
    box.append(label(title.upper(), 'am-heading'))
    box.append(label(text, 'am-sub', wrap=True))
    btns = Gtk.Box(spacing=10, halign=Gtk.Align.END)
    btns.append(button('Cancel', win.close))
    btns.append(button(yes_label, lambda: (win.close(), on_yes()), primary=True))
    box.append(btns)
    win.set_child(box)
    win.present()
    return win


def password_dialog(parent, title, text, on_submit, submit_label='Connect'):
    """Ask for a secret in-process. The value goes straight to on_submit and is never stored by the dialog."""
    win = Gtk.Window(transient_for=parent, modal=True, title=title, default_width=420)
    win.add_css_class('am-dialog')
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    for m in ('top', 'bottom', 'start', 'end'):
        getattr(box, f'set_margin_{m}')(20)
    box.append(label(title.upper(), 'am-heading'))
    box.append(label(text, 'am-sub', wrap=True))
    pw = Gtk.PasswordEntry(show_peek_icon=True)
    box.append(pw)

    def submit():
        secret = pw.get_text()
        pw.set_text('')
        win.close()
        on_submit(secret)
    pw.connect('activate', lambda *_: submit())
    btns = Gtk.Box(spacing=10, halign=Gtk.Align.END)
    btns.append(button('Cancel', win.close))
    btns.append(button(submit_label, submit, primary=True))
    box.append(btns)
    win.set_child(box)
    win.present()
    pw.grab_focus()
    return win


def list_box():
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)


def divider():
    return Gtk.Separator()
