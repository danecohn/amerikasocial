"""Amerika Studio core: keyring (fake secret-tool), bridge (fake upstream), tool loop, MCP, confinement, projects.
No real network, no real keys: every key here is the obviously fake `sk-ant-test-FAKE...`."""
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as types_namespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src/os/studio'))

from amerika_studio import bridge, cli, client, common, confine, control, keyring, mcp, projects, prompts, webcore  # noqa: E402
from amerika_studio.usage import UsageLog  # noqa: E402

FAKE_TOOL = '''#!%(py)s
import json, os, sys
db = os.environ['FAKE_SECRETS']
log = os.environ.get('FAKE_SECRETS_ARGV')
if log:
    open(log, 'a').write(json.dumps(sys.argv[1:]) + '\\n')
try:
    data = json.load(open(db))
except Exception:
    data = {}
cmd = sys.argv[1]
rest = [a for a in sys.argv[2:] if not a.startswith('--label=')]
attrs = dict(zip(rest[0::2], rest[1::2]))
k = attrs.get('service', '') + '/' + attrs.get('name', '')
if cmd == 'store':
    data[k] = sys.stdin.read()
    json.dump(data, open(db, 'w'))
elif cmd == 'lookup':
    if k not in data:
        sys.exit(1)
    sys.stdout.write(data[k])
elif cmd == 'clear':
    data.pop(k, None)
    json.dump(data, open(db, 'w'))
'''

_REAL_RUN = subprocess.run   # tests/test_helper.py replaces subprocess.run for the whole process and never restores it

KEY = 'sk-ant-test-FAKE-shared-0001'
KEY_RENDER = 'sk-ant-test-FAKE-render-0002'
KEY_AGENT = 'sk-ant-test-FAKE-agent-0003'


class Env(unittest.TestCase):
    """Private HOME/XDG dirs and a fake secret-tool for every test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.home = t / 'home'
        run = t / 'run'
        run.mkdir(mode=0o700)
        self.home.mkdir()
        tool = t / 'secret-tool'
        tool.write_text(FAKE_TOOL % {'py': sys.executable})
        tool.chmod(0o755)
        self.argv_log = t / 'argv.log'
        self.env = mock.patch.dict(os.environ, {
            'HOME': str(self.home), 'XDG_RUNTIME_DIR': str(run), 'XDG_CONFIG_HOME': str(self.home / '.config'),
            'XDG_STATE_HOME': str(self.home / '.local/state'), 'XDG_DATA_HOME': str(self.home / '.local/share'),
            'AMERIKA_STUDIO_SECRET_TOOL': str(tool), 'FAKE_SECRETS': str(t / 'secrets.json'),
            'FAKE_SECRETS_ARGV': str(self.argv_log), 'AMERIKA_STUDIO_ROOT': str(self.home / 'Studio')})
        self.env.start()
        self._run = mock.patch('subprocess.run', _REAL_RUN)
        self._run.start()
        os.environ.pop('AMERIKA_STUDIO_UPSTREAM', None)
        self.paths = common.Paths()

    def tearDown(self):
        self._run.stop()
        self.env.stop()
        self.tmp.cleanup()


class KeyringTests(Env):
    def test_store_lookup_clear_shared_and_app(self):
        self.assertFalse(keyring.present())
        keyring.store(KEY + '\n')
        keyring.store(KEY_RENDER, 'render')
        self.assertEqual(keyring.lookup(), KEY)
        self.assertEqual(keyring.lookup('render'), KEY_RENDER)
        self.assertIsNone(keyring.lookup('box'))
        keyring.clear('render')
        self.assertFalse(keyring.present('render'))
        self.assertTrue(keyring.present())

    def test_key_never_in_argv(self):
        keyring.store(KEY)
        keyring.store(KEY_RENDER, 'render')
        keyring.lookup()
        calls = self.argv_log.read_text()
        self.assertNotIn('FAKE', calls)
        self.assertIn('amerika-studio', calls)
        self.assertIn('anthropic-render', calls)

    def test_attributes_follow_the_architecture(self):
        keyring.store(KEY)
        db = json.loads(Path(os.environ['FAKE_SECRETS']).read_text())
        self.assertEqual(list(db), ['amerika-studio/anthropic'])

    def test_clean_key_rejects_junk(self):
        for bad in ('', '   ', 'a b', 'abc\ndef', 'x' * 5000, 'a\x00b'):
            with self.assertRaises(common.StudioError):
                keyring.clean_key(bad)
        with self.assertRaises(common.StudioError):
            keyring.secret_name('nope')

    def test_error_messages_never_contain_the_key(self):
        try:
            keyring.clean_key('sk-ant-test-FAKE bad value')
        except common.StudioError as e:
            self.assertNotIn('FAKE', str(e))

    def test_resolve_order(self):
        s = common.load_settings(self.paths)
        self.assertEqual(keyring.resolve('render', s), (None, None))
        keyring.store(KEY)
        self.assertEqual(keyring.resolve('render', s), (KEY, 'shared'))
        keyring.store(KEY_RENDER, 'render')
        self.assertEqual(keyring.resolve('render', s), (KEY_RENDER, 'app'))
        self.assertEqual(keyring.resolve('box', s), (KEY, 'shared'))
        s['override']['render'] = False
        self.assertEqual(keyring.resolve('render', s), (KEY, 'shared'))

    def test_agent_key_reuse_is_opt_in(self):
        subprocess_store = [keyring._tool('store', 'service', 'amerika-agent', 'name', 'anthropic', stdin=KEY_AGENT)]
        self.assertEqual(subprocess_store[0].returncode, 0)
        s = common.load_settings(self.paths)
        self.assertEqual(keyring.resolve('sprite', s), (None, None))
        s['reuse_agent_key'] = True
        self.assertEqual(keyring.resolve('sprite', s), (KEY_AGENT, 'agent'))
        self.assertTrue(keyring.key_state(s)['sprite'])

    def test_missing_tool_is_a_clean_error(self):
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_SECRET_TOOL': '/nonexistent/secret-tool'}):
            with self.assertRaises(common.StudioError) as cm:
                keyring.store(KEY)
            self.assertEqual(cm.exception.code, 'no_secret_tool')
            self.assertFalse(keyring.present())


# --------------------------------------------------------------------------------------------- fake upstream
class FakeUpstream:
    """Records requests and answers from a queue of (status, body, headers) tuples (last one repeats)."""

    def __init__(self):
        self.requests = []
        self.queue = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(n)
                outer.requests.append({'path': self.path, 'headers': {k.lower(): v for k, v in self.headers.items()},
                                       'body': json.loads(body)})
                status, payload, headers = outer.queue[0] if len(outer.queue) == 1 else outer.queue.pop(0)
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def msg_response(text='hi', blocks=None, stop='end_turn', tin=10, tout=5):
    return {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5-5',
            'content': blocks if blocks is not None else [{'type': 'text', 'text': text}], 'stop_reason': stop,
            'usage': {'input_tokens': tin, 'output_tokens': tout}}


def post(url, path, body, token=None, app=None, headers=None, raw=None):
    h = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = 'Bearer ' + token
    if app:
        h['X-Amerika-App'] = app
    h.update(headers or {})
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(url + path, data=data, headers=h, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}'), dict(e.headers)


def get(url, path, token=None, headers=None):
    h = dict(headers or {})
    if token:
        h['Authorization'] = 'Bearer ' + token
    try:
        with urllib.request.urlopen(urllib.request.Request(url + path, headers=h), timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


GOOD = {'model': 'claude-sonnet-5-5', 'max_tokens': 100, 'messages': [{'role': 'user', 'content': 'make a cube PROMPT-SECRET-TEXT'}]}


class BridgeBase(Env):
    def setUp(self):
        super().setUp()
        self.up = FakeUpstream()
        self.up.queue = [(200, msg_response(), {'request-id': 'req_1'})]
        os.environ['AMERIKA_STUDIO_UPSTREAM'] = self.up.url
        self.bridge = bridge.Bridge(self.paths)
        self.server = bridge.make_server(self.bridge, 0)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.token = self.bridge.token
        self._stderr = mock.patch('sys.stderr', new=io.StringIO())
        self.err = self._stderr.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.up.close()
        self._stderr.stop()
        super().tearDown()


class BridgeTests(BridgeBase):
    def test_token_file_is_private_and_stable(self):
        st = self.paths.token.stat()
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)
        self.assertEqual(bridge.ensure_token(self.paths), self.token)
        self.assertGreaterEqual(len(self.token), 32)

    def test_ping_needs_no_token_everything_else_does(self):
        self.assertEqual(get(self.url, '/v1/ping')[0], 200)
        for path in ('/v1/status', '/v1/models'):
            self.assertEqual(get(self.url, path)[0], 401)
            self.assertEqual(get(self.url, path, token='wrong' * 8)[0], 401)
        self.assertEqual(post(self.url, '/v1/messages', GOOD)[0], 401)
        self.assertEqual(self.up.requests, [])

    def test_browser_origin_and_foreign_host_are_refused(self):
        self.assertEqual(get(self.url, '/v1/status', self.token, {'Origin': 'https://evil.example'})[0], 401)
        self.assertEqual(get(self.url, '/v1/status', self.token, {'Host': 'evil.example'})[0], 401)

    def test_proxy_adds_key_and_hides_everything(self):
        keyring.store(KEY)
        status, body, headers = post(self.url, '/v1/messages', GOOD, self.token, 'render')
        self.assertEqual(status, 200)
        self.assertEqual(body['content'][0]['text'], 'hi')
        up = self.up.requests[0]
        self.assertEqual(up['path'], '/v1/messages')
        self.assertEqual(up['headers']['x-api-key'], KEY)
        self.assertEqual(up['headers']['anthropic-version'], common.ANTHROPIC_VERSION)
        self.assertNotIn('authorization', up['headers'])
        self.assertNotIn(self.token, json.dumps(up['headers']))
        self.assertNotIn(KEY, json.dumps(body) + json.dumps(headers))
        self.assertNotIn(KEY, self.err.getvalue())
        self.assertNotIn(self.token, self.err.getvalue())

    def test_per_app_key_selection(self):
        keyring.store(KEY)
        keyring.store(KEY_RENDER, 'render')
        post(self.url, '/v1/messages', GOOD, self.token, 'render')
        self.bridge._key_cache.clear()
        post(self.url, '/v1/messages', GOOD, self.token, 'box')
        self.assertEqual([r['headers']['x-api-key'] for r in self.up.requests], [KEY_RENDER, KEY])

    def test_no_key_is_a_clean_error_and_not_forwarded(self):
        status, body, _ = post(self.url, '/v1/messages', GOOD, self.token, 'sprite')
        self.assertEqual(status, 403)
        self.assertEqual(body['error']['type'], 'no_api_key')
        self.assertEqual(self.up.requests, [])

    def test_validation_rejects_bad_requests(self):
        keyring.store(KEY)
        cases = [
            (dict(GOOD, model='claude-ancient-1'), 'model not allowed'),
            (dict(GOOD, model=None), 'model not allowed'),
            (dict(GOOD, stream=True), 'streaming'),
            (dict(GOOD, max_tokens=common.MAX_TOKENS_CAP + 1), 'cap'),
            (dict(GOOD, max_tokens=0), 'positive'),
            (dict(GOOD, max_tokens=True), 'positive'),
            (dict(GOOD, messages=[]), 'messages'),
            (dict(GOOD, messages=[{'role': 'system', 'content': 'x'}]), 'role'),
            (dict(GOOD, mcp_servers=[{'url': 'https://x'}]), 'not allowed'),
            (dict(GOOD, tools=[{'type': 'web_search_20250305', 'name': 'web_search'}]), 'custom'),
            ([1, 2], 'object'),
        ]
        for body, needle in cases:
            status, out, _ = post(self.url, '/v1/messages', body, self.token, 'engine')
            self.assertEqual(status, 400, body)
            self.assertIn(needle, out['error']['message'])
        self.assertEqual(self.up.requests, [])

    def test_all_three_models_are_allowed(self):
        keyring.store(KEY)
        for m in ('claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-5-5'):
            self.assertEqual(post(self.url, '/v1/messages', dict(GOOD, model=m), self.token, 'box')[0], 200)

    def test_bad_json_unknown_app_and_size_caps(self):
        keyring.store(KEY)
        self.assertEqual(post(self.url, '/v1/messages', None, self.token, 'box', raw=b'{nope')[0], 400)
        self.assertEqual(post(self.url, '/v1/messages', GOOD, self.token, 'mallory')[0], 400)
        with mock.patch.object(common, 'MAX_BODY_BYTES', 200):
            self.assertEqual(post(self.url, '/v1/messages', dict(GOOD, system='x' * 500), self.token, 'box')[0], 413)
        self.assertEqual(post(self.url, '/v1/other', GOOD, self.token, 'box')[0], 404)

    def test_daily_budget_blocks_and_counts_usage(self):
        keyring.store(KEY)
        s = common.load_settings(self.paths)
        s['daily_budget_tokens'] = 20
        common.save_settings(s, self.paths)
        self.assertEqual(post(self.url, '/v1/messages', GOOD, self.token, 'box')[0], 200)   # 15 tokens used
        self.assertEqual(post(self.url, '/v1/messages', GOOD, self.token, 'box')[0], 200)   # 30 >= 20 now
        status, body, _ = post(self.url, '/v1/messages', GOOD, self.token, 'box')
        self.assertEqual((status, body['error']['type']), (429, 'budget_exceeded'))
        self.assertEqual(len(self.up.requests), 2)
        st = get(self.url, '/v1/status', self.token)[1]
        self.assertEqual(st['budget'], {'daily_tokens': 20, 'used_today': 30})

    def test_budget_zero_is_unlimited(self):
        keyring.store(KEY)
        s = common.load_settings(self.paths)
        s['daily_budget_tokens'] = 0
        common.save_settings(s, self.paths)
        for _ in range(3):
            self.assertEqual(post(self.url, '/v1/messages', GOOD, self.token, 'box')[0], 200)

    def test_usage_log_is_metadata_only(self):
        keyring.store(KEY)
        post(self.url, '/v1/messages', GOOD, self.token, 'engine')
        text = self.paths.usage.read_text()
        row = json.loads(text.splitlines()[0])
        self.assertEqual((row['app'], row['model'], row['in'], row['out']), ('engine', 'claude-sonnet-5-5', 10, 5))
        self.assertNotIn('PROMPT-SECRET-TEXT', text)
        self.assertNotIn('FAKE', text)
        self.assertEqual(stat.S_IMODE(self.paths.usage.stat().st_mode), 0o600)

    def test_status_and_models(self):
        keyring.store(KEY_RENDER, 'render')
        st = get(self.url, '/v1/status', self.token)[1]
        self.assertTrue(st['key']['render'])
        self.assertFalse(st['key']['box'])
        self.assertEqual(st['models'], list(common.MODEL_IDS))
        self.assertEqual(st['default_model'], 'claude-sonnet-5-5')
        self.assertNotIn('FAKE', json.dumps(st))
        models = get(self.url, '/v1/models', self.token)[1]
        self.assertEqual(models['default'], 'claude-sonnet-5-5')
        self.assertEqual([m['id'] for m in models['models']], list(common.MODEL_IDS))

    def test_upstream_errors_pass_through_cleanly(self):
        keyring.store(KEY)
        self.up.queue = [(529, {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}, {'retry-after': '3'})]
        status, body, headers = post(self.url, '/v1/messages', GOOD, self.token, 'box')
        self.assertEqual((status, body['error']['type'], headers.get('retry-after')), (529, 'overloaded_error', '3'))
        self.up.queue = [(401, {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}}, {})]
        self.assertEqual(post(self.url, '/v1/messages', GOOD, self.token, 'box')[1]['error']['type'], 'authentication_error')
        self.up.queue = [(500, b'<html>oops</html>', {})]
        status, body, _ = post(self.url, '/v1/messages', GOOD, self.token, 'box')
        self.assertEqual((status, body['error']['type']), (502, 'bridge_upstream_invalid'))
        self.assertEqual(json.loads(self.paths.usage.read_text() or '{}') if self.paths.usage.exists() else {}, {})

    def test_upstream_down(self):
        keyring.store(KEY)
        self.bridge.upstream = 'http://127.0.0.1:1'
        status, body, _ = post(self.url, '/v1/messages', GOOD, self.token, 'box')
        self.assertEqual((status, body['error']['type']), (502, 'bridge_upstream_unreachable'))
        self.assertNotIn(KEY, json.dumps(body))

    def test_upstream_override_only_accepts_loopback(self):
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_UPSTREAM': 'https://evil.example.com'}), mock.patch('sys.stderr', new=io.StringIO()):
            self.assertEqual(bridge.upstream_base(), common.DEFAULT_UPSTREAM)
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_UPSTREAM': 'http://127.0.0.1:9/'}):
            self.assertEqual(bridge.upstream_base(), 'http://127.0.0.1:9')
        os.environ.pop('AMERIKA_STUDIO_UPSTREAM')
        self.assertEqual(bridge.upstream_base(), 'https://api.anthropic.com')


# --------------------------------------------------------------------------------------------- client + loop
class StubClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def messages(self, payload, stop=None):
        self.payloads.append(json.loads(json.dumps(payload)))
        return self.responses.pop(0)


TOOL_USE = {'type': 'tool_use', 'id': 'toolu_1', 'name': 'scene_info', 'input': {'x': 1}}


class LoopTests(Env):
    def test_tool_use_round_trip(self):
        c = StubClient([msg_response(blocks=[{'type': 'text', 'text': 'looking'}, TOOL_USE], stop='tool_use'),
                        msg_response('done: cube')])
        seen = []
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'hi'}], tools=[{'name': 'scene_info'}], system='sys',
                              handler=lambda n, i, u: seen.append((n, i, u)) or {'objects': ['Cube']}, model='claude-haiku-5-5')
        self.assertEqual(seen, [('scene_info', {'x': 1}, 'toolu_1')])
        self.assertEqual(res.text, 'done: cube')
        self.assertEqual(res.turns, 2)
        self.assertEqual(res.usage, {'input_tokens': 20, 'output_tokens': 10})
        self.assertEqual(res.tool_calls[0]['ok'], True)
        second = c.payloads[1]['messages']
        self.assertEqual(second[-1]['role'], 'user')
        tr = second[-1]['content'][0]
        self.assertEqual((tr['type'], tr['tool_use_id']), ('tool_result', 'toolu_1'))
        self.assertIn('Cube', tr['content'][0]['text'])
        self.assertEqual(c.payloads[0]['system'], 'sys')
        self.assertEqual(c.payloads[0]['model'], 'claude-haiku-5-5')

    def test_image_results_become_image_blocks(self):
        c = StubClient([msg_response(blocks=[TOOL_USE], stop='tool_use'), msg_response('ok')])
        client.run_loop(c, messages=[{'role': 'user', 'content': 'shot'}], model='claude-sonnet-5-5',
                        handler=lambda n, i, u: {'width': 4, 'images': [{'mime': 'image/png', 'base64': 'AAAA'}]})
        blocks = c.payloads[1]['messages'][-1]['content'][0]['content']
        kinds = [b['type'] for b in blocks]
        self.assertEqual(kinds, ['text', 'image'])
        self.assertEqual(blocks[1]['source'], {'type': 'base64', 'media_type': 'image/png', 'data': 'AAAA'})

    def test_handler_errors_are_reported_to_the_model(self):
        def boom(n, i, u):
            raise ValueError('cube too big')
        c = StubClient([msg_response(blocks=[TOOL_USE], stop='tool_use'), msg_response('sorry')])
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'x'}], handler=boom, model='claude-sonnet-5-5')
        tr = c.payloads[1]['messages'][-1]['content'][0]
        self.assertTrue(tr['is_error'])
        self.assertIn('cube too big', tr['content'][0]['text'])
        self.assertFalse(res.tool_calls[0]['ok'])

    def test_max_turns(self):
        c = StubClient([msg_response(blocks=[TOOL_USE], stop='tool_use')] * 5)
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'x'}], handler=lambda *a: 'ok', max_turns=3, model='claude-sonnet-5-5')
        self.assertTrue(res.hit_max_turns)
        self.assertEqual(res.turns, 3)

    def test_stop_flag_before_and_between_tools(self):
        stop = threading.Event()
        stop.set()
        c = StubClient([])
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'x'}], stop=stop, model='claude-sonnet-5-5')
        self.assertTrue(res.stopped)
        self.assertEqual(c.payloads, [])
        stop = threading.Event()
        two = [TOOL_USE, dict(TOOL_USE, id='toolu_2')]
        c = StubClient([msg_response(blocks=two, stop='tool_use')])
        calls = []
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'x'}], stop=stop, model='claude-sonnet-5-5',
                              handler=lambda n, i, u: calls.append(u) or stop.set() or 'ok')
        self.assertEqual(calls, ['toolu_1'])
        self.assertTrue(res.stopped)
        self.assertEqual(len(res.messages[-1]['content']), 2)       # the conversation stays valid: both tool_use ids answered
        self.assertTrue(res.messages[-1]['content'][1]['is_error'])

    def test_text_only_answer_stops_after_one_request(self):
        c = StubClient([msg_response('just text')])
        res = client.run_loop(c, messages=[{'role': 'user', 'content': 'x'}], model='claude-sonnet-5-5')
        self.assertEqual((res.text, res.turns, res.stop_reason), ('just text', 1, 'end_turn'))


class ClientIntegrationTests(BridgeBase):
    def client(self, **kw):
        return client.BridgeClient('engine', base_url=self.url, paths=self.paths, sleep=lambda s: None, **kw)

    def test_full_stack_loop_with_canned_upstream(self):
        keyring.store(KEY)
        self.up.queue = [(200, msg_response(blocks=[TOOL_USE], stop='tool_use'), {}), (200, msg_response('built it'), {})]
        res = client.run_loop(self.client(), messages=[{'role': 'user', 'content': 'go'}], handler=lambda *a: 'fine', model='claude-sonnet-5-5')
        self.assertEqual(res.text, 'built it')
        self.assertEqual(len(self.up.requests), 2)

    def test_retries_on_529_and_429_then_succeeds(self):
        keyring.store(KEY)
        over = (529, {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'busy'}}, {})
        rate = (429, {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'slow'}}, {'retry-after': '1'})
        self.up.queue = [over, rate, (200, msg_response('finally'), {})]
        sleeps = []
        c = client.BridgeClient('engine', base_url=self.url, paths=self.paths, sleep=sleeps.append)
        self.assertEqual(c.messages(GOOD)['content'][0]['text'], 'finally')
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(sleeps[1], 1.0)          # honours retry-after

    def test_gives_up_after_retries_with_mapped_error(self):
        keyring.store(KEY)
        self.up.queue = [(529, {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'busy'}}, {})]
        with self.assertRaises(client.ApiError) as cm:
            self.client(retries=2).messages(GOOD)
        self.assertEqual(cm.exception.kind, 'overloaded')
        self.assertEqual(len(self.up.requests), 3)

    def test_error_mapping(self):
        keyring.store(KEY)
        cases = [((401, {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'bad'}}), 'key_rejected'),
                 ((400, {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'bad'}}), 'invalid_request'),
                 ((413, {'type': 'error', 'error': {'type': 'request_too_large', 'message': 'big'}}), 'too_large'),
                 ((500, {'type': 'error', 'error': {'type': 'api_error', 'message': 'boom'}}), 'server')]
        for (status, body), kind in cases:
            self.up.queue = [(status, body, {})]
            with self.assertRaises(client.ApiError) as cm:
                self.client(retries=0).messages(GOOD)
            self.assertEqual(cm.exception.kind, kind)
        c = client.BridgeClient('engine', base_url=self.url, token='wrong' * 8, paths=self.paths)
        with self.assertRaises(client.ApiError) as cm:
            c.messages(GOOD)
        self.assertEqual(cm.exception.kind, 'bridge_auth')

    def test_no_key_and_budget_are_not_retried(self):
        with self.assertRaises(client.ApiError) as cm:
            self.client().messages(GOOD)
        self.assertEqual(cm.exception.kind, 'no_key')
        keyring.store(KEY)
        s = common.load_settings(self.paths)
        s['daily_budget_tokens'] = 1
        common.save_settings(s, self.paths)
        self.client().messages(GOOD)
        with self.assertRaises(client.ApiError) as cm:
            self.client().messages(GOOD)
        self.assertEqual(cm.exception.kind, 'budget')
        self.assertEqual(len(self.up.requests), 1)

    def test_bridge_down_is_reported(self):
        c = client.BridgeClient('box', base_url='http://127.0.0.1:1', token='t' * 40, paths=self.paths)
        with self.assertRaises(client.ApiError) as cm:
            c.messages(GOOD)
        self.assertEqual(cm.exception.kind, 'bridge_down')
        c = client.BridgeClient('box', base_url=self.url, paths=common.Paths())
        self.paths.token.unlink()
        with self.assertRaises(client.ApiError):
            c.token()

    def test_status_helper(self):
        keyring.store(KEY_RENDER, 'render')
        self.assertTrue(self.client().status()['key']['render'])


# --------------------------------------------------------------------------------------------- tools.json + MCP
class FakeApp:
    """A control endpoint like the apps open: JSON-RPC at /rpc with a bearer token, plus its descriptor file."""

    def __init__(self, paths, app, token='apptoken-' + 'x' * 30, ready=True):
        self.calls = []
        self.token = token
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                if self.headers.get('Authorization') != 'Bearer ' + outer.token:
                    self.send_response(401)
                    self.end_headers()
                    return
                req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.calls.append(req)
                m = req['method']
                if m == f'{app}.app.ping':
                    res = {'result': {'ok': True, 'app': app, 'ready': ready}}
                elif m.endswith('scene.info'):
                    res = {'result': {'objects': ['Cube']}}
                elif m.endswith('viewport.screenshot'):
                    res = {'result': {'width': 2, 'images': [{'mime': 'image/png', 'base64': 'AAAA'}]}}
                else:
                    res = {'error': {'code': -32601, 'message': 'method not found'}}
                raw = json.dumps(dict(res, jsonrpc='2.0', id=req['id'])).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        common.ensure_private_dir(paths.runtime_dir)
        self.path = paths.descriptor(app)
        common.atomic_write(self.path, json.dumps({'app': app, 'url': f'http://127.0.0.1:{self.server.server_address[1]}',
                                                   'token': token, 'pid': os.getpid(), 'version': '1'}), 0o600)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ToolsJsonTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / 'src/os/studio/tools.json').read_text())

    def test_structure(self):
        self.assertEqual(set(self.doc['apps']), set(common.APPS))
        names = set()
        for app, info in self.doc['apps'].items():
            self.assertEqual(info['launcher'], common.APP_LAUNCHERS[app])
            tools = {t['name'] for t in info['tools']}
            self.assertIn('app.prompt', tools)
            for t in info['tools']:
                self.assertRegex(t['name'], r'^[a-z_]+(\.[a-z_]+)+$|^(play|stop)$|^export$|^[a-z_]+\.[a-z_.]+$')
                self.assertIn(t['risk'], ('read', 'act', 'critical'))
                self.assertGreater(t['timeout'], 0)
                self.assertTrue(t['description'].strip())
                schema = t['inputSchema']
                self.assertEqual(schema['type'], 'object')
                self.assertIs(schema['additionalProperties'], False)
                for r in schema.get('required', []):
                    self.assertIn(r, schema['properties'])
                n = mcp.mcp_name(app, t['name'])
                self.assertRegex(n, r'^[a-zA-Z0-9_-]{1,64}$')       # valid Anthropic tool name
                self.assertNotIn(n, names)
                names.add(n)

    def test_required_tools_from_the_brief(self):
        want = {'render': ['scene.info', 'scene.run_python', 'model.create_from_description', 'model.apply_change',
                           'viewport.screenshot', 'export'],
                'engine': ['project.info', 'files.list', 'files.read', 'files.write', 'scene.create', 'scene.describe',
                           'script.create', 'script.edit', 'recipe.get', 'recipe.set', 'recipe.assemble', 'project.run',
                           'project.stop', 'project.logs', 'import.model'],
                'sprite': ['canvas.info', 'canvas.describe_to_sprite', 'canvas.apply_change', 'frames.list', 'palette.get',
                           'palette.set', 'export'],
                'box': ['song.get', 'song.set', 'song.compose_from_description', 'song.apply_change', 'play', 'stop', 'export.wav']}
        for app, tools in want.items():
            have = {t['name'] for t in self.doc['apps'][app]['tools']}
            self.assertFalse(set(tools) - have, (app, set(tools) - have))

    def test_code_execution_is_critical(self):
        run = next(t for t in self.doc['apps']['render']['tools'] if t['name'] == 'scene.run_python')
        self.assertEqual(run['risk'], 'critical')

    def test_validator(self):
        schema = {'type': 'object', 'properties': {'a': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'b': {'type': 'string', 'enum': ['x']},
                                                     'c': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 1}},
                  'required': ['a'], 'additionalProperties': False}
        self.assertEqual(mcp.validate({'a': 2, 'b': 'x', 'c': ['q']}, schema), [])
        for bad in ({}, {'a': 0}, {'a': 4}, {'a': True}, {'a': '2'}, {'a': 1, 'b': 'y'}, {'a': 1, 'z': 1}, {'a': 1, 'c': ['a', 'b']},
                    {'a': 1, 'c': [1]}, []):
            self.assertTrue(mcp.validate(bad, schema), bad)


class McpTests(Env):
    def serve(self, server, lines):
        out = io.StringIO()
        mcp.serve(server, io.StringIO('\n'.join(json.dumps(l) for l in lines) + '\n'), out)
        return {m['id']: m for m in map(json.loads, out.getvalue().splitlines())}

    def make(self, approver=lambda e, a: True, rpc=None, launcher=None):
        return mcp.Server(paths=self.paths, approver=approver, launcher=launcher or (lambda app: None),
                          rpc=rpc or (lambda desc, method, params, timeout=60: {'echo': method}))

    def test_initialize_and_list(self):
        out = self.serve(self.make(), [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                                       {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                                       {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                                       {'jsonrpc': '2.0', 'id': 3, 'method': 'nope'}])
        self.assertEqual(out[1]['result']['serverInfo']['name'], 'amerika-studio')
        tools = {t['name']: t for t in out[2]['result']['tools']}
        self.assertIn('render_scene_run_python', tools)
        self.assertIn('box_export_wav', tools)
        self.assertIn('studio_launch', tools)
        self.assertTrue(tools['render_scene_info']['annotations']['readOnlyHint'])
        self.assertTrue(tools['render_scene_run_python']['annotations']['destructiveHint'])
        for t in tools.values():
            self.assertEqual(t['inputSchema']['type'], 'object')
        self.assertEqual(out[3]['error']['code'], -32601)

    def test_call_forwards_to_the_app_endpoint(self):
        app = FakeApp(self.paths, 'render')
        self.addCleanup(app.close)
        srv = mcp.Server(paths=self.paths, approver=lambda e, a: True)
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'render_scene_info', 'arguments': {}}},
                               {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'render_viewport_screenshot', 'arguments': {'width': 64}}}])
        self.assertEqual(json.loads(out[1]['result']['content'][0]['text']), {'objects': ['Cube']})
        self.assertNotIn('isError', out[1]['result'])
        kinds = [c['type'] for c in out[2]['result']['content']]
        self.assertEqual(kinds, ['text', 'image'])
        self.assertEqual(out[2]['result']['content'][1]['mimeType'], 'image/png')
        methods = [c['method'] for c in app.calls]
        self.assertIn('render.scene.info', methods)
        self.assertIn('render.viewport.screenshot', methods)
        self.assertEqual([c['params'] for c in app.calls if c['method'] == 'render.viewport.screenshot'], [{'width': 64}])

    def test_invalid_arguments_never_reach_the_app(self):
        calls = []
        srv = self.make(rpc=lambda *a, **k: calls.append(a))
        out = self.serve(srv, [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'engine_files_read', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'engine_files_read', 'arguments': {'path': 'a', 'evil': 1}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'engine_nope', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'sprite_canvas_describe_to_sprite', 'arguments': {'description': 'x', 'width': 100000}}}])
        for i in (1, 2, 3, 4):
            self.assertTrue(out[i]['result']['isError'], i)
        self.assertEqual(calls, [])

    def test_critical_tools_always_need_approval(self):
        calls = []
        asked = []
        srv = self.make(approver=lambda e, a: asked.append(e['tool']) or False, rpc=lambda *a, **k: calls.append(a))
        srv.descriptor_for = lambda app: {'url': 'http://127.0.0.1:1', 'token': 'x'}
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                                'params': {'name': 'render_scene_run_python', 'arguments': {'code': 'print(1)'}}}])
        self.assertTrue(out[1]['result']['isError'])
        self.assertIn('declined', out[1]['result']['content'][0]['text'])
        self.assertEqual((asked, calls), (['scene.run_python'], []))
        srv.approver = lambda e, a: True
        srv.rpc = lambda desc, method, params, timeout=60: {'ran': method, 'timeout': timeout}
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                                'params': {'name': 'render_scene_run_python', 'arguments': {'code': 'print(1)'}}}])
        self.assertEqual(json.loads(out[1]['result']['content'][0]['text']), {'ran': 'render.scene.run_python', 'timeout': 120})

    def test_non_critical_tools_do_not_prompt(self):
        asked = []
        srv = self.make(approver=lambda e, a: asked.append(1) or False)
        srv.descriptor_for = lambda app: {'url': 'http://127.0.0.1:1', 'token': 'x'}
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'box_play', 'arguments': {}}}])
        self.assertNotIn('isError', out[1]['result'])
        self.assertEqual(asked, [])

    def test_approver_command_failure_means_no(self):
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_APPROVER': '/nonexistent/approver'}):
            self.assertFalse(mcp.approve({'app': 'render', 'tool': 'scene.run_python'}, {'code': 'x'}))
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_APPROVER': 'true'}):
            self.assertTrue(mcp.approve({'app': 'render', 'tool': 'scene.run_python'}, {'code': 'x'}))
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_APPROVER': 'false'}):
            self.assertFalse(mcp.approve({'app': 'render', 'tool': 'scene.run_python'}, {'code': 'x'}))

    def test_app_errors_become_tool_errors(self):
        app = FakeApp(self.paths, 'engine')
        self.addCleanup(app.close)
        srv = mcp.Server(paths=self.paths)
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'engine_project_info', 'arguments': {}}}])
        self.assertTrue(out[1]['result']['isError'])
        self.assertIn('method not found', out[1]['result']['content'][0]['text'])

    def test_not_installed_app_reports_clearly(self):
        srv = mcp.Server(paths=self.paths)
        with mock.patch.dict(os.environ, {'PATH': '/nonexistent'}):
            out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'box_song_get', 'arguments': {}}}])
        self.assertTrue(out[1]['result']['isError'])
        self.assertIn('not installed', out[1]['result']['content'][0]['text'])

    def test_autolaunch_can_be_disabled_and_studio_status(self):
        srv = mcp.Server(paths=self.paths)
        srv.autolaunch = False
        out = self.serve(srv, [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'box_song_get', 'arguments': {}}},
                               {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'studio_status', 'arguments': {}}}])
        self.assertIn('studio_launch', out[1]['result']['content'][0]['text'])
        self.assertEqual(set(json.loads(out[2]['result']['content'][0]['text'])), set(common.APPS))

    def test_launch_via_launcher_waits_for_ready(self):
        bin_dir = Path(self.tmp.name) / 'bin'
        bin_dir.mkdir()
        marker = Path(self.tmp.name) / 'launched'
        (bin_dir / 'amerika-box').write_text(f'#!/bin/sh\necho started > {marker}\n')
        (bin_dir / 'amerika-box').chmod(0o755)
        state = {}

        def fake_ping(app, paths=None):
            if marker.exists():
                state['n'] = state.get('n', 0) + 1
                return {'ok': True, 'ready': state['n'] > 2}
            return None
        with mock.patch.dict(os.environ, {'PATH': f'{bin_dir}:{os.environ["PATH"]}'}), \
                mock.patch.object(control, 'ping', fake_ping), \
                mock.patch.object(control, 'read_descriptor', lambda app, paths=None: {'app': app}):
            d = control.launch('box', wait=10, paths=self.paths, sleep=lambda s: __import__('time').sleep(0.05))
        self.assertEqual(d, {'app': 'box'})
        self.assertTrue(marker.exists())
        self.assertGreater(state['n'], 2)
        with mock.patch.dict(os.environ, {'PATH': '/nonexistent'}), self.assertRaises(common.StudioError) as cm:
            control.launch('sprite', paths=self.paths)
        self.assertEqual(cm.exception.code, 'not_installed')

    def test_descriptor_trust_rules(self):
        app = FakeApp(self.paths, 'sprite')
        self.addCleanup(app.close)
        self.assertEqual(control.read_descriptor('sprite', self.paths)['app'], 'sprite')
        self.assertTrue(control.ping('sprite', self.paths)['ready'])
        os.chmod(app.path, 0o644)                                                   # group/world readable: not trusted
        self.assertIsNone(control.read_descriptor('sprite', self.paths))
        d = {'app': 'sprite', 'url': 'http://example.com:80', 'token': 't', 'pid': os.getpid()}   # not loopback
        common.atomic_write(app.path, json.dumps(d), 0o600)
        self.assertIsNone(control.read_descriptor('sprite', self.paths))
        d.update(url='http://127.0.0.1:9', pid=2 ** 22 + 12345)                       # dead pid
        common.atomic_write(app.path, json.dumps(d), 0o600)
        self.assertIsNone(control.read_descriptor('sprite', self.paths))
        self.assertIsNone(control.ping('sprite', self.paths))


# --------------------------------------------------------------------------------------------- confinement etc.
class ConfineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'proj'
        self.root.mkdir()
        (Path(self.tmp.name) / 'secret.txt').write_text('outside')
        os.symlink(Path(self.tmp.name) / 'secret.txt', self.root / 'link.txt')
        os.symlink(self.tmp.name, self.root / 'dirlink')
        (self.root / 'a').mkdir()
        (self.root / 'a/b.gd').write_text('extends Node\n')
        (self.root / '.git').mkdir()
        (self.root / '.git/config').write_text('x')

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_escapes(self):
        for bad in ('/etc/passwd', '../secret.txt', 'a/../../secret.txt', '~/x', 'a\x00b', 'link.txt/../x', 'C:\\x', '..', 'dirlink/secret.txt'):
            with self.assertRaises(confine.ConfineError, msg=bad):
                confine.resolve_in(self.root, bad)
        with self.assertRaises(confine.ConfineError):
            confine.resolve_in(self.root, 'x' * 2000)
        with self.assertRaises(confine.ConfineError):
            confine.resolve_in(self.root, 5)

    def test_accepts_inside_paths(self):
        self.assertEqual(confine.resolve_in(self.root, 'a/b.gd', True), (self.root / 'a/b.gd').resolve())
        self.assertEqual(confine.resolve_in(self.root, 'new/dir/file.txt'), (self.root / 'new/dir/file.txt').resolve())
        self.assertEqual(confine.resolve_in(self.root, '.'), self.root.resolve())
        self.assertEqual(confine.resolve_in(self.root, ''), self.root.resolve())

    def test_read_write_list(self):
        self.assertEqual(confine.read_text(self.root, 'a/b.gd')['content'], 'extends Node\n')
        with self.assertRaises(confine.ConfineError):
            confine.read_text(self.root, 'link.txt')
        self.assertTrue(confine.read_text(self.root, 'a/b.gd', max_bytes=3)['truncated'])
        r = confine.write_text(self.root, 'scripts/player.gd', 'extends Node2D\n')
        self.assertEqual(r['bytes'], 15)
        with self.assertRaises(common.StudioError) as cm:
            confine.write_text(self.root, 'scripts/player.gd', 'x')
        self.assertEqual(cm.exception.code, 'exists')
        confine.write_text(self.root, 'scripts/player.gd', 'new', overwrite=True)
        with self.assertRaises(confine.ConfineError):
            confine.write_text(self.root, 'link.txt', 'pwn', overwrite=True)
        with self.assertRaises(confine.ConfineError):
            confine.write_text(self.root, 'dirlink/pwn.txt', 'pwn')
        self.assertEqual((Path(self.tmp.name) / 'secret.txt').read_text(), 'outside')
        names = [e['path'] for e in confine.list_dir(self.root, '.', recursive=True)]
        self.assertIn('scripts/player.gd', names)
        self.assertFalse([n for n in names if n.startswith('.git')])
        self.assertNotIn('dirlink/secret.txt', names)
        with self.assertRaises(confine.ConfineError):
            confine.list_dir(self.root, '..')


class MiscTests(Env):
    def test_prompts(self):
        p = prompts.system_prompt('render', project_summary='Cube at origin', extra='Be brief.')
        self.assertIn('Amerika Render', p)
        self.assertIn('bpy', p)
        self.assertIn('Cube at origin', p)
        self.assertIn('Be brief.', p)
        self.assertIn('<context>', prompts.user_request('make it red', {'selected': 'Cube'}))
        self.assertEqual(prompts.user_request('hi'), 'hi')
        self.assertEqual(prompts.extract_code('Here:\n```python\nprint(1)\n```\nok', 'python'), 'print(1)')
        self.assertEqual(prompts.extract_json('Sure! ```json\n{"a": [1, 2]}\n``` done'), {'a': [1, 2]})
        self.assertEqual(prompts.extract_json('result: [1,2,3] end'), [1, 2, 3])
        with self.assertRaises(ValueError):
            prompts.extract_json('nothing here')

    def test_usage_log_rolls_up(self):
        log = UsageLog(self.paths)
        log.record('box', 'claude-haiku-5-5', 100, 50)
        log.record('box', 'claude-haiku-5-5', 1, 1)
        self.assertEqual(log.tokens_today(), 152)
        self.assertEqual(UsageLog(self.paths).tokens_today(), 152)       # survives a restart
        self.assertEqual(list(log.summary().values())[0]['calls'], 2)

    def test_settings_validation(self):
        s = common.validate_settings({'model': 'gpt-evil', 'daily_budget_tokens': -5, 'agent_tools': 'yes', 'override': {'render': False, 'zzz': True}})
        self.assertEqual(s['model'], common.DEFAULT_MODEL)
        self.assertEqual(s['daily_budget_tokens'], common.DEFAULT_DAILY_BUDGET)
        self.assertFalse(s['agent_tools'])
        self.assertFalse(s['override']['render'])
        self.assertNotIn('zzz', s['override'])
        common.save_settings(dict(s, model='claude-opus-5-5'), self.paths)
        self.assertEqual(common.load_settings(self.paths)['model'], 'claude-opus-5-5')
        self.assertEqual(stat.S_IMODE(self.paths.settings.stat().st_mode), 0o600)

    def test_new_game_creates_studio_folders(self):
        r = projects.new_game('Space Cats!', self.paths)
        self.assertEqual(r['slug'], 'Space-Cats')
        for app in common.APPS:
            self.assertTrue((self.paths.project_dir(app) / 'Space-Cats').is_dir())
        self.assertIn('Space Cats', (self.paths.project_dir('engine') / 'Space-Cats/project.godot').read_text())
        self.assertEqual(projects.new_game('Space Cats', self.paths)['slug'], 'Space-Cats-2')
        with self.assertRaises(common.StudioError):
            projects.new_game('///', self.paths)
        self.assertTrue(projects.recent_projects(self.paths))

    def test_cli_key_set_reads_stdin_and_never_prints_it(self):
        with mock.patch('sys.stdin', io.StringIO(KEY + '\n')), mock.patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(cli.main(['key', 'set', '--app', 'render']), 0)
        self.assertNotIn('FAKE', out.getvalue())
        self.assertTrue(keyring.present('render'))
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            cli.main(['key', 'status', '--json'])
        st = json.loads(out.getvalue())
        self.assertTrue(st['apps']['render'])
        self.assertFalse(st['shared'])
        self.assertNotIn('FAKE', out.getvalue())
        with mock.patch('sys.stdin', io.StringIO('has space\n')), mock.patch('sys.stderr', new=io.StringIO()):
            self.assertEqual(cli.main(['key', 'set']), 1)
        with mock.patch('sys.stdout', new=io.StringIO()):
            cli.main(['key', 'clear', '--app', 'render'])
        self.assertFalse(keyring.present('render'))

    def test_cli_status_budget_config(self):
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(cli.main(['status', '--json']), 0)
        st = json.loads(out.getvalue())
        self.assertEqual(set(st['apps']), set(common.APPS))
        self.assertEqual(st['model'], 'claude-sonnet-5-5')
        with mock.patch('sys.stdout', new=io.StringIO()):
            cli.main(['budget', '--set', '12345'])
            cli.main(['config', 'model', 'claude-haiku-5-5'])
            cli.main(['config', 'override', 'off', '--app', 'box'])
        s = common.load_settings(self.paths)
        self.assertEqual((s['daily_budget_tokens'], s['model'], s['override']['box']), (12345, 'claude-haiku-5-5', False))
        with mock.patch('sys.stderr', new=io.StringIO()):
            self.assertEqual(cli.main(['config', 'model', 'gpt-5']), 1)

    def test_ensure_with_running_bridge_is_a_no_op(self):
        up = FakeUpstream()
        self.addCleanup(up.close)
        b = bridge.Bridge(self.paths)
        server = bridge.make_server(b, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with mock.patch.dict(os.environ, {'AMERIKA_STUDIO_PORT': str(server.server_address[1])}), mock.patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(cli.main(['ensure', '--json']), 0)
        self.assertTrue(json.loads(out.getvalue())['running'])


class PackagingFilesTests(unittest.TestCase):
    def test_launchers_and_unit_exist(self):
        base = ROOT / 'src/os/studio'
        for name in ('amerika-studio', 'amerika-studio-bridge', 'amerika-studio-mcp', 'amerika-studio-hub', 'amerika-studio-keys',
                     'amerika-studio-webview', 'amerika-studio-approve'):
            f = base / 'bin' / name
            self.assertTrue(os.access(f, os.X_OK), name)
        unit = (base / 'systemd/amerika-studio-bridge.service').read_text()
        self.assertIn('ExecStart=/usr/bin/amerika-studio-bridge', unit)


# --------------------------------------------------------------------------------------------- web shell (GTK-free parts)
class WebcoreTests(Env):
    def test_navigation_policy(self):
        app = Path(self.tmp.name) / 'app'
        (app / 'sub').mkdir(parents=True)
        (app / 'index.html').write_text('x')
        os.symlink('/etc', app / 'etc-link')
        roots = [app, Path(self.tmp.name) / 'shared']
        ok = [(app / 'index.html').as_uri(), (app / 'sub').as_uri(), 'about:blank', (app / 'a b.html').as_uri()]
        bad = ['https://example.com/', 'http://127.0.0.1:18890/v1/status', 'file:///etc/passwd', (app.parent / 'other.html').as_uri(),
               (app / 'etc-link/passwd').as_uri(), 'file://evil-host/x', 'javascript:alert(1)', 'data:text/html,hi', 'ftp://x/', '', 'file:///' + str(app).lstrip('/') + '/../secret']
        for uri in ok:
            self.assertTrue(webcore.uri_allowed(uri, roots), uri)
        for uri in bad:
            self.assertFalse(webcore.uri_allowed(uri, roots), uri)

    def test_bridge_path_allowlist(self):
        self.assertEqual(webcore.check_bridge_request('/v1/status', None), ('GET', '/v1/status'))
        self.assertEqual(webcore.check_bridge_request('/v1/messages', {'a': 1}), ('POST', '/v1/messages'))
        for path, body in (('/v1/messages', None), ('/v1/status', {}), ('/etc/passwd', None), ('/v1/other', {}), (5, None), ('/v1/messages/', {})):
            with self.assertRaises(webcore.RpcFail):
                webcore.check_bridge_request(path, body)

    def test_grants_recent_and_data(self):
        proj = Path(self.tmp.name) / 'proj'
        proj.mkdir()
        outside = Path(self.tmp.name) / 'picked.png'
        outside.write_bytes(b'\x89PNG')
        g = webcore.Grants(proj)
        self.assertTrue(g.allowed(proj / 'x/y.png'))
        self.assertFalse(g.allowed('/etc/passwd'))
        self.assertFalse(g.allowed(outside))
        g.grant(outside)
        self.assertTrue(g.allowed(outside))
        self.assertFalse(g.allowed(proj / '../etc/passwd'))
        spec = webcore.SPECS['sprite']
        self.assertTrue(webcore.is_binary('a.PNG', spec) and not webcore.is_binary('a.json', spec))
        f = webcore.read_for_page(outside, True)
        self.assertEqual(base64_decode(f['data']), b'\x89PNG')
        with self.assertRaises(webcore.RpcFail):
            webcore.read_for_page(proj, False)
        self.assertEqual(webcore.decode_data('aGk=', 'base64'), b'hi')
        self.assertEqual(webcore.decode_data('hé', 'utf8'), 'hé'.encode())
        for bad in (('!!notb64', 'base64'), (5, 'utf8'), ('x', 'latin1')):
            with self.assertRaises(webcore.RpcFail):
                webcore.decode_data(*bad)
        r = webcore.Recent(self.paths, 'box')
        files = []
        for i in range(15):
            fp = Path(self.tmp.name) / f's{i}.json'
            fp.write_text('{}')
            files.append(fp)
            r.add(fp)
        listed = r.list()
        self.assertEqual(len(listed), webcore.MAX_RECENT)
        self.assertEqual(listed[0], str(files[-1].resolve()))
        files[-1].unlink()
        self.assertNotIn(str(files[-1].resolve()), r.list())          # vanished files drop out
        r.clear()
        self.assertEqual(r.list(), [])
        self.assertEqual(stat.S_IMODE(self.paths.recent('box').stat().st_mode), 0o600)

    def test_pending_hand_over(self):
        pend = webcore.Pending()
        rid = pend.new()
        threading.Timer(0.05, lambda: pend.resolve(rid, {'ok': 1})).start()
        self.assertEqual(pend.wait(rid, 2), {'ok': 1})
        rid = pend.new()
        pend.resolve(rid, error={'code': -32001, 'message': 'denied'})
        with self.assertRaises(webcore.RpcFail) as cm:
            pend.wait(rid, 2)
        self.assertEqual(cm.exception.code, -32001)
        with self.assertRaises(webcore.RpcFail):
            pend.wait(pend.new(), 0.05)

    def test_control_server_auth_prefix_busy_and_descriptor(self):
        gate = threading.Event()
        started = threading.Event()

        def handler(name, params, timeout):
            if name == 'slow':
                started.set()
                gate.wait(5)
            if name == 'boom':
                raise RuntimeError('secret detail')
            if name == 'denied':
                raise webcore.RpcFail(-32001, 'user said no')
            return {'name': name, 'params': params, 'timeout': timeout}
        srv = webcore.ControlServer('box', handler, self.paths)
        srv.start()
        self.addCleanup(srv.stop)
        d = control.read_descriptor('box', self.paths)
        self.assertEqual(stat.S_IMODE(self.paths.descriptor('box').stat().st_mode), 0o600)
        self.assertEqual(control.rpc(d, 'box.song.get', {'a': 1}, timeout=7), {'name': 'song.get', 'params': {'a': 1}, 'timeout': 7})
        with self.assertRaises(control.RpcError) as cm:
            control.rpc(dict(d, token='nope'), 'box.song.get')
        self.assertEqual(cm.exception.rpc_code, -32005)
        with self.assertRaises(control.RpcError) as cm:
            control.rpc(d, 'sprite.song.get')
        self.assertEqual(cm.exception.rpc_code, -32601)
        with self.assertRaises(control.RpcError) as cm:
            control.rpc(d, 'box.denied')
        self.assertEqual(cm.exception.rpc_code, -32001)
        with self.assertRaises(control.RpcError) as cm:
            control.rpc(d, 'box.boom')
        self.assertNotIn('secret detail', str(cm.exception))
        t = threading.Thread(target=lambda: control.rpc(d, 'box.slow', {}, timeout=10))
        t.start()
        self.assertTrue(started.wait(3))
        with self.assertRaises(control.RpcError) as cm:
            control.rpc(d, 'box.song.get')
        self.assertEqual(cm.exception.rpc_code, -32002)
        self.assertTrue(control.rpc(d, 'box.app.ping')['name'] == 'app.ping')   # direct methods are not blocked
        gate.set()
        t.join(5)
        srv.stop()
        self.assertFalse(self.paths.descriptor('box').exists())

    def test_mcp_restore_env(self):
        env = {}
        run = Path(self.tmp.name) / 'run2'
        run.mkdir()
        (run / 'wayland-1').write_text('')
        (run / 'wayland-1.lock').write_text('')
        (run / 'bus').write_text('')
        env['XDG_RUNTIME_DIR'] = str(run)
        mcp.restore_env(env)
        self.assertEqual(env['WAYLAND_DISPLAY'], 'wayland-1')
        self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'], f'unix:path={run}/bus')
        env = {}
        mcp.restore_env(env)
        self.assertEqual(env['XDG_RUNTIME_DIR'], f'/run/user/{os.getuid()}')


def base64_decode(s):
    import base64
    return base64.b64decode(s)


class JsClientTests(unittest.TestCase):
    """The web apps' tool-use loop (ai-client.js), run under node with a canned `request`."""

    def test_ai_client_under_node(self):
        import shutil
        node = shutil.which('node') or str(ROOT.parent / 'tools/node/bin/node')
        if not os.path.exists(node):
            self.skipTest('node is not available')
        script = r"""
const {AIClient} = require(process.argv[1]);
const assert = require('assert');
(async () => {
  const sent = [];
  const queue = [
    {status: 529, json: {error: {type: 'overloaded_error', message: 'busy'}}, headers: {}},
    {status: 200, json: {content: [{type: 'text', text: 'looking'}, {type: 'tool_use', id: 't1', name: 'canvas_info', input: {}}], stop_reason: 'tool_use', usage: {input_tokens: 5, output_tokens: 2}}},
    {status: 200, json: {content: [{type: 'text', text: 'done'}], stop_reason: 'end_turn', usage: {input_tokens: 6, output_tokens: 3}}},
  ];
  const sleeps = [];
  const ai = new AIClient({model: 'claude-haiku-5-5', system: 'sys', tools: [{name: 'canvas_info', description: 'd', input_schema: {type: 'object'}}],
    request: async (path, body) => { sent.push([path, JSON.parse(JSON.stringify(body))]); return queue.shift(); },
    sleep: async (ms) => { sleeps.push(ms); },
    run: async (name, input) => ({width: 16, image: {mime: 'image/png', base64: 'AAAA'}})});
  const out = await ai.send('draw', {images: [{mime: 'image/png', base64: 'QQ=='}]});
  assert.strictEqual(out.text, 'done');
  assert.deepStrictEqual(out.toolCalls.map((c) => c.name), ['canvas_info']);
  assert.deepStrictEqual(out.usage, {input_tokens: 11, output_tokens: 5});
  assert.strictEqual(sleeps.length, 1);                                  // one retry for the 529
  assert.strictEqual(sent.length, 3);
  assert.strictEqual(sent[0][1].model, 'claude-haiku-5-5');
  assert.strictEqual(sent[0][1].messages[0].content[0].type, 'image');
  const tr = sent[2][1].messages[2].content[0];
  assert.strictEqual(tr.type, 'tool_result');
  assert.deepStrictEqual(tr.content.map((b) => b.type), ['text', 'image']);
  // errors
  const bad = new AIClient({model: 'claude-sonnet-5-5', request: async () => ({status: 403, json: {error: {type: 'no_api_key', message: 'x'}}}), sleep: async () => {}});
  await assert.rejects(() => bad.send('hi'), (e) => e.code === 'no_key');
  assert.strictEqual(bad.messages.length, 0);                            // the unanswered user turn is dropped
  const budget = new AIClient({model: 'claude-sonnet-5-5', request: async () => ({status: 429, json: {error: {type: 'budget_exceeded', message: 'x'}}}), sleep: async () => { throw new Error('must not retry'); }});
  await assert.rejects(() => budget.send('hi'), (e) => e.code === 'budget');
  // stop flag and handler errors
  let calls = 0;
  const loop = new AIClient({model: 'claude-sonnet-5-5', maxTurns: 3,
    request: async () => ({status: 200, json: {content: [{type: 'tool_use', id: 'u' + (++calls), name: 'x', input: {}}], stop_reason: 'tool_use', usage: {}}}),
    run: async () => { throw new Error('boom'); }});
  const res = await loop.send('go');
  assert.strictEqual(res.hitMaxTurns, true);
  assert.strictEqual(loop.messages[2].content[0].is_error, true);
  const stopper = new AIClient({model: 'claude-sonnet-5-5', request: async () => ({status: 200, json: {content: [{type: 'tool_use', id: 'a', name: 'x', input: {}}, {type: 'tool_use', id: 'b', name: 'x', input: {}}], stop_reason: 'tool_use', usage: {}}}),
    run: async () => { stopper.stop(); return 'ok'; }});
  const r2 = await stopper.send('go');
  assert.strictEqual(r2.stopped, true);
  assert.strictEqual(stopper.messages[stopper.messages.length - 1].content.length, 2);
  console.log('JS OK');
})().catch((e) => { console.error(e); process.exit(1); });
"""
        r = _REAL_RUN([node, '-e', script, str(ROOT / 'src/os/studio/web/ai-client.js')], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn('JS OK', r.stdout)


class PackagingTests(unittest.TestCase):
    def build(self, name):
        import importlib.util
        import shutil
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)

        class Pkg:
            def __init__(s, pname, version, desc, **kw):
                s.name, s.kw, s.root, s.scripts, s.desc = pname, kw, tmp / pname, {}, desc
                s.root.mkdir(parents=True)

            def path(s, p):
                return s.root / str(p).lstrip('/')

            def file(s, d, t, m=0o644):
                q = s.path(d)
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(t)

            def copy(s, src, d, m=None):
                q = s.path(d)
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, q)

            def copyright(s, t):
                s.file(f'/usr/share/doc/{s.name}/copyright', t)
        b = types_namespace(Pkg=Pkg, OS=ROOT / 'src/os', ROOT=ROOT, DE_VERSION='3.2.0-1')
        spec = importlib.util.spec_from_file_location(name, ROOT / f'tools/builders/{name}.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, {k: f() for k, f in mod.register(b).items()}, tmp

    def test_studio_package_contents(self):
        mod, pkgs, tmp = self.build('studio')
        root = pkgs['amerika-studio'].root
        for rel in ('usr/bin/amerika-studio', 'usr/bin/amerika-studio-bridge', 'usr/bin/amerika-studio-mcp', 'usr/bin/amerika-studio-hub',
                    'usr/bin/amerika-studio-keys', 'usr/bin/amerika-studio-webview', 'usr/lib/systemd/user/amerika-studio-bridge.service',
                    'usr/share/amerika-studio/tools.json', 'usr/share/amerika-studio/web/ai-client.js', 'usr/share/amerika-studio/web/shell.js',
                    'usr/lib/python3/dist-packages/amerika_studio/bridge.py', 'usr/share/applications/amerika-studio.desktop',
                    'usr/share/icons/hicolor/scalable/apps/amerika-studio.svg', 'usr/share/icons/hicolor/scalable/apps/amerika-render.svg',
                    'usr/share/doc/amerika-studio/README.md', 'usr/share/doc/amerika-studio/webview.md'):
            self.assertTrue((root / rel).exists(), rel)
        self.assertFalse(list(root.rglob('__pycache__')))
        self.assertNotIn('enable', pkgs['amerika-studio'].scripts['postinst'].replace('enabled', ''))
        self.assertIn('libsecret-tools', pkgs['amerika-studio'].kw['depends'])
        self.assertEqual(getattr(mod, 'META_DEPENDS', []), [])

    def test_developer_meta_is_opt_in(self):
        mod, pkgs, _ = self.build('developer')
        kw = pkgs['amerika-developer'].kw
        for dep in ('amerika-studio', 'amerika-render', 'amerika-engine', 'amerika-sprite', 'amerika-box'):
            self.assertIn(dep, kw['depends'])
        for rec in ('git', 'ffmpeg', 'vulkan-tools', 'mesa-utils-bin', 'audacity', 'gimp', 'inkscape'):
            self.assertIn(rec, kw['recommends'])
        self.assertEqual(getattr(mod, 'META_DEPENDS', []), [])         # must never become a dependency of amerika-desktop
        self.assertEqual(getattr(mod, 'META_RECOMMENDS', []), [])
        _mod, _pkgs, _ = self.build('studio')
        self.assertEqual(getattr(_mod, 'META_RECOMMENDS', []), [])

    def test_agent_config_registers_studio_mcp_only_when_enabled(self):
        sys.path.insert(0, str(ROOT / 'src/os/agent'))
        from amerika_agent import config
        off = config.build_config(config.DEFAULT_SETTINGS)
        self.assertNotIn('amerika-studio', off['mcp']['servers'])
        on = config.build_config(dict(config.DEFAULT_SETTINGS, studio_tools=True))
        srv = on['mcp']['servers']['amerika-studio']
        self.assertTrue(srv['command'].endswith('amerika-studio-mcp'))
        self.assertIn('amerika-studio__*', on['tools']['allow'])
        self.assertIn('amerika', on['mcp']['servers'])
        with self.assertRaises(Exception):
            config.validate_settings(dict(config.DEFAULT_SETTINGS, studio_tools='yes'))
        self.assertNotIn('sk-ant', json.dumps(on))


if __name__ == '__main__':
    unittest.main()
