"""Real pinned gateway + actual shell broker, with fake keyring and no model requests.

Run under tools/kwin-rig.sh via agent_gateway.sh. All HOME/XDG paths must be disposable.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/os/agent'))
from amerika_agent import common, config, keyring

work = Path(os.environ['T'])
assert work in Path(os.environ['XDG_CONFIG_HOME']).parents
assert work in Path(os.environ['XDG_RUNTIME_DIR']).parents
common.ENGINE_DIR = ROOT.parent/'openclaw-src/stage-amerika'
common.NODE_BIN = str(ROOT.parent/'tools/node/bin/node')
common.SECRET_TOOL = str(ROOT/'tests/rig/agent_fake_secret_tool.py')
common.SECRET_BIN = str(ROOT/'src/os/agent/bin/amerika-agent-secret')
common.MCP_COMMAND = str(ROOT/'src/os/agent/amerika-mcp-wrapper')
common.SHARE = work/'share'
shutil.copytree(ROOT/'src/os/agent/activity-plugin', common.SHARE/'activity-plugin')
shutil.copytree(ROOT/'src/os/agent/workspace', common.SHARE/'workspace')
for p in common.SHARE.rglob('*'):
    p.chmod(0o700 if p.is_dir() else 0o600)
common.SHARE.chmod(0o700)
os.environ.update({'FAKE_SECRET_DIR':str(work/'fake-secrets'),
                   'AMERIKA_AGENT_SECRET_TOOL':common.SECRET_TOOL,
                   'AMERIKA_AGENT_SECRET_BIN':common.SECRET_BIN,
                   'AMERIKA_AGENT_ENGINE':str(common.ENGINE_DIR),
                   'AMERIKA_AGENT_NODE':common.NODE_BIN,
                   'AMERIKA_AGENT_SHARE':str(common.SHARE),
                   'PYTHONPATH':str(ROOT/'src/os/agent')+':'+str(ROOT/'src/os')})
paths=common.Paths()
keyring.store('gateway-token','sk-test-FAKE-gateway-token')
with socket.socket() as probe:
    probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
settings=dict(config.DEFAULT_SETTINGS,port=port)
cfg=config.write_config(paths,settings,{},set())
cfg['secrets']['providers']['amerika']['passEnv'] += ['PYTHONPATH', 'FAKE_SECRET_DIR', 'AMERIKA_AGENT_SECRET_TOOL']
cfg['mcp']['servers']['amerika']['env'].update({'AMERIKA_MCP_BIN':str(ROOT/'src/os/bin/amerika-mcp'),
                                             'PYTHONPATH':str(ROOT/'src/os')})
common.atomic_write(paths.openclaw_config,config.render(cfg))
config.save_settings(paths,settings)
env={**os.environ,**paths.engine_env()}
for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENCLAW_GATEWAY_TOKEN','OPENCLAW_GATEWAY_PASSWORD'):
    env.pop(name,None)
cmd=[common.NODE_BIN,str(paths.engine_entry())]


def run(*args,timeout=70):
    r=subprocess.run([*cmd,*args],env=env,capture_output=True,text=True,timeout=timeout)
    if r.returncode:
        raise AssertionError('Engine command failed: '+str(args)+'\n'+(r.stderr+r.stdout)[-2500:])
    return r.stdout


children=[]
try:
    print('Validating generated config against real OpenClaw',flush=True)
    result=run('config','validate')
    assert 'Config valid' in result
    # Probe the real Amerika MCP through the real OpenClaw registry before the
    # gateway acquires state ownership (OpenClaw disallows live CLI probing).
    servers=json.loads(run('mcp','list','--json'))
    assert 'amerika' in json.dumps(servers)
    probed=run('mcp','probe','amerika','--json')
    assert 'amerika' in probed and ('tools' in probed.lower())
    print('OpenClaw listed and connected the actual Amerika MCP server',flush=True)
    activity_log=open(work/'activity.log','w')
    activity=subprocess.Popen([sys.executable,'-m','amerika_agent.cli','activity'],env=env,stdout=activity_log,stderr=subprocess.STDOUT)
    children.append(activity)
    deadline=time.monotonic()+10
    while not paths.activity_socket.exists() and time.monotonic()<deadline:time.sleep(.05)
    assert paths.activity_socket.exists()
    gateway_log=open(work/'gateway.log','w')
    gateway=subprocess.Popen([*cmd,'gateway','run'],env=env,stdout=gateway_log,stderr=subprocess.STDOUT)
    children.append(gateway)
    deadline=time.monotonic()+55
    ready=False
    while time.monotonic()<deadline:
        assert gateway.poll() is None,'Gateway exited: '+(work/'gateway.log').read_text()[-2000:]
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):ready=True;break
        except OSError:time.sleep(.2)
    assert ready,'gateway startup timed out'
    import urllib.request
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=5) as response:assert response.status==200
    health=json.loads(run('health','--json'));assert isinstance(health,dict)
    dashboard=json.loads(run('dashboard','--json'))
    bootstrap=dashboard.get('browserUrl','')
    assert bootstrap.startswith(f'http://127.0.0.1:{port}/#bootstrapToken=')
    assert 'sk-test-FAKE-gateway-token' not in json.dumps(dashboard)
    print('Real gateway: loopback UI 200, authenticated health and one-time browser handoff passed',flush=True)
    window_env=dict(env, AMERIKA_AGENT_BIN=str(ROOT/'src/os/agent/bin/amerika-agent'),
                    AGENT_SHOTS=str(ROOT/'dist/agent-ui'))
    test_typelibs=ROOT.parent/'tools/webkit-dl/root/usr/lib/aarch64-linux-gnu/girepository-1.0'
    if test_typelibs.exists():
        window_env['GI_TYPELIB_PATH']=str(test_typelibs)+':'+env.get('GI_TYPELIB_PATH','')
    subprocess.run([sys.executable,str(ROOT/'tests/rig/agent_window_test.py')],env=window_env,check=True,timeout=100)
    # Exercise the exact shipped plugin hooks against the private socket.
    # This tests state delivery without spending tokens or contacting a provider.
    plugin_script=work/'plugin-test.mjs'
    plugin_script.write_text('''import plugin from '''+json.dumps((common.SHARE/'activity-plugin/index.js').as_uri())+''';
const hooks={};plugin.register({on:(name,fn)=>hooks[name]=fn});
const ctx={sessionKey:'rig-task'};
hooks.before_agent_start({},ctx);
await new Promise(r=>setTimeout(r,100));
hooks.before_tool_call({args:{doNotPublish:'sk-test-FAKE-private-text'}},ctx);
await new Promise(r=>setTimeout(r,100));
hooks.after_tool_call({result:'sk-test-FAKE-private-text'},ctx);
hooks.agent_end({success:true},ctx);
await new Promise(r=>setTimeout(r,200));
''')
    subprocess.run([common.NODE_BIN,str(plugin_script)],env=env,check=True,timeout=10)
    snapshot=json.loads(paths.activity_file.read_text())
    assert snapshot['state']=='idle' and set(snapshot)=={'state','text','since'}
    assert 'sk-test-FAKE-private-text' not in paths.activity_file.read_text()
    # The fake keyring is the only allowed plaintext secret fixture store.
    for folder in (paths.config_dir,paths.state_dir,paths.data_dir):
        if folder.exists():
            for p in folder.rglob('*'):
                if p.is_file():assert b'sk-test-FAKE-gateway-token' not in p.read_bytes(),str(p)
    print('PASS: real pinned gateway + MCP + non-content activity + no persisted shared token; no model calls made',flush=True)
finally:
    for process in reversed(children):
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()
    for handle in ('activity_log','gateway_log'):
        if handle in locals():locals()[handle].close()
