"""The Caster: a full-screen overlay (opened by the Copilot key) with two large cards, Claude and ChatGPT.

`CasterState` is the pure state machine (unit tested); `Caster` is the layer-shell overlay that draws it.
"""
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gsk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk  # noqa: E402

from . import apps, home, layer

CARDS = ('claude', 'chatgpt')
OPEN_MS, CLOSE_MS, FOCUS_MS = 220, 140, 160
FOCUS_SCALE, REST_SCALE = 1.045, 0.97


# ---------------------------------------------------------------- pure logic
def ago(then, now=None):
    """'never opened', 'just now', '12 min ago', '3 h ago', '2 days ago'."""
    if not then:
        return 'never opened'
    secs = max(0, int((now if now is not None else time.time()) - float(then)))
    if secs < 60:
        return 'just now'
    if secs < 3600:
        return '%d min ago' % (secs // 60)
    if secs < 86400:
        return '%d h ago' % (secs // 3600)
    days = secs // 86400
    return '%d day%s ago' % (days, '' if days == 1 else 's')


class CasterState:
    """Which card has focus and what a key press does. Returns an action tuple, never touches the UI.

    actions: ('focus', index) | ('choose', key) | ('close',) | None
    """

    def __init__(self, cards=CARDS, initial=None):
        self.cards = tuple(cards)
        self.visible = False
        self.index = self._index_of(initial)

    def _index_of(self, key):
        return self.cards.index(key) if key in self.cards else 0

    @property
    def focused(self):
        return self.cards[self.index]

    def open(self, last=None):
        self.visible = True
        self.index = self._index_of(last)
        return ('focus', self.index)

    def close(self):
        self.visible = False
        return ('close',)

    def move(self, delta):
        self.index = (self.index + delta) % len(self.cards)
        return ('focus', self.index)

    def pick(self, number):
        """Quick pick by 1-based number."""
        if 1 <= number <= len(self.cards):
            self.index = number - 1
            return ('choose', self.cards[self.index])
        return None

    def copilot_again(self):
        """The Copilot key pressed while the Caster is open cycles to the other card."""
        return self.move(1)

    def key(self, name):
        if not self.visible:
            return None
        if name in ('Right', 'Tab', 'Down'):
            return self.move(1)
        if name in ('Left', 'ISO_Left_Tab', 'Up'):
            return self.move(-1)
        if name in ('Return', 'KP_Enter', 'space'):
            return ('choose', self.focused)
        if name == 'Escape':
            return self.close()
        if name.isdigit():
            return self.pick(int(name))
        return None


def ease_out(p):
    return 1 - (1 - p) ** 3


# ---------------------------------------------------------------- widgets
class ScaleBin(Gtk.Widget):
    """A single-child container that draws (and hit-tests) its child scaled around the centre."""
    __gtype_name__ = 'AmerikaScaleBin'

    def __init__(self):
        super().__init__()
        self._child = None
        self._scale = 1.0
        self.set_overflow(Gtk.Overflow.VISIBLE)

    def set_child(self, child):
        self._child = child
        child.set_parent(self)

    def get_scale(self):
        return self._scale

    def set_scale(self, value):
        if abs(value - self._scale) > 1e-4:
            self._scale = value
            self.queue_allocate()

    def do_measure(self, orientation, for_size):
        if self._child is None:
            return 0, 0, -1, -1
        return self._child.measure(orientation, for_size)

    def do_size_allocate(self, width, height, baseline):
        if self._child is None:
            return
        c = Graphene.Point()
        t = Gsk.Transform()
        t = t.translate(c.init(width / 2.0, height / 2.0))
        t = t.scale(self._scale, self._scale)
        t = t.translate(c.init(-width / 2.0, -height / 2.0))
        self._child.allocate(width, height, baseline, t)

    def do_dispose(self):
        if self._child is not None:
            self._child.unparent()
            self._child = None
        Gtk.Widget.do_dispose(self)


class Caster(Gtk.Window):
    def __init__(self, shell):
        super().__init__(application=shell, title='Amerika Caster')
        self.shell = shell
        self.state = CasterState()
        self.add_css_class('am-caster')
        layer.setup(self, 'overlay', anchors=('top', 'bottom', 'left', 'right'), exclusive=-1, keyboard='exclusive',
                    namespace='amerika-caster')
        self._tick = 0
        self._closing = False
        self.cards = {}

        self.stage = ScaleBin()
        self.stage.set_hexpand(True)
        self.stage.set_vexpand(True)
        self.set_child(self.stage)
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=26, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.stage.set_child(self.root)

        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        t = Gtk.Label(label='CASTER')
        t.add_css_class('am-caster-title')
        head.append(t)
        s = Gtk.Label(label='CHOOSE YOUR AI')
        s.add_css_class('am-caster-sub')
        head.append(s)
        self.root.append(head)

        self.row = Gtk.Box(spacing=36, halign=Gtk.Align.CENTER)
        self.root.append(self.row)
        hint = Gtk.Label(label='LEFT / RIGHT / TAB  CHOOSE     ENTER  OPEN     1  2  QUICK PICK     ESC  CLOSE     COPILOT KEY  NEXT')
        hint.add_css_class('am-caster-hint')
        self.root.append(hint)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect('key-pressed', self._on_key)
        self.add_controller(keys)
        outside = Gtk.GestureClick()
        outside.connect('pressed', self._on_outside)
        self.stage.add_controller(outside)
        self.connect('notify::visible', lambda *_: self._visibility())

    # ----- opening and closing
    def info(self, key):
        """Facts shown on one card (also used by the tests and the rig)."""
        app = home.APPS[key]
        desktop = apps.lookup(app['id'])
        wins = home.home_windows(self.shell.windows.app_windows(), self.shell.settings, key) if self.shell.windows else []
        used = (self.shell.settings.get('app_last_used') or {}).get(key)
        return {'key': key, 'name': app['name'], 'desktop': desktop, 'running': bool(wins), 'installed': desktop is not None,
                'last_used': ago(used), 'is_home': home.home_key(self.shell.settings) == key}

    def toggle(self):
        """The Copilot key: open, or (when already open) move to the other card."""
        if self.get_visible() and self.state.visible and not self._closing:
            self._apply(self.state.copilot_again())
        else:
            self.open()

    def open(self):
        self._closing = False
        self._build_cards()
        self.state.open(self.shell.settings.get('caster_last'))
        self.root.set_opacity(0.0)
        self.stage.set_scale(0.94)
        for key, c in self.cards.items():
            self._set_focus_look(key, key == self.state.focused, animate=False)
        if self.get_visible():
            self.present()
        else:
            self.present()
        self._animate(OPEN_MS, lambda p: (self.root.set_opacity(p), self.stage.set_scale(0.94 + 0.06 * p)))

    def close(self, animate=True):
        if not self.get_visible() or self._closing:
            return
        self._closing = True
        self.state.close()
        if not animate:
            self._finish_close()
            return
        self._animate(CLOSE_MS, lambda p: (self.root.set_opacity(1 - p), self.stage.set_scale(1.0 - 0.04 * p)), self._finish_close)

    def _finish_close(self):
        self.hide()
        self._closing = False
        self.stage.set_scale(1.0)

    def _visibility(self):
        if not self.get_visible():
            self.state.visible = False

    # ----- cards
    def _build_cards(self):
        child = self.row.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.row.remove(child)
            child = nxt
        self.cards = {}
        for n, key in enumerate(self.state.cards, start=1):
            facts = self.info(key)
            frame = ScaleBin()
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER)
            card.add_css_class('am-caster-card')
            card.add_css_class(key)
            card.set_size_request(330, 430)
            badge = Gtk.Label(label=str(n), halign=Gtk.Align.START)
            badge.add_css_class('am-caster-badge')
            card.append(badge)
            icon = apps.icon_image(facts['desktop'] or 'amerika-ai', 128)
            icon.set_halign(Gtk.Align.CENTER)
            icon.set_vexpand(True)
            icon.set_valign(Gtk.Align.CENTER)
            card.append(icon)
            name = Gtk.Label(label=facts['name'].upper())
            name.add_css_class('am-caster-name')
            card.append(name)
            if not facts['installed']:
                state_text, css = 'NOT INSTALLED', 'off'
            elif facts['running']:
                state_text, css = 'RUNNING', 'on'
            else:
                state_text, css = 'NOT RUNNING', 'off'
            pill = Gtk.Label(label=state_text, halign=Gtk.Align.CENTER)
            pill.add_css_class('am-pill')
            pill.add_css_class(css)
            card.append(pill)
            last = Gtk.Label(label=('Last used ' + facts['last_used']) if facts['last_used'] != 'never opened' else 'Never opened')
            last.add_css_class('am-sub')
            card.append(last)
            action = Gtk.Label(label=('OPEN' if facts['running'] else 'LAUNCH') + ('  ·  HOME' if facts['is_home'] else ''))
            action.add_css_class('am-caster-action')
            card.append(action)
            frame.set_child(card)
            click = Gtk.GestureClick()
            click.connect('released', lambda g, n_press, x, y, k=key: self.choose(k))
            card.add_controller(click)
            motion = Gtk.EventControllerMotion()
            motion.connect('enter', lambda c, x, y, k=key: self._hover(k))
            card.add_controller(motion)
            self.row.append(frame)
            self.cards[key] = (frame, card)

    def _hover(self, key):
        if not self.state.visible or self.state.focused == key:
            return
        self.state.index = self.state.cards.index(key)
        self._apply(('focus', self.state.index))

    def _set_focus_look(self, key, focused, animate=True):
        frame, card = self.cards[key]
        if focused:
            card.add_css_class('focused')
        else:
            card.remove_css_class('focused')
        target = FOCUS_SCALE if focused else REST_SCALE
        if not animate:
            frame.set_scale(target)
            return
        start = frame.get_scale()
        self._tween(frame, start, target)

    def _tween(self, frame, start, target):
        """Animate one card's scale; independent of the open/close animation."""
        t0 = [None]

        def tick(widget, clock):
            now = clock.get_frame_time() / 1000.0
            if t0[0] is None:
                t0[0] = now
            p = min(1.0, (now - t0[0]) / FOCUS_MS)
            frame.set_scale(start + (target - start) * ease_out(p))
            return GLib.SOURCE_CONTINUE if p < 1.0 else GLib.SOURCE_REMOVE
        frame.add_tick_callback(tick)

    def _animate(self, ms, update, done=None):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0
        t0 = [None]

        def tick(widget, clock):
            now = clock.get_frame_time() / 1000.0
            if t0[0] is None:
                t0[0] = now
            p = min(1.0, (now - t0[0]) / ms)
            update(ease_out(p))
            if p >= 1.0:
                self._tick = 0
                if done:
                    done()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        self._tick = self.add_tick_callback(tick)

    # ----- input
    def _apply(self, action):
        if not action:
            return False
        if action[0] == 'focus':
            for key in self.cards:
                self._set_focus_look(key, key == self.state.focused)
        elif action[0] == 'choose':
            self.choose(action[1])
        elif action[0] == 'close':
            self.state.visible = True      # close() returns early otherwise
            self.close()
        return True

    def _on_key(self, _c, keyval, _code, state):
        name = Gdk.keyval_name(keyval) or ''
        if state & Gdk.ModifierType.SHIFT_MASK and name == 'Tab':
            name = 'ISO_Left_Tab'
        return self._apply(self.state.key(name))

    def press(self, name):
        """Feed a key name to the overlay (the rig and the Control interface use this instead of synthetic input)."""
        return self._apply(self.state.key(name))

    def _on_outside(self, gesture, n_press, x, y):
        picked = self.stage.pick(x, y, Gtk.PickFlags.DEFAULT)
        for frame, card in self.cards.values():
            if picked is not None and (picked is card or picked.is_ancestor(card)):
                return
        self.close()

    def choose(self, key):
        if key not in home.APPS or self._closing:
            return
        self.state.visible = True
        self.close()
        self.shell.choose_home(key)
