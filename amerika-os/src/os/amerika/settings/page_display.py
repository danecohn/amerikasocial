"""Display controls with an independent, timed rollback process."""
import json
import os
import subprocess
import sys
import threading
from gi.repository import GLib,Gtk
from .. import displays
from . import ui
from .page_system import Page


def build(app):
    def fetch():return displays.outputs(),displays.night_light()
    def render(p,data):
        outputs,night=data
        def preview(changes):
            if p.busy:return
            p.busy=True;p.body.set_sensitive(False);p.message.set_text('Trying display settings…')
            env=dict(os.environ);env.pop('LD_PRELOAD',None)
            proc=subprocess.Popen([sys.executable,'-m','amerika.displays','--preview'],stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env)
            state={'answered':False,'dialog':None}
            def answer(keep):
                if state['answered']:return
                state['answered']=True
                try:proc.stdin.write('keep\n' if keep else 'revert\n');proc.stdin.flush()
                except (OSError,ValueError):pass
                if state['dialog']:state['dialog'].close()
            def ask():
                dialog=Gtk.Window(transient_for=app.win,modal=True,title='Keep display settings?',default_width=420)
                state['dialog']=dialog
                box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.add_css_class('am-card')
                box.append(ui.label('KEEP DISPLAY SETTINGS?','am-heading'))
                box.append(ui.label('The previous settings return automatically after 15 seconds unless you keep this change.','am-sub',wrap=True))
                buttons=Gtk.Box(spacing=8)
                buttons.append(ui.button('Revert',lambda:answer(False)))
                buttons.append(ui.button('Keep',lambda:answer(True),primary=True));box.append(buttons)
                dialog.connect('close-request',lambda *_:(answer(False),False)[1]);dialog.set_child(box);dialog.present()
                return False
            def finished(outcome):
                state['answered']=True
                if state['dialog']:state['dialog'].destroy()
                p.notice = ('Previous display settings restored.' if outcome=='reverted' else '' if outcome=='kept' else 'The display change failed; the previous settings were restored where possible.')
                p.busy=False;p.body.set_sensitive(True);p.load()
                return False
            def worker():
                outcome='error'
                try:
                    proc.stdin.write(json.dumps(changes)+'\n');proc.stdin.flush()
                    if proc.stdout.readline().strip()=='ready':
                        GLib.idle_add(ask)
                        outcome=proc.stdout.readline().strip()
                    proc.wait(timeout=40)
                except (OSError,ValueError,subprocess.TimeoutExpired):
                    # EOF asks the preview process to roll back. Do not kill the
                    # child before it has restored the previous configuration.
                    pass
                finally:
                    proc.stdin.close();proc.stdout.close()
                    GLib.idle_add(finished,outcome)
            threading.Thread(target=worker,daemon=True).start()
        for output in outputs:
            name=output['name']
            if not output['enabled']:p.section(name,ui.empty_state('This output is disabled.'));continue
            options=[(mode['id'],f'{mode["width"]} × {mode["height"]} · {mode["refresh"]:g} Hz') for mode in output['modes']]
            rows=[]
            if options:rows.append(ui.dropdown_row('Resolution and refresh rate',None,options,(output['mode'] or {}).get('id'),
                                                 lambda value,n=name:preview([(n,'mode',value)])))
            rows.append(ui.dropdown_row('Scale',None,[(v,f'{v*100:g}%') for v in displays.SCALES],output['scale'],
                                        lambda value,n=name:preview([(n,'scale',value)])))
            rows.append(ui.dropdown_row('Rotation',None,[(v,v.capitalize()) for v in displays.ROTATION_NAMES],output['rotation'],
                                        lambda value,n=name:preview([(n,'rotation',value)])))
            position=ui.entry(f'{output["x"]},{output["y"]}',placeholder='x,y')
            controls=Gtk.Box(spacing=6);controls.append(position)
            controls.append(ui.button('Preview',lambda n=name,e=position:preview([(n,'position',e.get_text())])))
            rows.append(ui.row('Position', 'Logical pixels; use x,y.',controls))
            p.section(name,*rows)
        if not outputs:p.section('Screens',ui.empty_state('No configurable outputs were reported by KWin.'))
        if night['available'] is not False:
            p.section('Night light',p.toggle('Reduce blue light',night['active'],lambda on:displays.set_night_light(active=on)),
                      p.choose('Schedule',[(v,v) for v in displays.NIGHT_MODES],night['mode'],lambda value:displays.set_night_light(mode=value)),
                      p.field('Temperature (Kelvin)',night['night_temp'],lambda value:displays.set_night_light(night_temp=int(value))))
    return Page(app,'Displays','Preview resolution, rotation and scaling changes before keeping them.',fetch,render).widget
