"""Rig: the real AltStack Box UI inside amerika-studio-webview (WebKitGTK), with a fake Anthropic upstream returning canned
tool_use turns. Checks: page ready, control endpoint (song.get/set, app.prompt through the tool loop, export.wav, play/stop),
undo of an AI turn, game export bundle, confinement. Run:  tests/rig/studio-rig.sh src/os/box/test/rig/box_rig.sh
Screenshots go to dist/studio/box-*.png."""
import base64
import json
import os
import sys
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/rig'))
from studio_rig import FAKE_KEY, OUT, ROOT, T, kill_bridge, settle, shot, spin  # noqa: E402

from amerika_studio import bridge, common, control, keyring, webview  # noqa: E402

APP = ROOT / 'src/os/box/app'
upstream = []
SCRIPT = [
    {'content': [{'type': 'text', 'text': 'Starting with the boss preset.'},
                 {'type': 'tool_use', 'id': 'toolu_1', 'name': 'genre_preset', 'input': {'name': 'boss', 'bars': 8}}], 'stop_reason': 'tool_use'},
    {'content': [{'type': 'tool_use', 'id': 'toolu_2', 'name': 'set_song_settings', 'input': {'tempo': 150, 'key': 'A', 'scale': 'minor'}},
                 {'type': 'tool_use', 'id': 'toolu_3', 'name': 'render_preview', 'input': {}}], 'stop_reason': 'tool_use'},
    {'content': [{'type': 'text', 'text': 'Done: an 8-bar boss battle in A minor at 150 bpm.'}], 'stop_reason': 'end_turn'},
]


class Fake(ThreadingHTTPServer):
    daemon_threads = True


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        upstream.append(body)
        out = dict(SCRIPT[min(len(upstream) - 1, len(SCRIPT) - 1)], id='m', type='message', role='assistant', model=body['model'],
                   usage={'input_tokens': 100, 'output_tokens': 20})
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


up = Fake(('127.0.0.1', 0), Upstream)
threading.Thread(target=up.serve_forever, daemon=True).start()
os.environ['AMERIKA_STUDIO_UPSTREAM'] = f'http://127.0.0.1:{up.server_address[1]}'
paths = common.Paths()
keyring.store(FAKE_KEY, 'box')
br = bridge.Bridge(paths)
bsrv = bridge.make_server(br, int(os.environ['AMERIKA_STUDIO_PORT']))
threading.Thread(target=bsrv.serve_forever, daemon=True).start()
pool = ThreadPoolExecutor(4)


def wait(fut, timeout=60):
    spin(fut.done, timeout=timeout, what='background call')
    return fut.result()


def js(win, code):
    win.web.evaluate_javascript(code, -1, None, None, None, None)


try:
    from gi.repository import Gtk
    app = Gtk.Application(application_id='org.amerika.BoxRig')
    assert app.register(None)
    from amerika_studio import ui
    ui.setup()
    project = paths.project_dir('box')
    win = webview.StudioWebWindow(app, 'box', APP, 'index.html', project, None, paths)
    win.present()
    spin(lambda: win.page_ready_rpc and win.page_ready_open, timeout=30, what='AltStack Box ready')
    settle(1.0)
    shot(win, 'box-01-startup.png')
    desc = control.read_descriptor('box', paths)
    rpc = lambda m, p=None, t=60: wait(pool.submit(control.rpc, desc, 'box.' + m, p or {}), t)

    # ---- song.get on the blank default song
    got = rpc('song.get')
    assert got['song']['channels'] and got['summary']['channels'], got

    # ---- app.prompt: the whole composer loop (AIClient -> bridge -> fake upstream -> tools -> editor)
    r = rpc('app.prompt', {'message': 'an upbeat 8-bit boss battle, 150 bpm, minor key', 'timeout_s': 120}, 150)
    print(json.dumps(r)[:400], flush=True)
    assert r['reply'].startswith('Done'), r
    assert [t['name'] for t in r['tool_calls']] == ['genre_preset', 'set_song_settings', 'render_preview'], r['tool_calls']
    assert all(t['ok'] for t in r['tool_calls'])
    assert r['song']['key'] == 'A' and r['song']['tempo'] == 150 and r['song']['bars'] == 8, r['song']
    assert len(upstream) == 3
    sysprompt = upstream[0]['system']
    assert 'Composer' in sysprompt and {t['name'] for t in upstream[0]['tools']} >= {'write_track', 'render_preview', 'set_song_json'}
    assert upstream[0]['messages'][0]['content'][-1]['text'].startswith('[Current song:'), 'song state is attached'
    assert 'sk-ant' not in json.dumps(upstream[0]) or FAKE_KEY not in json.dumps(upstream[0])
    settle(0.8)
    shot(win, 'box-02-after-ai.png')

    # ---- song.set / song.get round trip, transport, play does not crash headless
    song = rpc('song.get')['song']
    song['beatsPerMinute'] = 111
    assert rpc('song.set', {'song': song})['ok'], 'song.set'
    assert rpc('song.get')['song']['beatsPerMinute'] == 111
    assert rpc('play')['ok'] and rpc('stop')['ok']
    try:
        rpc('song.set', {'song': 'nope'})
        raise SystemExit('expected invalid params')
    except control.RpcError as e:
        assert e.rpc_code == -32602, e.rpc_code

    # ---- export.wav through the project folder; confinement
    w = rpc('export.wav', {'path': 'exports/rig.wav', 'loops': 1}, 120)
    f = project / 'exports/rig.wav'
    assert f.is_file() and f.stat().st_size == w['bytes'], w
    with wave.open(str(f)) as wf:
        assert wf.getframerate() == 48000 and wf.getnchannels() == 2
        secs = wf.getnframes() / 48000
        assert abs(secs - 8 * 4 * 60 / 111) < 0.1, secs                     # 8 bars at the new 111 bpm
        data = wf.readframes(wf.getnframes())
    assert max(data) > 0 and any(b for b in data[:200000]), 'silent export'
    for bad in ('/etc/x.wav', '../x.wav'):
        try:
            rpc('export.wav', {'path': bad})
            raise SystemExit('path must be refused: ' + bad)
        except control.RpcError as e:
            assert e.rpc_code == -32003, (bad, e.rpc_code)
    try:
        rpc('export.wav', {'path': 'x.wav', 'loops': 99})
        raise SystemExit('loops must be validated')
    except control.RpcError as e:
        assert e.rpc_code == -32602
    assert not (project.parent / 'x.wav').exists()

    def page(code, name, timeout=90):
        """Run async JS in the page; its string result is written into the project folder (the only channel back)."""
        out = project / 'rig' / (name + '.txt')
        out.unlink(missing_ok=True)
        js(win, "(async () => { let r; try { r = String(await (async () => { " + code + " })()); } catch (e) { r = 'ERR:' + e.message; } "
                "await amerikaStudio.fs.writeProject('rig/" + name + ".txt', r, {overwrite: true}); })()")
        spin(out.exists, timeout=timeout, what=name)
        settle(0.2)
        return out.read_text()

    # ---- undo of an AI turn restores the previous song (BeepBox's own undo history)
    r1 = page("const S = Amerika.state; S.host.beginTurn(); await S.tools.run('set_song_settings', {tempo: 77}); "
              "S.composer.lastTurnCommits = S.host.endTurn(); return S.doc.song.tempo;", 'set77')
    assert r1 == '77', r1
    r2 = page("const S = Amerika.state; S.composer.undoTurn(); await new Promise(r => setTimeout(r, 900)); return S.doc.song.tempo;", 'undo')
    assert r2 == '111', 'AI turn undo should restore tempo 111, got ' + r2

    # ---- game export bundle written into the project folder
    g = page("const r = await Amerika.app.exportGame({name: 'rigtrack', sampleRate: 44100, normalizeDb: -1, ogg: false}); return r.files.join(',');", 'game')
    assert g.startswith('rigtrack.wav'), g
    d = project / 'exports/rigtrack'
    meta = json.loads((d / 'rigtrack.json').read_text())
    assert meta['bpm'] == 111 and (d / 'rigtrack.wav').is_file() and (d / 'README.txt').is_file()
    with wave.open(str(d / 'rigtrack.wav')) as wf:
        assert wf.getnframes() == meta['length_samples']
    print('game bundle ok', flush=True)

    # ---- UI: open the export prompt and the about dialog for screenshots, no JS errors
    js(win, "Amerika.state.doc.openPrompt('export'); Amerika.state.doc.notifier.changed(); requestAnimationFrame(() => Amerika.state.doc.notifier.notifyWatchers());")
    settle(1.0)
    shot(win, 'box-03-export-prompt.png')
    js(win, "Amerika.state.doc.undo(); requestAnimationFrame(() => Amerika.state.doc.notifier.notifyWatchers());")
    settle(0.6)
    js(win, "document.getElementById('amAbout').click();")
    settle(0.8)
    shot(win, 'box-04-about.png')
    win._force_close = True
    win.control.stop()
    print('BOX RIG OK', flush=True)
finally:
    kill_bridge()
