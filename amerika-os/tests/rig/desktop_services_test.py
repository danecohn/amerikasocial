"""Real shell, compositor windows and desktop surfaces; no live session/device changes."""
import os,time
from pathlib import Path
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import GLib,Gtk
from amerika.shell.app import Shell,save_widget
from amerika.shell import screenshot


def spin(check,timeout=12):
    end=time.monotonic()+timeout;ctx=GLib.MainContext.default()
    while time.monotonic()<end:
        while ctx.pending():ctx.iteration(False)
        if check():return
        time.sleep(.01)
    raise AssertionError('Desktop rig timed out')


def settle(seconds=.5):
    target=time.monotonic()+seconds;spin(lambda:time.monotonic()>target,seconds+2)


out=Path('dist/desktop');out.mkdir(parents=True,exist_ok=True)
app=Shell();assert app.register(None);app.activate()
windows=[]
for title in ('Research notes','Amerika Office — Budget','Amerika Venture — Reference'):
    win=Gtk.Window(title=title);win.set_default_size(650,450)
    win.set_child(Gtk.Label(label=title));win.present();windows.append(win)
spin(lambda:len(app.windows.app_windows())>=3)
app.parity.desktops.set_count(3)
spin(lambda:len(app.windows.state['desktops'])==3)
app.action('switcher:next');settle()
assert app.parity.switcher.get_visible() and len(app.parity.switcher.items)>=3
assert save_widget(app.parity.switcher,out/'window-switcher.png')
app.parity.switcher.advance(1);target=app.parity.switcher.items[app.parity.switcher.index]['id']
app.parity.switcher.commit()
spin(lambda:any(w['id']==target and w.get('active') for w in app.windows.app_windows()))
app.action('overview');settle()
assert app.parity.overview.get_visible()
app.parity.overview.search.set_text('Budget');settle()
assert len(app.parity.overview.cards)==1
assert 'Budget' in app.parity.overview.items[app.parity.overview.index]['caption']
assert save_widget(app.parity.overview,out/'window-overview.png')
app.parity.overview.hide()
# GDK clipboard event path (background data-control is separately detected).
app.parity.clipboard.clipboard.set('Amerika clipboard rig text')
spin(lambda:'Amerika clipboard rig text' in app.parity.clipboard.history.items)
app.action('clipboard');settle();assert save_widget(app.parity.clipboard,out/'clipboard-history.png')
app.parity.clipboard.hide()
app.action('calendar');settle();assert save_widget(app.parity.calendar,out/'calendar.png')
app.parity.calendar.start_timer(1)
spin(lambda:any(h['summary']=='Timer finished' for h in app.notifications.history),5)
app.parity.calendar.hide()
app.parity.osd.show_value('Volume 45%',45);settle();assert save_widget(app.parity.osd,out/'volume-osd.png')
# KWin receives the original display pixels, not a mocked image.
result=[]
screenshot.run_async(lambda:app.parity.screenshots.capture.workspace()[0],lambda surface,error:result.append((surface,error)))
spin(lambda:bool(result),25)
assert result[0][1] is None,str(result[0][1])
surface=result[0][0];assert surface.get_width()>=1900
surface.write_to_png(str(out/'compositor-capture.png'))
# Exercise a real mode preview on this virtual compositor and let owner EOF
# revert it. No output on the physical desktop is touched.
from amerika import displays
import json,subprocess,sys
outputs=displays.outputs()
assert outputs,'kscreen-doctor did not report the virtual output'
output=next(o for o in outputs if o['enabled']);original_scale=output['scale']
preview=subprocess.Popen([sys.executable,'-m','amerika.displays','--preview'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
preview.stdin.write(json.dumps([(output['name'],'scale',1.25 if original_scale!=1.25 else 1.0)])+'\n');preview.stdin.flush()
response=[]
import threading
threading.Thread(target=lambda:response.append(preview.stdout.readline().strip()),daemon=True).start()
spin(lambda:bool(response),20);assert response[0]=='ready',response
preview.stdin.close()
spin(lambda:preview.poll() is not None,20);assert preview.returncode==0
assert displays.outputs()[0]['scale']==original_scale
preview.stdout.close()
# Record actual compositor frames, then verify a nonempty WebM container.
recorder=app.parity.screenshots.recorder
path=recorder.start(out,area=(0,0,640,360))
settle(1.5);recorder.stop();spin(lambda:not recorder.running,20)
assert not recorder.error,recorder.error
assert path.is_file() and path.stat().st_size>1000
print('Real display preview reverted on owner EOF; real compositor recording saved',flush=True)
for win in windows:win.destroy()
app.parity.close()
app.quit()
print('DESKTOP SERVICES RIG OK: windows, desktops, switcher, overview, clipboard, calendar, OSD, actual KWin capture',flush=True)
