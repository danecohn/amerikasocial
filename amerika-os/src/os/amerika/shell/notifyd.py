"""Notification daemon (org.freedesktop.Notifications) with toasts and a history popover."""
import time

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, GObject, Gtk  # noqa: E402

from . import layer
from .. import notifprefs

XML = '''<node><interface name="org.freedesktop.Notifications">
 <method name="GetCapabilities"><arg type="as" direction="out"/></method>
 <method name="Notify">
  <arg type="s" name="app_name" direction="in"/><arg type="u" name="replaces_id" direction="in"/><arg type="s" name="app_icon" direction="in"/>
  <arg type="s" name="summary" direction="in"/><arg type="s" name="body" direction="in"/><arg type="as" name="actions" direction="in"/>
  <arg type="a{sv}" name="hints" direction="in"/><arg type="i" name="expire_timeout" direction="in"/><arg type="u" direction="out"/>
 </method>
 <method name="CloseNotification"><arg type="u" name="id" direction="in"/></method>
 <method name="GetServerInformation"><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method>
 <signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
 <signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
</interface></node>'''


class Notifications(GObject.Object):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.dnd = notifprefs.load()['dnd']
        self.history = []  # newest first: dicts
        self._next = 1
        self._action_handlers = {}
        self._toasts = {}
        self._conn = None
        self._popover_list = None

    # ------------------------------------------------------------------ bus
    def start(self):
        Gio.bus_own_name(Gio.BusType.SESSION, 'org.freedesktop.Notifications', Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                         self._on_bus, None, lambda *_: print('notification name lost', flush=True))

    def _on_bus(self, conn, name):
        self._conn = conn
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        conn.register_object('/org/freedesktop/Notifications', info.interfaces[0], self._on_call, None, None)

    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        if method == 'GetCapabilities':
            invocation.return_value(GLib.Variant('(as)', (['body', 'actions', 'icon-static', 'persistence'],)))
        elif method == 'GetServerInformation':
            invocation.return_value(GLib.Variant('(ssss)', ('Amerika Shell', 'Amerika LLC', '3.0', '1.2')))
        elif method == 'CloseNotification':
            self.close(params.unpack()[0], 3)
            invocation.return_value(None)
        elif method == 'Notify':
            app, replaces, icon, summary, body, actions, hints, timeout = params.unpack()
            nid = self.notify(app, replaces, icon, summary, body, actions, hints, timeout)
            invocation.return_value(GLib.Variant('(u)', (nid,)))

    # ------------------------------------------------------------------ model
    def notify(self, app, replaces, icon, summary, body, actions=(), hints=None, timeout=-1, ai=False, on_action=None):
        hints = hints or {}
        nid = replaces if replaces and replaces in {h['id'] for h in self.history} else self._next
        if nid == self._next:
            self._next += 1
        entry = {'id': nid, 'app': app, 'icon': icon, 'summary': summary, 'body': body, 'time': time.time(), 'ai': ai,
                 'actions': list(actions), 'urgency': int(hints.get('urgency', 1))}
        if on_action:self._action_handlers[nid]=on_action
        else:self._action_handlers.pop(nid,None)
        self.history = [h for h in self.history if h['id'] != nid]
        self.history.insert(0, entry)
        del self.history[200:]
        alive={h['id'] for h in self.history}
        self._action_handlers={k:v for k,v in self._action_handlers.items() if k in alive}
        self._refresh_popover()
        notifprefs.record_seen(app)
        if notifprefs.allows(app,entry['urgency'],manual_dnd=self.dnd):
            self._toast(entry, timeout)
        return nid

    def close(self, nid, reason=3):
        toast = self._toasts.pop(nid, None)
        if toast:
            toast.destroy()
        if self._conn:
            self._conn.emit_signal(None, '/org/freedesktop/Notifications', 'org.freedesktop.Notifications', 'NotificationClosed',
                                   GLib.Variant('(uu)', (nid, reason)))

    def set_dnd(self, on):
        self.dnd = bool(on)
        notifprefs.set_dnd(self.dnd)

    def clear(self):
        self.history.clear()
        self._action_handlers.clear()
        self._refresh_popover()

    # ------------------------------------------------------------------ toast windows
    def _toast(self, entry, timeout):
        win = Gtk.Window(application=self.shell, title='Notification')
        win.add_css_class('am-overlay-clear')
        layer.setup(win, 'overlay', anchors=('top', 'right'), margins={'top': 46 + 12 * len(self._toasts) + 84 * len(self._toasts), 'right': 14},
                    namespace='amerika-toast')
        box = Gtk.Box(spacing=12)
        box.add_css_class('am-toast')
        if entry['ai']:
            box.add_css_class('ai')
        box.set_size_request(340, -1)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
        t = Gtk.Label(label=entry['summary'], xalign=0, wrap=True)
        t.add_css_class('am-toast-title')
        b = Gtk.Label(label=entry['body'], xalign=0, wrap=True, max_width_chars=44)
        b.add_css_class('am-toast-body')
        col.append(t)
        if entry['body']:
            col.append(b)
        self._add_actions(col,entry)
        box.append(col)
        close = Gtk.Button(icon_name='amerika-close-symbolic', valign=Gtk.Align.START)
        close.add_css_class('am-bar-icon')
        close.connect('clicked', lambda *_: self.close(entry['id'], 2))
        box.append(close)
        win.set_child(box)
        win.present()
        self._toasts[entry['id']] = win
        ms = timeout if timeout and timeout > 0 else 6500
        GLib.timeout_add(ms, lambda: (self.close(entry['id'], 1) if entry['id'] in self._toasts else None, False)[1])

    # ------------------------------------------------------------------ history popover (bar bell)
    def center_popover(self):
        pop = Gtk.Popover()
        pop.add_css_class('am-panel')
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for m in ('top', 'bottom', 'start', 'end'):
            getattr(col, f'set_margin_{m}')(12)
        head = Gtk.Box(spacing=8)
        title = Gtk.Label(label='NOTIFICATIONS', xalign=0, hexpand=True)
        title.add_css_class('am-label')
        head.append(title)
        clear = Gtk.Button(label='Clear')
        clear.add_css_class('am-secondary')
        clear.connect('clicked', lambda *_: self.clear())
        head.append(clear)
        col.append(head)
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(80)
        scroller.set_max_content_height(420)
        scroller.set_propagate_natural_height(True)
        scroller.set_size_request(360, -1)
        self._popover_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroller.set_child(self._popover_list)
        col.append(scroller)
        pop.set_child(col)
        self._refresh_popover()
        return pop

    def _refresh_popover(self):
        box = self._popover_list
        if box is None:
            return
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        if not self.history:
            empty = Gtk.Label(label='Nothing new.', xalign=0)
            empty.add_css_class('am-sub')
            box.append(empty)
        for h in self.history[:40]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.add_css_class('am-card')
            t = Gtk.Label(label=h['summary'], xalign=0, wrap=True)
            t.add_css_class('am-toast-title')
            card.append(t)
            if h['body']:
                b = Gtk.Label(label=h['body'], xalign=0, wrap=True, max_width_chars=44)
                b.add_css_class('am-toast-body')
                card.append(b)
            meta = Gtk.Label(label=f"{h['app'] or 'system'} · {time.strftime('%H:%M', time.localtime(h['time']))}", xalign=0)
            meta.add_css_class('am-label')
            card.append(meta)
            self._add_actions(card,h)
            box.append(card)


    def _add_actions(self,box,entry):
        actions=entry.get('actions',[])
        if len(actions)<2:return
        buttons=Gtk.Box(spacing=6)
        for i in range(0,min(len(actions)-1,20),2):
            key,title=actions[i:i+2]
            if key=='default':continue
            button=Gtk.Button(label=title)
            button.add_css_class('am-secondary')
            button.connect('clicked',lambda _,nid=entry['id'],action=key:self.invoke_action(nid,action))
            buttons.append(button)
        box.append(buttons)

    def invoke_action(self,nid,action):
        handler=self._action_handlers.get(nid)
        if handler:handler(action)
        elif self._conn:
            self._conn.emit_signal(None,'/org/freedesktop/Notifications','org.freedesktop.Notifications','ActionInvoked',
                                   GLib.Variant('(us)',(nid,action)))
        self.close(nid,2)
