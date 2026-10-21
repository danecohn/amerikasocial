"""Text clipboard history. Memory only, bounded, password hints excluded.

Wayland background monitoring needs wl-clipboard's data-control support. If the
compositor does not expose it, GDK continues tracking while this client has focus.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from gi.repository import Gdk, GLib, Gtk
from .. import deskconf
from . import dutil,layer

PASSWORD_HINTS=('x-kde-passwordManagerHint','application/x-kde-passwordManagerHint')


class History:
    def __init__(self,limit=50,max_bytes=1<<20):
        self.limit=max(1,min(100,limit));self.max_bytes=max(1,min(1<<20,max_bytes));self.items=[]
    def add(self,text,sensitive=False):
        if sensitive or not isinstance(text,str) or not text.strip() or len(text.encode())>self.max_bytes:return False
        if self.items and self.items[0]==text:return False
        self.items=[text]+[item for item in self.items if item!=text]
        del self.items[self.limit:]
        # Limit total memory as well as individual values.
        while sum(len(item.encode()) for item in self.items)>8<<20:self.items.pop()
        return True
    def clear(self):self.items.clear()


class Clipboard(Gtk.Window):
    def __init__(self,shell):
        super().__init__(application=shell,title='Clipboard history')
        self.shell=shell;self.process=None;self._closed=False
        cfg=deskconf.get('clipboard',shell.settings)
        self.enabled=cfg.get('enabled',True)
        self.history=History(cfg.get('max_items',50),cfg.get('max_item_bytes',1<<20))
        self.clipboard=Gdk.Display.get_default().get_clipboard()
        self.clipboard.connect('changed',self._changed)
        self.add_css_class('am-overlay-clear')
        layer.setup(self,'overlay',keyboard='exclusive',namespace='amerika-clipboard')
        self.set_default_size(620,520)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);box.add_css_class('am-popup-panel');self.set_child(box)
        box.append(dutil.label('CLIPBOARD HISTORY','am-heading'))
        box.append(dutil.label('Text stays in memory for this session. Password-manager hints are skipped.','am-sub',wrap=True))
        clear=Gtk.Button(label='Clear history');clear.connect('clicked',lambda *_:(self.history.clear(),self.render()));box.append(clear)
        sc=Gtk.ScrolledWindow(vexpand=True);self.list=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);sc.set_child(self.list);box.append(sc)
        self.connect('close-request',lambda *_:(self.hide(),True)[1])
        ctl=Gtk.EventControllerKey();ctl.connect('key-pressed',lambda _,key,*a:(self.hide(),True)[1] if key==Gdk.KEY_Escape else False);self.add_controller(ctl)
        if self.enabled:self._watch()

    def _watch(self):
        if not shutil.which('wl-paste'):return
        env=dict(os.environ);env.pop('LD_PRELOAD',None)
        try:
            self.process=subprocess.Popen(['wl-paste','--type','text','--watch',sys.executable,'-m','amerika.shell.clipboard',
                                           '--watch-event'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env,start_new_session=True)
        except OSError:return
        def read():
            for line in self.process.stdout:
                if self._closed:break
                try:text=json.loads(line)
                except ValueError:continue
                GLib.idle_add(self._receive,text)
        threading.Thread(target=read,daemon=True).start()

    def _receive(self,text):
        if self.enabled and not self._closed and self.history.add(text) and self.get_visible():self.render()
        return False

    def _changed(self,clipboard):
        if not self.enabled:return
        formats=clipboard.get_formats()
        if any(formats.contain_mime_type(hint) for hint in PASSWORD_HINTS):return
        def ready(cb,result):
            try:self._receive(cb.read_text_finish(result))
            except GLib.Error:pass
        clipboard.read_text_async(None,ready)

    def render(self):
        dutil.clear(self.list)
        for text in self.history.items:
            preview=' '.join(text.split())[:180]
            button=Gtk.Button();button.set_child(dutil.label(preview,wrap=True))
            button.connect('clicked',lambda _,value=text:(self.clipboard.set(value),self.hide()))
            self.list.append(button)
        if not self.history.items:self.list.append(dutil.label('Copy some text to begin.','am-sub'))

    def toggle(self):
        if self.get_visible():self.hide()
        else:self.render();self.present()

    def close_service(self):
        self._closed=True;self.history.clear()
        if self.process and self.process.poll() is None:
            try:os.killpg(self.process.pid,signal.SIGTERM)
            except ProcessLookupError:pass


def watch_event():
    # wl-paste gives us a pipe for this event, not a file or an argv value.
    if os.environ.get('CLIPBOARD_STATE') in ('sensitive','clear','nil'):return
    try:
        result=subprocess.run(['wl-paste','--list-types'],capture_output=True,text=True,timeout=2)
        if result.returncode or any(hint in result.stdout.splitlines() for hint in PASSWORD_HINTS):return
        raw=sys.stdin.buffer.read((1<<20)+1)
        if len(raw)>1<<20:return
        text=raw.decode('utf-8')
        if text.strip():print(json.dumps(text),flush=True)
    except (OSError,UnicodeError,subprocess.TimeoutExpired):pass


if __name__=='__main__' and '--watch-event' in sys.argv:watch_event()
