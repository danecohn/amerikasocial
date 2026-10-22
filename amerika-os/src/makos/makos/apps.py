"""Small original MakOS applications. Upstream apps are launched without shell preloads."""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from gi.repository import Gtk, Gio, GLib
from . import ui, common, catalog, search
from .backends import storage, system


def launch_external(app, record, path=None):
    argv = catalog.resolve(record, shutil.which)
    if not argv:
        ui.message(app, record.name, 'The application backend is not installed.')
        return
    if path:
        argv.append(str(path))
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)
    proc = subprocess.Popen(argv, env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Thread(target=proc.wait, daemon=True).start()


def launch(app, app_id, path=None):
    if app_id == 'files':
        from .files import Files
        return Files(app, path)
    if app_id == 'settings':
        from .settings import Settings
        settings=Settings(app)
        if path:settings.pane(str(path))
        return settings
    if app_id in ('seek','spread','desktops','widgets') and hasattr(app, 'action'):
        return app.action(app_id)
    if app_id in ('chatgpt','claude','paper','digits','slides','makbox','venture','terminal','render','engine','sprite','studio'):
        return launch_external(app, catalog.BY_ID[app_id], path)
    if app_id == 'trash-empty':
        context = Gio.AppLaunchContext()
        context.unsetenv('LD_PRELOAD')
        try:
            Gio.AppInfo.launch_default_for_uri('trash:///', context)
        except GLib.Error:
            ui.message(app, 'Trash', 'No system trash handler is installed. Files have not been changed.')
        return
    if app_id == 'preview':
        from .files import preview
        if path:
            return preview(app, path)
        dialog = Gtk.FileDialog(title='Open a file')
        def picked(dialog, result):
            try:
                file = dialog.open_finish(result)
                if file:
                    preview(app, file.get_path())
            except GLib.Error:
                pass
        dialog.open(None, None, picked)
        return
    record = catalog.BY_ID.get(app_id)
    w = ui.window(app, record.name if record else 'MakOS', 650, 480)
    col = ui.box(True, 14, 'sheet')
    if app_id == 'calculator':
        expression = Gtk.Entry(placeholder_text='Enter a calculation', hexpand=True)
        result = Gtk.Label(label='0', xalign=1, selectable=True, css_classes=['hero'])
        def calc():
            try:
                result.set_text(search.calculate(expression.get_text()))
            except (ValueError,SyntaxError,ZeroDivisionError,OverflowError):
                result.set_text('Check the expression')
        expression.connect('activate', lambda *_: calc())
        col.append(expression)
        col.append(result)
        col.append(ui.button('Calculate', calc, 'suggested-action'))
    elif app_id in ('text-editor','notes'):
        text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, monospace=app_id=='text-editor')
        text.set_vexpand(True)
        text.set_hexpand(True)
        path = common.STATE / 'notes.txt' if app_id == 'notes' else Path(path) if path else None
        if path and path.exists():
            if path.stat().st_size>2_000_000:
                return ui.message(app,'Text Editor','This file is too large for the built-in editor. Use another text editor to preserve the whole file.')
            text.get_buffer().set_text(path.read_text(errors='replace'))
            text.get_buffer().set_modified(False)
        col.append(ui.scroll(text))
        def write(target):
            buf = text.get_buffer()
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.makos-tmp')
            temp.write_text(buf.get_text(buf.get_start_iter(),buf.get_end_iter(),True))
            temp.replace(target)
            buf.set_modified(False)
        def save(close_after=False):
            if path:
                try:
                    write(path)
                    if close_after:w.destroy()
                except OSError as error:
                    ui.message(app,'Cannot save',str(error))
            else:
                dialog=Gtk.FileDialog(title='Save text')
                def selected(d,r):
                    try:
                        target=d.save_finish(r)
                        if target:
                            write(Path(target.get_path()))
                            if close_after:w.destroy()
                    except (GLib.Error,OSError) as error:
                        if isinstance(error,OSError):
                            ui.message(app,'Cannot save',str(error))
                dialog.save(w,None,selected)
        col.append(ui.button('Save',save,'suggested-action'))
        def closing(_win):
            if not text.get_buffer().get_modified():return False
            sheet=ui.window(app,'Save changes?',430,190)
            sheet.set_transient_for(w);sheet.set_modal(True)
            body=ui.box(True,16,'sheet')
            body.append(Gtk.Label(label='Save your changes before closing?',wrap=True))
            row=ui.box(spacing=12)
            row.append(ui.button('Cancel',sheet.close))
            row.append(ui.button('Discard',lambda:(sheet.destroy(),w.destroy())))
            row.append(ui.button('Save',lambda:(sheet.destroy(),save(True)),'suggested-action'))
            body.append(row);sheet.set_child(body);sheet.present()
            return True
        w.connect('close-request',closing)
    elif app_id == 'calendar':
        col.append(Gtk.Calendar(hexpand=True,vexpand=True))
    elif app_id == 'disk-utility':
        col.append(Gtk.Label(label='Storage • read-only',xalign=0,css_classes=['hero']))
        for vol in storage.volumes():
            col.append(Gtk.Label(label=json.dumps(vol,ensure_ascii=False),wrap=True,selectable=True,xalign=0))
    elif app_id == 'system-info':
        col.append(ui.icon('settings',96))
        col.append(Gtk.Label(label='MakOS',css_classes=['hero']))
        col.append(Gtk.Label(label='Development preview 0.1.0 • ARM64',css_classes=['subtitle']))
        col.append(Gtk.Label(label=json.dumps(system.os_info(),indent=2),selectable=True,wrap=True))
    elif app_id == 'activity':
        report=Gtk.Label(selectable=True,xalign=0,yalign=0,css_classes=['subtitle'])
        col.append(ui.scroll(report))
        reading=[False]
        def update():
            if not w.get_visible():return False
            if reading[0]:return True
            reading[0]=True
            def work():
                try:
                    rows=subprocess.run(['ps','-eo','pid,comm,%cpu,%mem','--sort=-%cpu'],capture_output=True,text=True,timeout=3).stdout.splitlines()[:28]
                    value='\n'.join(rows)
                except (OSError,subprocess.TimeoutExpired):
                    value='Process information unavailable.'
                def apply():
                    reading[0]=False
                    if w.get_visible():report.set_text(value)
                    return False
                GLib.idle_add(apply)
            threading.Thread(target=work,daemon=True).start()
            return True
        GLib.timeout_add_seconds(3,update)
        GLib.idle_add(lambda:(update(),False)[1])
    else:
        col.append(Gtk.Label(label='This application is not implemented in this development build.',wrap=True))
    w.set_child(col)
    w.present()
    return w


class Applications(Gtk.Application):
    def __init__(self, app_id, path=None):
        super().__init__(application_id='org.makos.Apps.'+app_id.replace('-','_'))
        self.app_id=app_id
        self.path=path
    def do_activate(self):
        self._theme=ui.install_theme()
        launch(self,self.app_id,self.path)
