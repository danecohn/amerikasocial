import sys
import gi
gi.require_version('Gtk','4.0')
from .apps import Applications
from .catalog import BY_ID
name=sys.argv[1] if len(sys.argv)>1 else 'files'
if name not in BY_ID:
    sys.exit('Unknown MakOS application')
if name in ('seek','spread','desktops','widgets','screenshot'):
    from gi.repository import Gio,GLib
    try:
        bus=Gio.bus_get_sync(Gio.BusType.SESSION)
        bus.call_sync('org.makos.Shell','/Control','org.makos.Control','Action',GLib.Variant('(s)',(name,)),None,Gio.DBusCallFlags.NONE,3000,None)
    except GLib.Error:
        sys.exit('Start the MakOS session to use this application.')
    sys.exit(0)
path=sys.argv[2] if len(sys.argv)>2 else None
if path and path.startswith('file://'):
    from gi.repository import Gio
    path=Gio.File.new_for_uri(path).get_path()
sys.exit(Applications(name,path).run([sys.argv[0]]))
