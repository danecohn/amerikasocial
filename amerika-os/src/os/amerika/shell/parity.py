"""Lifecycle and action routing for Amerika's everyday desktop surfaces."""
from .. import deskconf
from . import media,screenshot,workspaces
from .calendar import Calendar
from .clipboard import Clipboard
from .osd import OSD
from .switcher import WindowPicker


class DesktopServices:
    def __init__(self,shell):
        self.shell=shell
        self.desktops=workspaces.DesktopManager()
        self.screenshots=screenshot.ScreenshotService(shell)
        self.thumbnails=self.screenshots.thumbs
        self.switcher=WindowPicker(shell)
        self.overview=WindowPicker(shell,overview=True)
        self.clipboard=Clipboard(shell)
        self.calendar=Calendar(shell)
        self.osd=OSD(shell)
        shell.windows.connect('changed',self._windows_changed)

    def _windows_changed(self,*args):
        self.thumbnails.forget({w['id'] for w in self.shell.windows.app_windows()})

    def action(self,name):
        if name.startswith(('corner:','touch:')):
            kind,key=name.split(':',1)
            name=deskconf.get(('hot_corners.' if kind=='corner' else 'touch_edges.')+key,self.shell.settings,'none')
            if name=='none':return True
            if name=='launcher':self.shell.toggle_launcher();return True
            if name=='lock':self.shell.action('lock');return True
        if name=='overview':
            if self.overview.get_visible():self.overview.hide()
            else:self.overview.open()
        elif name=='switcher' or name.startswith('switcher:'):
            self.switcher.open(-1 if name.endswith('prev') else 1,app_only=name.endswith('app-next'))
        elif name=='clipboard':self.clipboard.toggle()
        elif name=='calendar':self.calendar.toggle()
        elif name=='screenshot' or name.startswith('screenshot:'):
            self.screenshots.start(name.split(':',1)[1] if ':' in name else 'region')
        elif name=='record:toggle':self.screenshots.toggle_recording()
        elif name.startswith('osd:'):self.osd.action(name.split(':',1)[1])
        elif name.startswith('media:'):
            screenshot.run_async(lambda:media.control(name.split(':',1)[1]),lambda result,error:None)
        elif name=='show-desktop':workspaces.show_desktop(self.shell.windows)
        elif name in ('next-desktop','previous-desktop'):
            items=workspaces.desktops_of(self.shell.windows.state)
            if items:
                index=next((i for i,d in enumerate(items) if d['current']),0)
                self.desktops.switch_to(items[(index+(1 if name=='next-desktop' else -1))%len(items)]['n'])
        else:return False
        return True

    def close(self):
        self.clipboard.close_service();self.calendar.cancel_timer()
        self.screenshots.recorder.stop()
        for win in (self.switcher,self.overview,self.clipboard,self.calendar,self.osd):win.destroy()
