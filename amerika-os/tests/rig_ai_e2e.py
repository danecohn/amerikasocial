"""End-to-end test of the AI layer inside the KWin rig: MCP stdio server -> broker -> real tools -> audit log.
Run through tools/kwin-rig.sh (see tests/run-rig-tests.sh)."""
import json
import os
import subprocess
import sys
import time

ROOT = os.environ['ROOT']
T = os.environ['T']
env = dict(os.environ)
mcp = subprocess.Popen([f'{ROOT}/src/os/bin/amerika-mcp', '--client', 'claude'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                       text=True, env=env, bufsize=1)
n = [0]


def rpc(method, params=None, timeout=60):
    n[0] += 1
    mcp.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': n[0], 'method': method, 'params': params or {}}) + '\n')
    mcp.stdin.flush()
    line = mcp.stdout.readline()
    return json.loads(line)


def call(name, **args):
    r = rpc('tools/call', {'name': name, 'arguments': args})
    res = r['result']
    text = res['content'][0]['text']
    return (not res.get('isError', False)), (json.loads(text) if not res.get('isError') else text)


results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('PASS ' if cond else 'FAIL ') + name + (' :: ' + str(detail)[:160] if detail and not cond else ''), flush=True)


r = rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '0'}})
check('initialize', r['result']['serverInfo']['name'] == 'amerika-system')
tools = rpc('tools/list')['result']['tools']
check('tools/list has the system tools', len(tools) >= 30 and any(t['name'] == 'windows.list' for t in tools), len(tools))
ok, info = call('system.info')
check('system.info', ok and info.get('machine'), info)
ok, wl = call('windows.list')
check('windows.list sees the test window', ok and any('E2E TEST WINDOW' in (w.get('caption') or '').upper() for w in wl['windows']), wl)
wid = next((w['id'] for w in (wl['windows'] if ok else []) if 'E2E TEST WINDOW' in (w.get('caption') or '').upper()), None)
ok, r1 = call('windows.tile', id=wid, side='left')
check('windows.tile (act, allowed in balanced mode)', ok, r1)
time.sleep(1.2)
ok, wl2 = call('windows.list')
w2 = next((w for w in wl2['windows'] if w['id'] == wid), None)
check('window actually moved to the left half', w2 and w2['x'] <= 5 and 800 <= w2['w'] <= 1000, w2)
ok, r2 = call('windows.move_resize', id=wid, x=300, y=200, w=700, h=500)
time.sleep(1.2)
ok, wl3 = call('windows.list')
w3 = next((w for w in wl3['windows'] if w['id'] == wid), None)
check('windows.move_resize', ok and w3 and (w3['x'], w3['y']) == (300, 200), w3)
ok, r3 = call('notifications.send', title='Claude says hi', body='Sent through the MCP server')
check('notifications.send', ok and r3.get('id'), r3)
ok, r4 = call('settings.set', key='wallpaper', value='grid')
check('settings.set wallpaper', ok, r4)
ok, r5 = call('settings.set', key='dock_size', value=500)
check('settings.set rejects bad values', not ok, r5)
ok, r6 = call('windows.focus', id='not-a-window')
check('rejects an unknown window id', not ok, r6)
ok, r7 = call('apps.launch', id='does-not-exist')
check('rejects an unknown app', not ok, r7)
ok, r8 = call('files.list', path='/etc')
check('files.list refuses paths outside home', not ok, r8)
ok, r9 = call('nonexistent.tool')
check('unknown tool refused', not ok, r9)
# sensitive tool: balanced mode must ask. Nobody answers, so pause the AI (the Stop switch) and expect a refusal.
import threading
box = {}
threading.Thread(target=lambda: box.update(res=call('shell.run', command='echo hello')), daemon=True).start()
time.sleep(2.5)
subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.amerika.Shell', '--object-path', '/Control', '--method', 'org.amerika.Control.Action', 'stop'],
               capture_output=True)
time.sleep(2)
res = box.get('res')
check('sensitive tool asks first; Stop cancels it', res and not res[0] and 'declined' in str(res[1]).lower(), res)
ok, r10 = call('system.status')
check('everything refused while paused', not ok and 'paused' in str(r10).lower(), r10)
subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.amerika.Shell', '--object-path', '/Control', '--method', 'org.amerika.Control.Action', 'stop'],
               capture_output=True)
time.sleep(1)
ok, r11 = call('system.status')
check('resume works', ok, r11)
mcp.stdin.close()
audit = [json.loads(line) for line in open(f'{T}/state/amerika-os/ai-audit.log')]
check('audit log records calls and denials', any(e['event'] == 'denied' for e in audit) and sum(1 for e in audit if e['event'] == 'call') >= 8, len(audit))
print(f'RESULT {sum(1 for _, c, _ in results if c)}/{len(results)} passed', flush=True)
sys.exit(0 if all(c for _, c, _ in results) else 1)
