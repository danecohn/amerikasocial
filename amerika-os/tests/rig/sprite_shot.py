"""Real UI of Amerika Sprite in WebKitGTK with a FAKE shell/bridge: a canned AI turn builds a knight, then the window is rendered to PNG.
Run through tests/rig/sprite-rig.sh. Env: SPRITE_SHOTS (output dir)."""
import json
import os
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')
from gi.repository import GLib, Gtk, WebKit

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / 'src/os/sprite/app'
OUT = Path(os.environ.get('SPRITE_SHOTS', ROOT / 'dist/sprite-ui/shots'))
OUT.mkdir(parents=True, exist_ok=True)

KNIGHT = [
    '..........ee..........', '.........eEEe.........', '.........eEe..........', '......00000000........',
]


def tu(i, name, inp):
    return {'type': 'tool_use', 'id': 'tu%s' % i, 'name': name, 'input': inp}


R = lambda *rows: list(rows)
SCRIPT = [
    [{'type': 'text', 'text': 'Plan: 24x32 knight, Sweetie 16 palette, light from the top-left.'},
     tu(1, 'set_canvas', {'width': 24, 'height': 32, 'mode': 'indexed', 'clear': True}), tu(2, 'set_palette', {'preset': 'sweetie16'})],
    [tu(3, 'draw_pixels', {'rows': R(
        '..........2222........', '.........2222222.......', '..........222.........', '.......000000000......', '......0dddddddd00.....', '.....0dddddddddd0.....',
        '.....0dd0000000d0.....', '.....0dd0e0e0e0dd0....', '.....0dd0000000d0.....', '......0dddddddd0......', '.......000dd000.......', '....00cccdddddcc00....',
        '...0cccccdddddcccc0...', '..0cc0cccdddddcc0cc0..', '..0cc0ccccddcccc0cc0..', '..0dd0cc000000cc0dd0..', '...00.0cccccccc0.00...', '......0cccddccc0......',
        '......0ccc00ccc0......', '......0ccc00ccc0......', '......0bbb00bbb0......', '.....00bbb00bbb00.....', '....0bbbb0..0bbbb0....', '....000000..000000....')}),
     tu(4, 'view_canvas', {})],
    [tu(5, 'draw_shape', {'shape': 'line', 'x0': 20, 'y0': 9, 'x1': 20, 'y1': 22, 'color': 14, 'thickness': 1}),
     tu(6, 'draw_pixels', {'rows': ['.0.', '000', '.0.'], 'x': 19, 'y': 22}),
     tu(7, 'shade_by_light_direction', {'direction': 'nw'}), tu(8, 'outline', {'color': 0, 'diagonal': False})],
    [tu(9, 'copy_frame_with_transform', {'dy': 1, 'duration_ms': 160}), tu(10, 'new_frame', {'copy_from': 0, 'duration_ms': 160}),
     tu(11, 'set_tag', {'name': 'idle', 'from': 0, 'to': 1}), tu(12, 'select', {'frame': 0}), tu(13, 'view_canvas', {'all_frames': True})],
    [{'type': 'text', 'text': 'Done: a 24x32 knight with a red plume and a sword, two idle frames (tag "idle"). Want a walk cycle next?'}],
]

FAKE = r'''
(function(){
  window.__errors=[]; window.addEventListener('error',function(e){window.__errors.push(String(e.message)+' @'+e.filename+':'+e.lineno)});
  var script=%s, n=0;
  var store={};
  window.amerikaStudio={ info:{app:'sprite',version:'rig',projectDir:'/tmp/rig-project',shell:'rig'},
    request:async function(path,body){ if(path==='/v1/status') return {status:200,json:{key:{sprite:true},models:['claude-sonnet-5-5'],default_model:'claude-sonnet-5-5'}};
      var c=script[n++]; return {status:200,json:{content:c,usage:{input_tokens:10,output_tokens:10},stop_reason:c.some(function(b){return b.type==='tool_use'})?'tool_use':'end_turn'}}; },
    fs:{open:async function(){return null},save:async function(){return null},readFile:async function(){throw new Error('x')},writeProject:async function(p,d){store[p]=d;return {path:'/tmp/rig-project/'+p}},listProject:async function(){return []}},
    recent:{list:async function(){return []},add:async function(){},clear:async function(){}},
    window:{setTitle:async function(){},setDirty:async function(){},close:async function(){}} };
})();
''' % json.dumps(SCRIPT)


def spin(check, timeout=60):
    end = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        if check():
            return True
        time.sleep(0.02)
    return False


def js(view, code, timeout=30):
    res = []
    view.evaluate_javascript(code, -1, None, None, None, lambda v, r: res.append(v.evaluate_javascript_finish(r)))
    assert spin(lambda: bool(res), timeout), 'javascript timed out: ' + code[:60]
    v = res[0]
    return v.to_string() if v is not None else None


Gtk.init()
win = Gtk.Window(title='Amerika Sprite rig')
win.set_default_size(1500, 900)
ucm = WebKit.UserContentManager()
ucm.add_script(WebKit.UserScript.new(FAKE, WebKit.UserContentInjectedFrames.TOP_FRAME, WebKit.UserScriptInjectionTime.START, None, None))
session = WebKit.NetworkSession.new_ephemeral()
view = WebKit.WebView(network_session=session, user_content_manager=ucm)
view.get_settings().set_allow_file_access_from_file_urls(True)
win.set_child(view)
win.present()
loaded = []
view.connect('load-changed', lambda v, e: loaded.append(e) if e == WebKit.LoadEvent.FINISHED else None)
view.load_uri('file://%s/index.html' % APP)
assert spin(lambda: bool(loaded), 30), 'page did not load'
assert spin(lambda: js(view, 'String(!!window.amerikaSprite && !!document.querySelector(".viewport"))') == 'true', 20), 'app did not boot'
from amerika.shell.app import save_widget


def shot(name):
    spin(lambda: False, 0.6) if False else None
    t = time.monotonic() + 0.6
    spin(lambda: time.monotonic() > t, 2)
    assert save_widget(win, OUT / name), 'snapshot failed'


shot('sprite-empty.png')
js(view, 'window.__done=false; window.amerikaSprite.runPrompt("32x32 knight with a red plume, idle animation, SNES style","user").then(function(r){window.__done="ok:"+r.toolCalls.length},function(e){window.__done="err:"+e.message}); 1')
assert spin(lambda: js(view, 'String(window.__done)') != 'false', 60), 'AI turn did not finish'
result = js(view, 'String(window.__done)')
print('AI turn:', result)
assert result.startswith('ok:13'), result
js(view, 'window.amerikaSprite.editor.fit(); window.amerikaSprite.act("toggleOnion"); 1')
shot('sprite-ai-knight.png')
info = json.loads(js(view, 'JSON.stringify({w:AS.session&&window.amerikaSprite.S.doc.w,h:window.amerikaSprite.S.doc.h,frames:window.amerikaSprite.S.doc.frames.length,undo:window.amerikaSprite.S.doc.undoStack.length,tags:window.amerikaSprite.S.doc.tags.length,errors:window.__errors})'))
print(info)
assert info['w'] == 24 and info['h'] == 32 and info['frames'] == 3 and info['tags'] == 1
assert info['errors'] == [], info['errors']
# ONE undo step for the whole AI turn
assert js(view, 'window.amerikaSprite.S.doc.undo(); String(window.amerikaSprite.S.doc.frames.length+"/"+window.amerikaSprite.S.doc.w)') == '1/32'
print('SPRITE RIG OK')
win.close()
