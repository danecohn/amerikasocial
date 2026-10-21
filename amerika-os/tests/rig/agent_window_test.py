"""Actual Control UI in ephemeral WebKit, no provider or model request.

Run by agent_gateway.py inside the private compositor with the real gateway.
"""
import os
import time
from pathlib import Path

import gi
gi.require_version('Gtk','4.0')
from gi.repository import GLib, Gtk
from amerika.agent.window import AgentApp


def spin(check, timeout=60):
    deadline=time.monotonic()+timeout
    ctx=GLib.MainContext.default()
    while time.monotonic()<deadline:
        while ctx.pending():ctx.iteration(False)
        if check():return
        time.sleep(.02)
    raise AssertionError('Agent window did not reach the expected state')


app=AgentApp()
assert app.register(None)
app._setup()
from amerika.agent.window import AgentWindow
app.win=win=AgentWindow(app)
assert win.web is not None,'WebKitGTK is required by the rig'
assert win.web.get_network_session().is_ephemeral(),'browser credentials must remain in memory'
win.present()
spin(lambda:win.status.running and win.stack.get_visible_child_name()=='web' and not win._loading)
results=[]
def got_text(view,result):
    results.append(view.evaluate_javascript_finish(result).to_boolean())
# WebKit's load-finished precedes the Control UI's asynchronous application boot.
ready=False
for attempt in range(60):
    results.clear()
    win.web.evaluate_javascript("document.body.innerText.toLowerCase().includes('chat')",-1,None,None,None,got_text)
    spin(lambda:bool(results),10)
    if results[0]:ready=True;break
    tick=time.monotonic()+.5
    spin(lambda:time.monotonic()>tick,2)
from amerika.shell.app import save_widget
out=Path(os.environ['AGENT_SHOTS']);out.mkdir(parents=True,exist_ok=True)
assert save_widget(win,out/'agent-real-control-ui.png')
assert ready,'The actual Control UI was not rendered; inspect the saved screenshot'
print('REAL WEBKIT RIG OK: ephemeral session and actual gateway Control UI rendered',flush=True)
win.close()
