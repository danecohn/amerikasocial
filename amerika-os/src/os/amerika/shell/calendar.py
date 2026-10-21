"""Local calendar, world clocks and an in-session countdown timer."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import time
from gi.repository import GLib, Gtk
from .. import deskconf
from . import dutil, layer


def world_times(zones,now=None):
    result=[]
    for name in zones[:12]:
        try:result.append((name,datetime.fromtimestamp(now or time.time(),ZoneInfo(name)).strftime('%a %H:%M')))
        except (ZoneInfoNotFoundError,ValueError,TypeError):continue
    return result


class Calendar(Gtk.Window):
    def __init__(self,shell):
        super().__init__(application=shell,title='Calendar & clocks')
        self.shell=shell;self.timer=0;self.deadline=0
        self.add_css_class('am-overlay-clear')
        layer.setup(self,'overlay',anchors=('top',),margins={'top':48},keyboard='on_demand',namespace='amerika-calendar')
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.add_css_class('am-popup-panel');self.set_child(box)
        box.append(dutil.label('CALENDAR & CLOCKS','am-heading'))
        self.calendar=Gtk.Calendar();box.append(self.calendar)
        self.clocks=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);box.append(self.clocks)
        row=Gtk.Box(spacing=8)
        self.minutes=Gtk.SpinButton.new_with_range(1,1440,1);self.minutes.set_value(5)
        row.append(self.minutes);row.append(dutil.label('minutes'))
        start=Gtk.Button(label='Start timer');start.connect('clicked',lambda *_:self.start_timer(self.minutes.get_value_as_int()*60));row.append(start)
        cancel=Gtk.Button(label='Cancel timer');cancel.connect('clicked',lambda *_:self.cancel_timer());row.append(cancel)
        box.append(row);self.countdown=dutil.label('');box.append(self.countdown)
        self.connect('close-request',lambda *_:(self.hide(),True)[1])
        ctl=Gtk.EventControllerKey();ctl.connect('key-pressed',lambda _,key,*a:(self.hide(),True)[1] if key==65307 else False);self.add_controller(ctl)

    def toggle(self):
        if self.get_visible():self.hide();return
        dutil.clear(self.clocks)
        for name,value in world_times(deskconf.get('world_clocks',self.shell.settings)):
            self.clocks.append(dutil.label(name+' · '+value,'am-mono'))
        self.present()

    def start_timer(self,seconds):
        self.cancel_timer();self.deadline=time.monotonic()+seconds
        self.timer=GLib.timeout_add_seconds(1,self._tick);self._tick()

    def cancel_timer(self):
        if self.timer:GLib.source_remove(self.timer)
        self.timer=0;self.deadline=0;self.countdown.set_text('')

    def _tick(self):
        left=max(0,round(self.deadline-time.monotonic()))
        self.countdown.set_text(f'{left//60:02}:{left%60:02}')
        if left:return True
        self.timer=0;self.shell.notifications.notify('Amerika timer',0,'alarm-symbolic','Timer finished','Your countdown is complete.')
        return False
