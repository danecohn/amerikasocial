"""Hardware-key actions on workers, with a short, noninteractive on-screen display."""
from gi.repository import GLib,Gtk
from .. import common,deskconf,system,sysutil
from . import dutil,layer,screenshot


class OSD(Gtk.Window):
    def __init__(self,shell):
        super().__init__(application=shell,title='Hardware status')
        self.shell=shell;self.timer=0
        self.add_css_class('am-overlay-clear')
        layer.setup(self,'overlay',anchors=('bottom',),margins={'bottom':120},keyboard='none',namespace='amerika-osd')
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);box.add_css_class('am-popup-panel');box.set_size_request(280,-1)
        self.title=dutil.label('','am-heading',.5);self.level=Gtk.ProgressBar();box.append(self.title);box.append(self.level);self.set_child(box)

    def show_value(self,title,percent=None):
        if not deskconf.get('osd.enabled',self.shell.settings):return
        self.title.set_text(title);self.level.set_visible(percent is not None)
        if percent is not None:self.level.set_fraction(max(0,min(1,percent/100)))
        self.present()
        if self.timer:GLib.source_remove(self.timer)
        def hide():self.timer=0;self.hide();return False
        self.timer=GLib.timeout_add(deskconf.get('osd.timeout_ms',self.shell.settings),hide)

    def action(self,name):
        def work():
            if name.startswith('volume-'):
                value=system.volume() or {'percent':0,'muted':False}
                if name=='volume-mute':
                    ok=system.set_mute(not value['muted']);return ('Muted' if not value['muted'] else 'Sound on'),None
                percent=max(0,min(100,value['percent']+(5 if name=='volume-up' else -5)))
                system.set_volume(percent);return f'Volume {percent}%',percent
            if name=='mic-mute':
                result=sysutil.run(['wpctl','set-mute','@DEFAULT_AUDIO_SOURCE@','toggle'])
                return ('Microphone mute toggled' if not result.code else 'Microphone unavailable'),None
            if name.startswith('brightness-'):
                value=system.brightness()
                if value:
                    percent=max(1,min(100,value['percent']+(5 if name.endswith('up') else -5)))
                    system.set_brightness(percent);return f'Brightness {percent}%',percent
                return 'Brightness unavailable',None
            if name.startswith('kbd-'):
                result=sysutil.run(['brightnessctl','--device=*::kbd_backlight','set','5%+' if name.endswith('up') else '5%-'])
                return ('Keyboard brightness' if not result.code else 'Keyboard backlight unavailable'),None
            return 'Unavailable',None
        screenshot.run_async(work,lambda result,error:self.show_value(*(result if not error else ('Unavailable',None))))
