"""Rig: amerika-studio-webview with a test page: JS bridge, bridge proxy, tool loop, file confinement, navigation/CSP
restrictions, control endpoint (also through the MCP server). Screenshots in dist/studio/."""
import base64
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from studio_rig import FAKE_KEY, OUT, ROOT, RUN, T, kill_bridge, settle, shot, spin  # noqa: F401

from gi.repository import Gio, GLib  # noqa: E402

from amerika_studio import bridge, common, control, keyring, mcp, webview  # noqa: E402


class Fake(ThreadingHTTPServer):
    daemon_threads = True


def serve(handler_cls):
    srv = Fake(('127.0.0.1', 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


external_hits = []


class External(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        external_hits.append(self.path)
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


upstream_requests = []
script = [
    {'content': [{'type': 'tool_use', 'id': 'toolu_1', 'name': 'canvas_info', 'input': {}}], 'stop_reason': 'tool_use'},
    {'content': [{'type': 'text', 'text': 'sprite is 16x16'}], 'stop_reason': 'end_turn'},
]


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        upstream_requests.append({'headers': {k.lower(): v for k, v in self.headers.items()}, 'body': body})
        out = dict(script[min(len(upstream_requests) - 1, len(script) - 1)], id='m', type='message', role='assistant',
                   model=body['model'], usage={'input_tokens': 7, 'output_tokens': 3})
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


ext = serve(External)
up = serve(Upstream)
os.environ['AMERIKA_STUDIO_UPSTREAM'] = f'http://127.0.0.1:{up.server_address[1]}'
paths = common.Paths()
keyring.store(FAKE_KEY, 'sprite')
br = bridge.Bridge(paths)
bsrv = bridge.make_server(br, int(os.environ['AMERIKA_STUDIO_PORT']))
threading.Thread(target=bsrv.serve_forever, daemon=True).start()
pool = ThreadPoolExecutor(4)

try:
    from gi.repository import Gtk
    app = Gtk.Application(application_id='org.amerika.StudioWebTest')
    assert app.register(None)
    from amerika_studio import ui
    ui.setup()
    project = paths.project_dir('sprite')
    win = webview.StudioWebWindow(app, 'sprite', ROOT / 'tests/rig/webview_testapp', 'index.html', project, None, paths)
    win.present()
    spin(lambda: win.page_ready_rpc and win.page_ready_open, timeout=20, what='test page ready')
    print('page ready', flush=True)

    def wait(fut, timeout=20):
        spin(fut.done, timeout=timeout, what='background call')
        return fut.result()

    # ---- control endpoint, driven like the MCP server does
    desc = control.read_descriptor('sprite', paths)
    assert desc and desc['url'].startswith('http://127.0.0.1:'), desc
    assert oct(paths.descriptor('sprite').stat().st_mode & 0o777) == '0o600'
    assert wait(pool.submit(control.ping, 'sprite', paths))['ready'] is True
    info = wait(pool.submit(control.rpc, desc, 'sprite.canvas.info', {'x': 1}))
    assert info == {'width': 16, 'height': 16, 'frames': 1, 'got': {'x': 1}}, info
    try:
        wait(pool.submit(control.rpc, desc, 'sprite.canvas.apply_change', {'instruction': 'x'}))
        raise SystemExit('expected an error')
    except control.RpcError as e:
        assert e.rpc_code == -32001 and 'nope' in str(e), (e.rpc_code, str(e))
    try:
        wait(pool.submit(control.rpc, desc, 'sprite.bogus', {}))
        raise SystemExit('expected an error')
    except control.RpcError as e:
        assert e.rpc_code == -32601, e.rpc_code
    try:
        wait(pool.submit(control.rpc, desc, 'render.scene.info', {}))
        raise SystemExit('wrong app prefix must be refused')
    except control.RpcError as e:
        assert e.rpc_code == -32601
    bad = dict(desc, token='wrong')
    try:
        wait(pool.submit(control.rpc, bad, 'sprite.canvas.info', {}))
        raise SystemExit('bad token must be refused')
    except control.RpcError:
        pass
    slow = pool.submit(control.rpc, desc, 'sprite.slow', {})
    settle(0.2)
    busy = pool.submit(control.rpc, desc, 'sprite.canvas.info', {})
    try:
        wait(busy)
        raise SystemExit('expected busy')
    except control.RpcError as e:
        assert e.rpc_code == -32002, e.rpc_code
    assert wait(slow) == {'slow': True}
    assert wait(pool.submit(control.ping, 'sprite', paths))['ready']          # ping works while busy too

    # ---- the same through the MCP server
    srv = mcp.Server(paths=paths, approver=lambda e, a: True)
    content = wait(pool.submit(srv.call_tool, 'sprite_canvas_info', {}))
    assert json.loads(content[0]['text'])['width'] == 16
    try:
        wait(pool.submit(srv.call_tool, 'sprite_palette_get', {}))           # the test page has no such method -> error
        raise SystemExit('expected an error')
    except control.RpcError as e:
        assert 'unknown palette.get' in str(e) and e.rpc_code == -32601, str(e)
    print('mcp ok', flush=True)
finally:
    pass

try:
    # ---- page self test: JS bridge, proxy, tool loop, confinement, CSP
    win.web.evaluate_javascript(f"selfTest('http://127.0.0.1:{ext.server_address[1]}')", -1, None, None, None, None)
    spin(lambda: win.get_title().startswith('DONE'), timeout=30, what='page self test')
    r = wait(pool.submit(control.rpc, control.read_descriptor('sprite', paths), 'sprite.result', {}))
    print(json.dumps(r, indent=1), flush=True)
    assert r['hasToken'] is False, 'token visible to the page'
    assert r['status'] == 200
    assert 'may only call' in r['badPath'] and 'may only call' in r['badGet'], r
    assert r['ai']['text'] == 'sprite is 16x16' and r['ai']['calls'] == ['canvas_info'] and r['ai']['messages'] == 4, r['ai']
    assert r['ai']['usage'] == {'input_tokens': 14, 'output_tokens': 6}
    assert r['write'] is True
    assert 'outside' in r['escape'] or 'not allowed' in r['escape'], r['escape']
    assert 'absolute' in r['abs'], r['abs']
    assert 'path_not_allowed' in r['read'], r['read']
    assert 'exports/test.png' in r['list']
    assert (paths.project_dir('sprite') / 'exports/test.png').read_bytes() == base64.b64decode('AAAA')
    assert not (paths.project_dir('sprite').parent / 'evil.txt').exists()
    assert r['fetchExternal'] == 'blocked' and r['imgExternal'] == 'blocked', r
    assert r['fetchLocal'] == 'ok', r['fetchLocal']
    assert r['localStorage'] == 'v'
    assert upstream_requests and all(u['headers'].get('x-api-key') == FAKE_KEY for u in upstream_requests)
    assert all('authorization' not in u['headers'] for u in upstream_requests)
    assert not external_hits, external_hits

    # ---- navigation away is refused
    win.web.evaluate_javascript(f"location.href = 'http://127.0.0.1:{ext.server_address[1]}/nav'", -1, None, None, None, None)
    settle(1.0)
    assert not external_hits, 'navigation to an external page was not blocked'
    assert win.web.get_uri().startswith('file://'), win.web.get_uri()
    from amerika_studio import webcore
    assert not webcore.uri_allowed('file:///etc/passwd', win.roots)

    # ---- opening a file delivers it to onOpen; binary by extension
    png = T / 'pic.png'
    png.write_bytes(b'\x89PNG\r\n\x1a\nFAKE')
    win.open_path(str(png))
    desc = control.read_descriptor('sprite', paths)
    settle(0.5)
    got = pool.submit(control.rpc, desc, 'sprite.last_open', {})
    f = wait(got)
    assert f and f['name'] == 'pic.png' and f['binary'] is True and base64.b64decode(f['data']).startswith(b'\x89PNG'), f
    assert str(png.resolve()) in win.recent.list()
    ss = wait(pool.submit(control.rpc, desc, 'sprite.app.screenshot', {}))
    (OUT / 'webview-screenshot.png').write_bytes(base64.b64decode(ss['images'][0]['base64']))
    shot(win, 'webview-window.png')
    # ---- close removes the descriptor
    win._force_close = True
    win.control.stop()
    assert not paths.descriptor('sprite').exists()
    print('STUDIO WEBVIEW RIG OK', flush=True)
finally:
    kill_bridge()
