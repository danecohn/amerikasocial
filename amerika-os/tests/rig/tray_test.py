"""Exercise the real GTK shell and tray against a private fake application.

Run through tools/kwin-rig.sh tests/rig/tray_test.sh, never on the user's bus.
"""
import os
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk
from amerika.shell.app import Shell, save_widget
from amerika.shell.tray import ITEM, MENU, WATCHER, WATCH_PATH, Tray, call


def spin(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Timed out: ' + str(predicate))


def remote(conn, bus, path, iface, method, params=None, fail=False):
    answer = []
    call(conn, bus, path, iface, method, params, lambda value, error: answer.append((value, error)))
    spin(lambda: answer)
    value, error = answer[0]
    assert bool(error) == fail, (method, error)
    return value.unpack() if value else None


def connection():
    return Gio.DBusConnection.new_for_address_sync(os.environ['DBUS_SESSION_BUS_ADDRESS'],
              Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)


ITEM_XML = '''<node><interface name="org.kde.StatusNotifierItem">
 <property name="Id" type="s" access="read"/>
 <property name="Title" type="s" access="read"/>
 <property name="Status" type="s" access="read"/>
 <property name="IconName" type="s" access="read"/>
 <property name="IconPixmap" type="a(iiay)" access="read"/>
 <property name="AttentionIconName" type="s" access="read"/>
 <property name="ItemIsMenu" type="b" access="read"/>
 <property name="Menu" type="o" access="read"/>
 <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
 <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
 <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
 <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
 <signal name="NewStatus"><arg type="s"/></signal>
 <signal name="NewIcon"/>
</interface></node>'''
MENU_XML = '''<node><interface name="com.canonical.dbusmenu">
 <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
 <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
 <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
 <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
 <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
</interface></node>'''


def node(ident, props, children=()):
    return GLib.Variant('(ia{sv}av)', (ident, {key: GLib.Variant('b' if isinstance(value, bool) else
                        'i' if isinstance(value, int) else 's', value) for key, value in props.items()}, list(children)))


class App:
    def __init__(self):
        self.conn = connection()
        self.events = []
        self.props = {'Id': GLib.Variant('s', 'test'), 'Title': GLib.Variant('s', 'Tray Test'),
                      'Status': GLib.Variant('s', 'Active'), 'IconName': GLib.Variant('s', 'folder'),
                      'IconPixmap': GLib.Variant('a(iiay)', []),
                      'AttentionIconName': GLib.Variant('s', 'dialog-warning-symbolic'),
                      'ItemIsMenu': GLib.Variant('b', False), 'Menu': GLib.Variant('o', '/Menu'),
                      'ToolTip': GLib.Variant('(sa(iiay)ss)', ('', [], 'Tray test', 'Private rig application'))}
        for path in ('/StatusNotifierItem', '/CustomTray'):
            self.conn.register_object(path, Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0], self.method,
                                      lambda _c, _s, _p, _i, name: self.props[name], None)
        self.conn.register_object('/Menu', Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0], self.method, None, None)
        self.label = '_Open'
        self.register('/CustomTray')

    def register(self, service, fail=False):
        remote(self.conn, WATCHER, WATCH_PATH, WATCHER, 'RegisterStatusNotifierItem',
               GLib.Variant('(s)', (service,)), fail)

    def method(self, _conn, _sender, _path, iface, method, params, invocation):
        self.events.append((method, params.unpack()))
        if method == 'AboutToShow':
            invocation.return_value(GLib.Variant('(b)', (False,)))
        elif method == 'GetLayout':
            parent = params.unpack()[0]
            children = [node(4, {'label': '_Nested action'})] if parent == 3 else [
                node(1, {'label': self.label}), node(2, {'label': 'Disabled', 'enabled': False}),
                node(3, {'label': 'Submenu', 'children-display': 'submenu'}),
                node(5, {'label': 'Hidden', 'visible': False}), node(6, {'type': 'separator'}),
                node(7, {'label': 'Checked', 'toggle-type': 'checkmark', 'toggle-state': 1})]
            invocation.return_value(GLib.Variant('(u(ia{sv}av))', (1, (parent, {}, children))))
        else:
            invocation.return_value(None)

    def change(self, name, value, signal='NewIcon'):
        self.props[name] = value
        self.conn.emit_signal(None, '/CustomTray', ITEM, signal,
                              GLib.Variant('(s)', (value.unpack(),)) if signal == 'NewStatus' else None)


shell = Shell()
assert shell.register(None)
shell.activate()
tray = shell.bar.tray
spin(lambda: tray.conn is not None)
spin(lambda: remote(tray.conn, WATCHER, WATCH_PATH, 'org.freedesktop.DBus.Properties', 'Get',
                    GLib.Variant('(ss)', (WATCHER, 'IsStatusNotifierHostRegistered')))[0])
app = App()
print('Registered fake tray app', flush=True)
key = app.conn.get_unique_name() + '/CustomTray'
spin(lambda: key in tray.items and tray.items[key].props)
item = tray.items[key]
assert item.get_visible() and item.get_tooltip_text() == 'Tray test\nPrivate rig application'
app.register('/CustomTray')
assert len(tray.items) == 1, 'Duplicate registration'
app.register('org.amerika.Shell', fail=True)
app.register('bad name', fail=True)
remote(app.conn, 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'RequestName',
       GLib.Variant('(su)', ('org.amerika.TrayTest', 0)))
app.register('org.amerika.TrayTest')
spin(lambda: len(tray.items) == 2)
remote(app.conn, 'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ReleaseName',
       GLib.Variant('(s)', ('org.amerika.TrayTest',)))
spin(lambda: len(tray.items) == 1)
print('Validated bus-name registration and removal', flush=True)
item.emit('clicked')
spin(lambda: ('Activate', (0, 0)) in app.events)
item._invoke('SecondaryActivate', GLib.Variant('(ii)', (0, 0)))
item._scroll(None, 0, 1)
spin(lambda: ('SecondaryActivate', (0, 0)) in app.events and ('Scroll', (-120, 'vertical')) in app.events)
app.change('Status', GLib.Variant('s', 'Passive'), 'NewStatus')
spin(lambda: not item.get_visible())
app.change('Status', GLib.Variant('s', 'NeedsAttention'), 'NewStatus')
spin(lambda: item.get_visible() and item.has_css_class('attention'))
app.change('Status', GLib.Variant('s', 'Active'), 'NewStatus')
app.change('IconName', GLib.Variant('s', ''))
app.change('IconPixmap', GLib.Variant('a(iiay)', [(64, 64, bytes([255, 255, 40, 100]) * 4096)]))
spin(lambda: item.image.get_paintable() is not None and item.image.get_paintable().__class__.__name__ == 'MemoryTexture')
app.change('ItemIsMenu', GLib.Variant('b', True))
spin(lambda: item.props.get('ItemIsMenu'))
print('Validated icon states and actions; opening menu', flush=True)
item.emit('clicked')


def menu_buttons():
    if not item.menu.pop.get_child():
        return []
    # Gtk.ScrolledWindow inserts a viewport around non-scrollable content.
    child = item.menu.pop.get_child().get_child()
    col = child.get_child() if isinstance(child, Gtk.Viewport) else child
    buttons = []
    button = col.get_first_child()
    while button:
        buttons.append(button)
        button = button.get_next_sibling()
    return buttons


spin(lambda: menu_buttons())
print('Menu opened', flush=True)
buttons = menu_buttons()
assert len(buttons) == 5 and not buttons[1].get_sensitive()
assert buttons[0].get_label() == 'Open' and buttons[-1].get_label() == '✓ Checked'
original_pop = item.menu.pop
app.label = '_Updated action'
app.conn.emit_signal(None, '/Menu', MENU, 'LayoutUpdated', GLib.Variant('(ui)', (2, 0)))
spin(lambda: menu_buttons()[0].get_label() == 'Updated action')
assert item.menu.pop is original_pop and original_pop.get_visible(), 'Menu disappeared on update'
menu_buttons()[2].emit('clicked')
spin(lambda: len(menu_buttons()) == 2)
menu_buttons()[1].emit('clicked')
spin(lambda: any(method == 'Event' and args[0] == 4 for method, args in app.events))
item.open_menu()
spin(lambda: len(menu_buttons()) == 5)
for attempt in range(6):
    events = sum(method == 'Event' for method, _args in app.events)
    menu_buttons()[0].emit('clicked')
    spin(lambda: sum(method == 'Event' for method, _args in app.events) > events)
    item.open_menu()
    spin(lambda: len(menu_buttons()) == 5)
# Let GTK draw before capturing both the integrated bar and its tray menu.
until = time.monotonic() + 1
spin(lambda: time.monotonic() >= until)
assert item.image.get_width() <= 24 and item.image.get_height() <= 24, 'Pixmap inflated the bar icon'
out = Path(os.environ['T'])
assert save_widget(shell.bar, out / 'tray-bar.png')
assert save_widget(item.menu.pop, out / 'tray-menu.png')
app.conn.close_sync(None)
spin(lambda: key not in tray.items)
assert remote(tray.conn, WATCHER, WATCH_PATH, 'org.freedesktop.DBus.Properties', 'Get',
              GLib.Variant('(ss)', (WATCHER, 'RegisteredStatusNotifierItems')))[0] == []
# A second host joins the existing watcher and sees already registered items.
app2 = App()
other = Tray()
other.start()
spin(lambda: other._external is not None and len(other.items) == 1)
assert len(tray.items) == 1
other.close()
app2.conn.close_sync(None)
spin(lambda: not tray.items)
tray.close()
print('PASS: registration, deduplication, caller ownership, icon updates, passive/attention, actions, scroll, menus, submenu, live menu update, disconnect and second host', flush=True)
print('Screenshots:', out / 'tray-bar.png', out / 'tray-menu.png', flush=True)
