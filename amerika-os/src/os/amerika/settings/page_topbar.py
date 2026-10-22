"""Settings > Top bar: choose, place and order the bar widgets, the clock format, height and translucency, with a live preview."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

from ..shell import barlayout
from . import ui
from .page_home import commit, fresh

ZONE_CHOICES = [('left', 'Left'), ('center', 'Centre'), ('right', 'Right')]
HOUR_CHOICES = [(False, '12-hour'), (True, '24-hour')]


def build(app):
    box = ui.page('Top bar', 'Pick what the bar shows, where, and in which order. Changes apply to the bar immediately.')
    preview_holder = Gtk.Box()
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    box.append(ui.section('Preview', preview_holder, note='This is how the bar will look. It uses the same layout engine as the real bar.'))
    box.append(body)
    box.rows = {}

    def save(**kw):
        s = fresh()
        s.update(kw)
        commit(app, s)

    def preview():
        ui.clear(preview_holder)
        s = fresh()
        bar = Gtk.CenterBox(hexpand=True)
        bar.add_css_class('am-preview-bar')
        conf = barlayout.clock_format(s)
        zs = barlayout.zones(s.get('bar_layout'))
        boxes = {}
        for zone in barlayout.ZONES:
            z = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
            boxes[zone] = z
            for wid in zs[zone]:
                text = barlayout.WIDGETS[wid][0].upper()
                if wid == 'clock':
                    text = barlayout.format_time(conf)
                elif wid == 'date':
                    text = barlayout.format_date(conf) or 'DATE'
                z.append(ui.label(text, 'am-preview-chip'))
        bar.set_start_widget(boxes['left'])
        bar.set_center_widget(boxes['center'])
        bar.set_end_widget(boxes['right'])
        preview_holder.append(bar)
        preview_holder.set_hexpand(True)
        box.preview = bar

    def set_layout(layout):
        save(bar_layout=layout, bar_preset='custom')
        render()

    def render():
        ui.clear(body)
        s = fresh()
        layout = barlayout.normalize(s.get('bar_layout'))
        rows = []
        box.rows = {}
        for zone in barlayout.ZONES:
            for r in [r for r in layout if r['zone'] == zone]:
                wid = r['id']
                title, desc = barlayout.WIDGETS[wid]
                line = Gtk.Box(spacing=8)
                sw = ui.switch(r['enabled'], lambda on, w=wid: set_layout(barlayout.set_enabled(fresh().get('bar_layout'), w, on)))
                zone_drop = ui.dropdown(ZONE_CHOICES, r['zone'], lambda v, w=wid, cur=r['zone']: v != cur and set_layout(barlayout.set_zone(fresh().get('bar_layout'), w, v)))
                up = ui.button('Up', lambda w=wid: set_layout(barlayout.move(fresh().get('bar_layout'), w, -1)))
                down = ui.button('Down', lambda w=wid: set_layout(barlayout.move(fresh().get('bar_layout'), w, 1)))
                for w_ in (zone_drop, up, down, sw):
                    line.append(w_)
                row = ui.row(title, desc, line)
                row.switch, row.zone_drop = sw, zone_drop
                box.rows[wid] = row
                rows.append(row)
        body.append(ui.section('Widgets', *rows, note='Safety controls (the Stop button and the recording indicator) always stay on the right.'))

        conf = barlayout.clock_format(s)
        hour = ui.dropdown_row('Time format', None, HOUR_CHOICES, conf['hour24'], lambda v: (save(bar_clock_format={**barlayout.clock_format(fresh()), 'hour24': bool(v)}), preview()))
        seconds = ui.switch_row('Show seconds', None, conf['seconds'], lambda on: (save(bar_clock_format={**barlayout.clock_format(fresh()), 'seconds': bool(on)}), preview()))
        date = ui.dropdown_row('Date style', None, barlayout.DATE_STYLES, conf['date'], lambda v: (save(bar_clock_format={**barlayout.clock_format(fresh()), 'date': v}), preview()))
        body.append(ui.section('Clock', hour, seconds, date))

        timer = {}

        def debounced(key, value):
            if timer.get(key):
                GLib.source_remove(timer[key])
            timer[key] = GLib.timeout_add(250, lambda: (timer.pop(key, None), save(**{key: value}), preview(), False)[3])
        height = ui.slider_row('Height', 'Pixels', barlayout.HEIGHT_MIN, barlayout.HEIGHT_MAX, 1, barlayout.height(s), lambda v: debounced('bar_height', int(v)))
        opacity = ui.slider_row('Opacity', 'Lower values let the wallpaper show through', barlayout.OPACITY_MIN, barlayout.OPACITY_MAX, 0.05,
                                barlayout.opacity(s), lambda v: debounced('bar_opacity', round(float(v), 2)), digits=2)
        body.append(ui.section('Size and look', height, opacity))

        resets = Gtk.Box(spacing=10)
        resets.append(ui.button('Reset to default', lambda: reset('classic')))
        resets.append(ui.button('Use the Home layout', lambda: reset('home')))
        body.append(ui.section('Presets', ui.row('Start over', 'Default is the classic bar; Home adds a Home button and centres the clock', resets)))
        preview()

    def reset(name):
        save(bar_layout=barlayout.preset(name), bar_preset=name, bar_clock_format=dict(barlayout.CLOCK_DEFAULTS), bar_height=barlayout.HEIGHT_DEFAULT, bar_opacity=1.0)
        render()

    box.render = render
    render()
    return box
