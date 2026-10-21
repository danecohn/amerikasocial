"""amerika-agent: command line for Amerika Agent (OpenClaw engine, Amerika integration).

The JSON shapes printed by `status --json` and `key status --json` are a contract with the Amerika Shell and Settings;
see docs/agent/README.md before changing them.
"""
import argparse
import getpass
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import __version__, common, config, keyring
from .common import AgentError

ENGINE_ENV_DROP = common.ENGINE_ENV_DROP
SHELL_TIMEOUT = 20


def out(obj):
    print(json.dumps(obj, indent=2, sort_keys=False))


def err(message):
    print(f'amerika-agent: {message}', file=sys.stderr)


# ------------------------------------------------------------------------------------------------------ engine helpers
def engine_installed(paths):
    return paths.engine_entry().is_file()


def engine_version(paths):
    pkg = common.read_json(paths.engine_entry().parent / 'package.json', {})
    return str(pkg.get('version') or '')


def engine_env(paths):
    """Environment for every engine process: ours on top of the user's, minus anything that could smuggle a credential in."""
    return common.clean_engine_env(paths)


def engine_cmd(paths, *args):
    return [common.NODE_BIN, str(paths.engine_entry()), *args]


def require_engine(paths):
    if not engine_installed(paths):
        raise AgentError(f'the OpenClaw engine is not installed at {paths.engine_entry()} (package amerika-agent)')


def gateway_live(port):
    """Unauthenticated local liveness probe: no keyring lookup for status polling."""
    import urllib.request
    try:
        # Explicitly bypass proxy environment for this loopback-only request.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/healthz',timeout=.5) as response:
            data=json.loads(response.read(4097))
            return response.status==200 and data.get('ok') is True and data.get('status')=='live'
    except (OSError,ValueError,AttributeError):return False


def port_open(port, host='127.0.0.1', timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ------------------------------------------------------------------------------------------------------ providers cache
def providers_cache_path(paths):
    return paths.state_dir / 'providers.json'


def read_providers_cache(paths):
    raw = common.read_json(providers_cache_path(paths), {})
    return {p: bool(raw.get(p)) for p in common.PROVIDERS}


def verify_providers(paths, write_cache=True):
    """Look the keys up in the keyring (may prompt to unlock it) and refresh the cache `status` uses."""
    found = {p: bool(keyring.lookup(p)) for p in common.PROVIDERS}
    if write_cache:
        paths.state_dir.mkdir(parents=True, exist_ok=True)
        common.atomic_write(providers_cache_path(paths), json.dumps(found) + '\n', 0o600)
    return found


# ------------------------------------------------------------------------------------------------------ systemd
def systemctl(*args, check=True):
    if not shutil.which('systemctl'):
        raise AgentError('systemctl not found; this system has no systemd')
    try:
        r = common.run(['systemctl', '--user', *args], timeout=30)
    except subprocess.TimeoutExpired:
        raise AgentError('systemctl --user timed out')
    if check and r.returncode != 0:
        text = (r.stderr or r.stdout).strip().splitlines()
        raise AgentError('systemctl --user ' + ' '.join(args) + ' failed' + (': ' + text[-1] if text else ''))
    return r


def service_active():
    try:
        return systemctl('is-active', common.SERVICE_NAME, check=False).stdout.strip() == 'active'
    except AgentError:
        return False


# ------------------------------------------------------------------------------------------------------ apply
def apply_config(paths, providers=None, quiet=True):
    """Regenerate openclaw.json from the settings and the keyring, make sure the gateway token exists."""
    settings = config.load_settings(paths)
    config.sync_shell_mode(paths,settings['mode'])
    providers = providers if providers is not None else verify_providers(paths)
    keyring.ensure_gateway_token()
    channel_secrets = {n for n in (s for c in common.CHANNEL_SECRETS.values() for s in c.values()) if keyring.present(n)}
    cfg = config.write_config(paths, settings, providers, channel_secrets)
    return settings, providers, cfg


# ------------------------------------------------------------------------------------------------------ status
def build_status(paths, verify=False):
    settings = config.load_settings(paths)
    providers = verify_providers(paths) if verify else read_providers_cache(paths)
    port = settings['port']
    return {
        'installed': engine_installed(paths),
        'engine': common.ENGINE_NAME,
        'engine_version': engine_version(paths),
        'gateway': {'running': gateway_live(port), 'url': f'http://127.0.0.1:{port}/', 'port': port},
        'providers': providers,
        'model': config.effective_model(settings, providers),
        'mode': settings['mode'],
        'channels': sorted(n for n, on in settings['channels'].items() if on),
        'autostart': bool(settings['autostart']),
    }


def cmd_status(args, paths):
    status = build_status(paths, verify=args.verify)
    if args.json:
        out(status)
        return 0
    print(f'Amerika Agent {__version__}  (engine {status["engine"]} {status["engine_version"] or "not installed"})')
    print(f'  gateway   {"running" if status["gateway"]["running"] else "stopped"}  {status["gateway"]["url"]}')
    print(f'  keys      ' + ', '.join(f'{p}: {"set" if ok else "not set"}' for p, ok in status['providers'].items()))
    print(f'  model     {status["model"] or "(no key yet)"}')
    print(f'  mode      {status["mode"]}')
    print(f'  channels  {", ".join(status["channels"]) or "none (all off)"}')
    print(f'  autostart {"on" if status["autostart"] else "off"}')
    return 0


# ------------------------------------------------------------------------------------------------------ key
PROVIDER_PROMPT = {'anthropic': 'Anthropic API key', 'openai': 'OpenAI API key'}


def read_secret_stdin(name):
    if sys.stdin.isatty():
        return getpass.getpass(f'{PROVIDER_PROMPT.get(name, name)} (input hidden): ')
    return sys.stdin.read()


def cmd_key(args, paths):
    if args.action == 'set':
        value = keyring.clean_value(read_secret_stdin(args.name))
        keyring.store(args.name, value)
        del value
        if args.name in common.PROVIDERS:
            verify_providers(paths)
        apply_config(paths)
        print(f'{args.name}: stored in the login keyring.')
        if service_active():
            if args.no_restart:
                print('The gateway is running; restart it to use the new key: amerika-agent restart')
            else:
                systemctl('restart', common.SERVICE_NAME)
                print('Gateway restarted.')
        return 0
    if args.action == 'clear':
        keyring.clear(args.name)
        if args.name in common.PROVIDERS:
            verify_providers(paths)
        apply_config(paths)
        print(f'{args.name}: removed from the login keyring.')
        if service_active() and not args.no_restart:
            systemctl('restart', common.SERVICE_NAME)
        return 0
    # status
    result = {n: keyring.present(n) for n in common.PROVIDERS}
    result['gateway_token'] = keyring.present(common.GATEWAY_TOKEN)
    result['channels'] = {n: all(keyring.present(s) for s in fields.values()) for n, fields in common.CHANNEL_SECRETS.items() if fields}
    verify_providers(paths)
    if args.json:
        out(result)
    else:
        for name in common.PROVIDERS:
            print(f'{name:10} {"set" if result[name] else "not set"}')
        print(f'{"gateway":10} token {"present" if result["gateway_token"] else "will be created on first start"}')
    return 0


# ------------------------------------------------------------------------------------------------------ lifecycle
def cmd_start(args, paths):
    require_engine(paths)
    _, providers, _ = apply_config(paths)
    if not any(providers.values()):
        err('note: no API key is stored yet. The gateway will start, but the agent cannot answer: amerika-agent key set anthropic|openai')
    systemctl('daemon-reload')
    systemctl('start', common.SERVICE_NAME)
    return wait_ready(paths, args.wait)


def wait_ready(paths, seconds):
    port = config.load_settings(paths)['port']
    deadline = time.time() + seconds
    while time.time() < deadline:
        if gateway_live(port):
            print(f'Gateway is up at http://127.0.0.1:{port}/')
            return 0
        time.sleep(0.5)
    err(f'the gateway did not open port {port} within {seconds}s; see: amerika-agent logs')
    return 1


def cmd_stop(args, paths):
    systemctl('stop', common.SERVICE_NAME)
    print('Gateway stopped.')
    return 0


def cmd_restart(args, paths):
    require_engine(paths)
    apply_config(paths)
    systemctl('restart', common.SERVICE_NAME)
    return wait_ready(paths, args.wait)


def set_autostart(paths, on, now=False):
    systemctl('daemon-reload')
    if on:
        require_engine(paths)
        apply_config(paths)
        systemctl('enable', common.SERVICE_NAME)
        if now:
            systemctl('start', common.SERVICE_NAME)
    else:
        systemctl('disable', common.SERVICE_NAME)
        if now:
            systemctl('stop', common.SERVICE_NAME)
    settings = config.load_settings(paths)
    settings['autostart'] = on
    config.save_settings(paths, settings)


def cmd_enable(args, paths):
    set_autostart(paths, True, args.now)
    print('Amerika Agent will start when you log in.' + ('' if args.now else ' (Not started now: amerika-agent start)'))
    return 0


def cmd_disable(args, paths):
    set_autostart(paths, False, args.now)
    print('Amerika Agent will no longer start at login.')
    return 0


def cmd_run(args, paths):
    """Foreground gateway (what the systemd unit runs). Replaces this process with the engine."""
    require_engine(paths)
    if not paths.openclaw_config.exists():
        apply_config(paths)
    else:
        keyring.ensure_gateway_token()
        config.ensure_resolver(paths)
        config.seed_workspace(paths)
    for d in (paths.state_dir, paths.state_dir / 'home'):
        d.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.state_dir, 0o700)
    cmd = engine_cmd(paths, 'gateway', 'run')
    sys.stdout.flush()
    os.execve(cmd[0], cmd, engine_env(paths))


# ------------------------------------------------------------------------------------------------------ config
CONFIG_KEYS = ('model', 'mode', 'autostart', 'port', 'linux-node')


def parse_bool(text):
    t = str(text).strip().lower()
    if t in ('1', 'true', 'on', 'yes', 'enable', 'enabled'):
        return True
    if t in ('0', 'false', 'off', 'no', 'disable', 'disabled'):
        return False
    raise AgentError(f'expected on/off, got {text!r}')


def config_view(paths):
    s = config.load_settings(paths)
    providers = read_providers_cache(paths)
    return {'model': s['model'], 'effective_model': config.effective_model(s, providers), 'mode': s['mode'],
            'autostart': s['autostart'], 'port': s['port'], 'linux-node': s['linux_node']}


def cmd_config(args, paths):
    if args.action == 'get':
        view = config_view(paths)
        if args.key is None:
            out(view) if args.json else [print(f'{k}={v}') for k, v in view.items()]
            return 0
        if args.key not in view:
            raise AgentError(f'unknown key {args.key!r} (known: {", ".join(CONFIG_KEYS)})')
        value = view[args.key]
        if args.key == 'model' and value is None:
            value = view['effective_model']
        out({args.key: value}) if args.json else print('' if value is None else str(value).lower() if isinstance(value, bool) else value)
        return 0
    if args.action == 'set':
        key, value = args.key, args.value
        if key not in CONFIG_KEYS:
            raise AgentError(f'unknown key {key!r} (known: {", ".join(CONFIG_KEYS)})')
        if key == 'autostart':
            set_autostart(paths, parse_bool(value), False)
            print(f'autostart = {"on" if parse_bool(value) else "off"}')
            return 0
        s = config.load_settings(paths)
        if key == 'model':
            s['model'] = None if value in ('default', 'auto', '') else value
        elif key == 'mode':
            s['mode'] = value
        elif key == 'port':
            try:
                s['port'] = int(value)
            except ValueError:
                raise AgentError('port must be a number')
        elif key == 'linux-node':
            s['linux_node'] = parse_bool(value)
        config.save_settings(paths, s)
        apply_config(paths)
        print(f'{key} = {value}')
        if service_active():
            print('The gateway is running. Most changes apply live; if something looks stale: amerika-agent restart')
        return 0
    if args.action == 'apply':
        apply_config(paths)
        return 0
    if args.action == 'show':
        if not paths.openclaw_config.exists():
            apply_config(paths)
        print(paths.openclaw_config.read_text(), end='')
        return 0
    if args.action == 'validate':
        require_engine(paths)
        apply_config(paths)
        ok, text = config.validate_with_engine(paths)
        print(text)
        return 0 if ok else 1
    raise AgentError('unknown config action')


# ------------------------------------------------------------------------------------------------------ channels
CHANNEL_WARNING = (
    'Channels let other people (or bots) send messages that reach your agent. Amerika Agent only answers senders you have '
    'approved (pairing is required), but a chat account is still an inbound path onto this computer. Leave channels off '
    'unless you need them.')


def cmd_channels(args, paths):
    s = config.load_settings(paths)
    if args.action == 'list':
        rows = []
        for name, fields in common.CHANNEL_SECRETS.items():
            rows.append({'name': name, 'enabled': bool(s['channels'].get(name)),
                         'secrets': {sec: keyring.present(sec) for sec in fields.values()}})
        if args.json:
            out(rows)
        else:
            for r in rows:
                have = ', '.join(f'{k}: {"set" if v else "missing"}' for k, v in r['secrets'].items())
                print(f'{r["name"]:10} {"ON " if r["enabled"] else "off"}  {have}')
        return 0
    name = args.name
    if name not in common.CHANNEL_SECRETS:
        raise AgentError(f'unknown channel {name!r} (known: {", ".join(common.CHANNEL_SECRETS)})')
    on = args.action == 'enable'
    s['channels'][name] = on
    config.save_settings(paths, s)
    apply_config(paths)
    if on:
        print(CHANNEL_WARNING, file=sys.stderr)
        missing = [sec for sec in common.CHANNEL_SECRETS[name].values() if not keyring.present(sec)]
        if missing:
            print(f'{name} enabled. It still needs credentials; store them with: amerika-agent key set {missing[0]}')
        else:
            print(f'{name} enabled.')
    else:
        print(f'{name} disabled.')
    if service_active():
        print('Restart the gateway to apply: amerika-agent restart')
    return 0


# ------------------------------------------------------------------------------------------------------ models
def engine_models(paths, provider):
    if not engine_installed(paths):
        return []
    try:
        r = common.run(engine_cmd(paths, 'models', 'list', '--all', '--provider', provider, '--json'), env=engine_env(paths), timeout=40)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return []
    items = data.get('models', data) if isinstance(data, dict) else data
    ids = []
    for item in items if isinstance(items, list) else []:
        ident = item.get('key') or item.get('id') if isinstance(item, dict) else item
        if isinstance(ident, str):
            ids.append(ident if '/' in ident else f'{provider}/{ident}')
    return ids


def cmd_models(args, paths):
    providers = [args.provider] if args.provider else list(common.PROVIDERS)
    result = {}
    for p in providers:
        entries = [{'id': i, 'description': d, 'source': 'static'} for i, d in common.STATIC_MODELS[p]]
        known = {e['id'] for e in entries}
        if not args.static:
            for ident in engine_models(paths, p):
                if ident not in known:
                    entries.append({'id': ident, 'description': '', 'source': 'engine'})
                    known.add(ident)
        for e in entries:
            e['default'] = e['id'] == common.DEFAULT_MODELS[p]
        result[p] = entries
    if args.json:
        out(result)
    else:
        for p, entries in result.items():
            print(f'{p}:')
            for e in entries:
                print(f'  {e["id"]}' + ('  [default]' if e['default'] else '') + (f'  {e["description"]}' if e['description'] else ''))
    return 0


# ------------------------------------------------------------------------------------------------------ ask
def extract_reply(stdout):
    """Pull the assistant's text out of `openclaw agent --json` output, whatever envelope version produced it."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout.strip(), None

    def texts(node):
        if isinstance(node, dict):
            if isinstance(node.get('final'), str) and node['final'].strip():
                return [node['final']]
            payloads = node.get('payloads')
            if isinstance(payloads, list):
                found = [p['text'] for p in payloads if isinstance(p, dict) and isinstance(p.get('text'), str) and p['text'].strip()]
                if found:
                    return found
            for key in ('result', 'response', 'reply'):
                if key in node:
                    found = texts(node[key])
                    if found:
                        return found
            if isinstance(node.get('text'), str):
                return [node['text']]
        return []
    found = texts(data)
    error = None
    if isinstance(data, dict):
        e = data.get('error')
        error = e.get('message') if isinstance(e, dict) else (e if isinstance(e, str) else None)
    return '\n\n'.join(found) if found else '', error


def cmd_ask(args, paths):
    require_engine(paths)
    s = config.load_settings(paths)
    if not port_open(s['port']):
        raise AgentError('the gateway is not running. Start it with: amerika-agent start')
    text = ' '.join(args.text) if args.text else sys.stdin.read()
    if not text.strip():
        raise AgentError('nothing to ask')
    fd, tmp = tempfile.mkstemp(prefix='ask-', suffix='.txt', dir=str(paths.state_dir))   # 0600; keeps the prompt out of argv
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
        cmd = engine_cmd(paths, 'agent', '--message-file', tmp, '--json', '--session-key', args.session, '--timeout', str(args.timeout))
        if args.model:
            cmd += ['--model', args.model]
        r = common.run(cmd, env=engine_env(paths), timeout=args.timeout + 30)
    except subprocess.TimeoutExpired:
        raise AgentError(f'no answer within {args.timeout} seconds')
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    reply, error = extract_reply(r.stdout)
    if args.json:
        out({'ok': r.returncode == 0 and not error, 'reply': reply, 'error': error})
    elif reply:
        print(reply)
    if r.returncode != 0 or error:
        err(error or (r.stderr.strip().splitlines() or ['the agent run failed'])[-1])
        return 1
    return 0


# ------------------------------------------------------------------------------------------------------ dashboard
def cmd_dashboard_url(args, paths):
    require_engine(paths)
    s = config.load_settings(paths)
    if not port_open(s['port']):
        raise AgentError('the gateway is not running. Start it with: amerika-agent start')
    base = f'http://127.0.0.1:{s["port"]}/'
    if not args.bootstrap:
        print(base)
        return 0
    if sys.stdout.isatty():
        raise AgentError('browser bootstrap links are available only to the Agent window, not terminal output')
    try:
        r = common.run(engine_cmd(paths, 'dashboard', '--json'), env=engine_env(paths), timeout=40)
        data = json.loads(r.stdout) if r.returncode == 0 else {}
        url = data.get('browserUrl') if isinstance(data, dict) else None
    except (subprocess.TimeoutExpired, ValueError, OSError):
        url = None
    # Never fall back to putting the shared gateway token in a URL.
    if not isinstance(url, str) or not url.startswith(base + '#') or 'token=' in url:
        raise AgentError('the gateway could not issue a one-time browser handoff; run amerika-agent doctor')
    print(url)
    return 0


# ------------------------------------------------------------------------------------------------------ logs
def cmd_logs(args, paths):
    if shutil.which('journalctl'):
        cmd = ['journalctl', '--user', '-u', common.SERVICE_NAME, '-n', str(args.lines), '--no-pager', '-o', 'short-iso']
        if args.follow:
            cmd.append('-f')
        rc = subprocess.call(cmd)
        if rc == 0:
            return 0
    log_dir = paths.state_dir / 'logs'
    files = sorted(log_dir.glob('*.log')) if log_dir.is_dir() else []
    if not files:
        err('no logs yet')
        return 1
    return subprocess.call(['tail', '-n', str(args.lines), *(['-f'] if args.follow else []), str(files[-1])])


# ------------------------------------------------------------------------------------------------------ doctor
def node_ok():
    try:
        r = common.run([common.NODE_BIN, '--version'], timeout=10)
        parts = tuple(int(x) for x in r.stdout.strip().lstrip('v').split('.')[:3])
        return (24, 16, 0) <= parts < (25, 0, 0), r.stdout.strip()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False, 'not found'


def run_doctor(paths):
    checks = []

    def add(name, status, detail=''):
        checks.append({'name': name, 'status': status, 'detail': detail})

    installed = engine_installed(paths)
    add('engine', 'ok' if installed else 'fail', f'openclaw {engine_version(paths)} at {paths.engine_entry().parent}' if installed else 'not installed')
    ok, ver = node_ok()
    add('node', 'ok' if ok else 'fail', f'{ver} (OpenClaw needs >= 24.16 and < 25)')
    add('secret-tool', 'ok' if shutil.which(common.SECRET_TOOL) else 'fail', 'libsecret-tools' if shutil.which(common.SECRET_TOOL) else 'package libsecret-tools is missing')
    try:
        keys = {p: keyring.present(p) for p in common.PROVIDERS}
        add('keyring', 'ok', 'readable')
        add('api key', 'ok' if any(keys.values()) else 'warn', ', '.join(f'{p}: {"set" if v else "not set"}' for p, v in keys.items()))
    except AgentError as error:
        add('keyring', 'fail', str(error))
    try:
        settings = config.load_settings(paths)
        add('settings', 'ok', str(paths.settings) if paths.settings.exists() else 'defaults (no settings file yet)')
    except AgentError as error:
        settings = None
        add('settings', 'fail', str(error))
    add('mcp wrapper', 'ok' if os.access(common.MCP_COMMAND, os.X_OK) else 'fail', common.MCP_COMMAND)
    add('amerika-mcp', 'ok' if shutil.which('amerika-mcp') or os.access('/usr/bin/amerika-mcp', os.X_OK) else 'fail', 'from amerika-desktop-shell')
    sock = paths.runtime_dir / 'control.sock'
    add('amerika shell broker', 'ok' if sock.exists() else 'warn', 'running' if sock.exists() else 'Amerika Shell is not running; desktop tools will be unavailable')
    unit_present = any(Path(d, common.SERVICE_NAME).exists() for d in ('/usr/lib/systemd/user', '/lib/systemd/user', str(paths.unit_dir)))
    add('systemd unit', 'ok' if unit_present else 'fail', common.SERVICE_NAME)
    if settings:
        add('gateway', 'ok' if port_open(settings['port']) else 'warn',
            f'listening on 127.0.0.1:{settings["port"]}' if port_open(settings['port']) else 'not running (amerika-agent start)')
        if installed and ok:
            if not paths.openclaw_config.exists():
                add('openclaw config', 'warn', 'not generated yet (created on first start)')
            else:
                try:
                    valid, text = config.validate_with_engine(paths)
                    add('openclaw config', 'ok' if valid else 'fail', text.splitlines()[0] if text else '')
                except subprocess.TimeoutExpired:
                    add('openclaw config', 'warn', 'validation timed out')
    if installed and ok:   # OpenClaw's own read-only lint; never --fix
        try:
            r = common.run(engine_cmd(paths, 'doctor', '--lint', '--json'), env=engine_env(paths), timeout=90)
            findings = None
            try:
                findings = json.loads(r.stdout)
            except ValueError:
                pass
            if r.returncode == 0:
                add('openclaw doctor', 'ok', 'no findings')
            else:
                text = (r.stdout or r.stderr).strip().splitlines()
                add('openclaw doctor', 'warn', (text[0] if text else f'exit {r.returncode}')[:200] if findings is None else f'{len(findings) if isinstance(findings, list) else "some"} finding(s); run: openclaw doctor --lint')
        except (subprocess.TimeoutExpired, OSError):
            add('openclaw doctor', 'warn', 'did not finish')
    return checks


def cmd_doctor(args, paths):
    checks = run_doctor(paths)
    failed = any(c['status'] == 'fail' for c in checks)
    if args.json:
        out({'ok': not failed, 'checks': checks})
    else:
        marks = {'ok': 'ok  ', 'warn': 'warn', 'fail': 'FAIL'}
        for c in checks:
            print(f'[{marks[c["status"]]}] {c["name"]:22} {c["detail"]}')
    return 1 if failed else 0


# ------------------------------------------------------------------------------------------------------ activity
def cmd_activity(args, paths):
    from . import activity
    return activity.main(paths, once=args.once)


# ------------------------------------------------------------------------------------------------------ parser
def build_parser():
    p = argparse.ArgumentParser(prog='amerika-agent', description='Amerika Agent: the OpenClaw-based agent of Amerika OS.')
    p.add_argument('--version', action='version', version=f'amerika-agent {__version__}')
    sub = p.add_subparsers(dest='cmd', required=True, metavar='command')

    s = sub.add_parser('status', help='show state (use --json for scripts)')
    s.add_argument('--json', action='store_true')
    s.add_argument('--verify', action='store_true', help='read the keyring instead of the cached key state (may prompt to unlock it)')
    s.set_defaults(fn=cmd_status)

    k = sub.add_parser('key', help='manage API keys in the login keyring (values are read from stdin only)')
    ks = k.add_subparsers(dest='action', required=True)
    names = [n for n in common.SECRET_NAMES if n != common.GATEWAY_TOKEN]
    for action in ('set', 'clear'):
        x = ks.add_parser(action)
        x.add_argument('name', choices=names)
        x.add_argument('--no-restart', action='store_true')
    x = ks.add_parser('status')
    x.add_argument('--json', action='store_true')
    k.set_defaults(fn=cmd_key)

    for name, fn, helptext in (('start', cmd_start, 'start the gateway (user service)'), ('restart', cmd_restart, 'restart the gateway')):
        x = sub.add_parser(name, help=helptext)
        x.add_argument('--wait', type=int, default=60, help='seconds to wait for the port')
        x.set_defaults(fn=fn)
    sub.add_parser('stop', help='stop the gateway').set_defaults(fn=cmd_stop)
    for name, fn, helptext in (('enable', cmd_enable, 'start the gateway at login'), ('disable', cmd_disable, 'do not start the gateway at login')):
        x = sub.add_parser(name, help=helptext)
        x.add_argument('--now', action='store_true', help='also start/stop it now')
        x.set_defaults(fn=fn)
    sub.add_parser('run', help='run the gateway in the foreground (used by the systemd unit)').set_defaults(fn=cmd_run)

    c = sub.add_parser('config', help='get/set model, mode, autostart (port, linux-node)')
    cs = c.add_subparsers(dest='action', required=True)
    x = cs.add_parser('get')
    x.add_argument('key', nargs='?')
    x.add_argument('--json', action='store_true')
    x = cs.add_parser('set')
    x.add_argument('key')
    x.add_argument('value')
    for a in ('apply', 'show', 'validate'):
        cs.add_parser(a)
    c.set_defaults(fn=cmd_config)

    ch = sub.add_parser('channels', help='chat channels (all off by default)')
    chs = ch.add_subparsers(dest='action', required=True)
    x = chs.add_parser('list')
    x.add_argument('--json', action='store_true')
    for a in ('enable', 'disable'):
        x = chs.add_parser(a)
        x.add_argument('name')
    ch.set_defaults(fn=cmd_channels)

    m = sub.add_parser('models', help='list model ids')
    m.add_argument('--provider', choices=common.PROVIDERS)
    m.add_argument('--json', action='store_true')
    m.add_argument('--static', action='store_true', help='do not ask the engine')
    m.set_defaults(fn=cmd_models)

    a = sub.add_parser('ask', help='one-shot question through the running gateway')
    a.add_argument('text', nargs='*', help='the question (or pipe it on stdin)')
    a.add_argument('--model')
    a.add_argument('--session', default='agent:main:amerika-cli')
    a.add_argument('--timeout', type=int, default=300)
    a.add_argument('--json', action='store_true')
    a.set_defaults(fn=cmd_ask)

    dashboard = sub.add_parser('dashboard-url', help='print the credential-free local Control UI URL')
    dashboard.add_argument('--bootstrap', action='store_true', help=argparse.SUPPRESS)
    dashboard.set_defaults(fn=cmd_dashboard_url)
    d = sub.add_parser('doctor', help='check the installation')
    d.add_argument('--json', action='store_true')
    d.set_defaults(fn=cmd_doctor)
    lg = sub.add_parser('logs', help='gateway log')
    lg.add_argument('-n', '--lines', type=int, default=100)
    lg.add_argument('-f', '--follow', action='store_true')
    lg.set_defaults(fn=cmd_logs)
    ac = sub.add_parser('activity', help='publish agent activity for the shell bar (used by the activity unit)')
    ac.add_argument('--once', action='store_true', help='connect, write one snapshot, exit')
    ac.set_defaults(fn=cmd_activity)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    paths = common.Paths()
    try:
        return args.fn(args, paths) or 0
    except AgentError as error:
        err(str(error))
        return 1
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0


if __name__ == '__main__':
    sys.exit(main())
