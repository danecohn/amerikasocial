"""Settings and the OpenClaw configuration generator.

~/.config/amerika-agent/settings.json   what the user chose (model, mode, autostart, channels...). Small, validated.
~/.config/amerika-agent/openclaw.json   GENERATED from the settings plus which secrets exist. Never hand-edited, never
                                        contains a credential: every secret is a SecretRef that makes OpenClaw run
                                        `amerika-agent-secret` (keyring lookup).

The generator is a pure function (build_config) so it can be tested without OpenClaw, a keyring or systemd.
"""
import copy
import json
import os
import shutil
from pathlib import Path

from . import common
from .common import AgentError

SETTINGS_VERSION = 1
SECRET_PROVIDER = 'amerika'     # name of the exec provider under secrets.providers

DEFAULT_SETTINGS = {
    'version': SETTINGS_VERSION,
    'model': None,              # None: the default model of the first provider that has a key
    'mode': common.DEFAULT_MODE,
    'autostart': False,
    'port': common.DEFAULT_PORT,
    'channels': {},             # name -> bool; everything is off unless listed here as true
    'linux_node': False,        # desktop notifications / camera / location through the OpenClaw node host
    'studio_tools': False,      # studio-core: register the amerika-studio MCP server (Render/Engine/Sprite/Box tools)
}

# Amerika permission mode -> OpenClaw policy (see docs/agent/README.md, "Permission modes").
#   exec             tools.exec  `mode` ("ask": allow-listed commands run, anything else asks a human; "auto": the native
#                    reviewer decides, a human is asked when it is unsure). OpenClaw refuses `mode` together with
#                    `security`/`ask`, so the strictest policy ("every command asks, even allow-listed ones") is spelled
#                    as the security/ask pair.
#   workspace_only   tools.fs.workspaceOnly   file tools stay inside the agent workspace
MODE_POLICY = {
    'ask': {'exec': {'security': 'allowlist', 'ask': 'always'}, 'workspace_only': True},
    'safe': {'exec': {'mode': 'ask'}, 'workspace_only': True},
    'trusted': {'exec': {'mode': 'auto'}, 'workspace_only': False},
}

STUDIO_MCP_COMMAND = os.environ.get('AMERIKA_AGENT_STUDIO_MCP', '/usr/bin/amerika-studio-mcp')   # studio-core
CHANNEL_DM_POLICY = 'pairing'   # unknown senders must be approved by the user first


# ---------------------------------------------------------------------------------------------------------- settings
def validate_settings(raw):
    """Return a clean copy of the settings or raise AgentError. Unknown keys are dropped, bad values are refused."""
    if not isinstance(raw, dict):
        raise AgentError('settings must be a JSON object')
    s = copy.deepcopy(DEFAULT_SETTINGS)
    for key in ('model', 'mode', 'autostart', 'port', 'channels', 'linux_node', 'studio_tools'):
        if key in raw:
            s[key] = raw[key]
    if s['model'] is not None and (not isinstance(s['model'], str) or not common.MODEL_RE.match(s['model'])):
        raise AgentError(f'invalid model {s["model"]!r}: expected anthropic/<id> or openai/<id>')
    if s['mode'] not in common.MODES:
        raise AgentError(f'invalid mode {s["mode"]!r}: expected one of {", ".join(common.MODES)}')
    for key in ('autostart', 'linux_node', 'studio_tools'):
        if not isinstance(s[key], bool):
            raise AgentError(f'{key} must be true or false')
    if isinstance(s['port'], bool) or not isinstance(s['port'], int) or not 1024 <= s['port'] <= 65535:
        raise AgentError('port must be an integer between 1024 and 65535')
    if not isinstance(s['channels'], dict):
        raise AgentError('channels must be an object')
    for name, on in s['channels'].items():
        if name not in common.CHANNEL_SECRETS:
            raise AgentError(f'unknown channel {name!r} (known: {", ".join(common.CHANNEL_SECRETS)})')
        if not isinstance(on, bool):
            raise AgentError(f'channel {name} must be true or false')
    s['version'] = SETTINGS_VERSION
    return s


def load_settings(paths):
    raw = common.read_json(paths.settings, None)
    if raw is None:
        return copy.deepcopy(DEFAULT_SETTINGS)
    return validate_settings(raw)


def save_settings(paths, settings):
    settings = validate_settings(settings)
    common.atomic_write(paths.settings, json.dumps(settings, indent=2, sort_keys=True) + '\n', 0o600)
    sync_shell_mode(paths,settings['mode'])
    return settings


def effective_model(settings, providers):
    """The model that will be used: the chosen one, else the default of the first provider with a key, else None."""
    if settings.get('model'):
        return settings['model']
    for provider in common.PROVIDERS:
        if providers.get(provider):
            return common.DEFAULT_MODELS[provider]
    return None


def model_provider(model):
    return model.split('/', 1)[0] if model else None


# ---------------------------------------------------------------------------------------------------------- generator
def secret_ref(name):
    return {'source': 'exec', 'provider': SECRET_PROVIDER, 'id': name}


def build_config(settings, providers=None, channel_secrets=None, paths=None, resolver=None):
    """Build the OpenClaw configuration (a plain dict).

    settings         validated settings
    providers        {'anthropic': bool, 'openai': bool}: which API keys exist in the keyring
    channel_secrets  set of secret names (channel-telegram...) that exist in the keyring
    resolver         absolute path of the user-owned secret-resolver shim (OpenClaw insists the command is owned by the user)
    """
    settings = validate_settings(settings)
    paths = paths or common.Paths()
    providers = providers or {}
    channel_secrets = channel_secrets or set()
    resolver = str(resolver or paths.resolver)
    policy = MODE_POLICY[settings['mode']]
    model = effective_model(settings, providers)

    cfg = {
        'gateway': {
            'mode': 'local',
            'bind': 'loopback',
            'port': settings['port'],
            'auth': {'mode': 'token', 'token': secret_ref(common.GATEWAY_TOKEN),
                     'rateLimit': {'maxAttempts': 10, 'windowMs': 60000, 'lockoutMs': 300000}},
            'controlUi': {'enabled': True},
            'tailscale': {'mode': 'off'},
            'terminal': {'enabled': False},     # the Control UI would otherwise offer a host shell to the token holder
            'cliAgents': {'enabled': False},
            'reload': {'mode': 'hybrid'},
        },
        'secrets': {
            'providers': {SECRET_PROVIDER: {
                'source': 'exec',
                'command': resolver,
                'args': [],
                'jsonOnly': True,
                'trustedDirs': [str(Path(resolver).parent)],
                'passEnv': ['HOME', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'],
                'timeoutMs': 10000,
            }},
            'defaults': {'exec': SECRET_PROVIDER},
        },
        'models': {'providers': {}, 'catalogRefresh': {'enabled': False}},
        'agents': {'defaults': {
            'workspace': str(paths.workspace),
            'skipBootstrap': True,                      # Amerika seeds the workspace itself (see seed_workspace)
            'sandbox': {'mode': 'off'},                 # no Docker on a desktop; containment is the policy below
            'heartbeat': {'every': '0m'},               # no recurring background model calls: the user pays for every token
        }},
        'discovery': {'mdns': {'mode': 'off'}},         # do not advertise the gateway on the LAN
        'browser': {'enabled': False, 'allowSystemProfileImport': False},
        'tools': {
            'profile': 'full',
            # Native exec/fs/UI tools would bypass the broker's approvals and
            # Stop switch. Desktop and file changes must use Amerika MCP.
            'allow': ['amerika__*', 'group:memory', 'group:web', 'group:sessions'],
            'deny': ['group:runtime', 'group:fs', 'group:ui', 'group:nodes', 'group:automation'],
            'exec': dict(policy['exec']),
            'fs': {'workspaceOnly': policy['workspace_only']},
            'elevated': {'enabled': False},
        },
        'mcp': {'servers': {'amerika': {
            'command': common.MCP_COMMAND,
            'args': [],
            # OpenClaw starts stdio servers with a minimal environment; the broker socket is found through this variable
            'env': {'XDG_RUNTIME_DIR': str(paths.runtime_dir.parent)},
            'connectionTimeoutMs': 15000,
            'requestTimeoutMs': 140000,                 # the broker may wait up to ~2 minutes for the user to approve
        }}},
        'update': {'checkOnStart': False, 'auto': {'enabled': False}},   # updates arrive through APT
        'telemetry': {'enabled': False},
        'diagnostics': {'otel': {'enabled': False}},
        'channels': {},
        'plugins': {
            'load': {'paths': [str(common.SHARE / 'activity-plugin')]},
            'entries': {
                'amerika-activity': {'enabled': True},
                'linux-node': {'enabled': False},
                'mcp-relay': {'enabled': False},
            },
        },
    }

    if settings['studio_tools']:   # studio-core: Amerika Studio apps as agent tools; code-running tools ask in their own dialog
        cfg['mcp']['servers']['amerika-studio'] = {
            'command': STUDIO_MCP_COMMAND,
            'args': [],
            'env': {'XDG_RUNTIME_DIR': str(paths.runtime_dir.parent)},
            'connectionTimeoutMs': 15000,
            'requestTimeoutMs': 960000,                 # app.prompt and model tools may run for several minutes
        }
        cfg['tools']['allow'].append('amerika-studio__*')

    if providers.get('anthropic'):
        cfg['models']['providers']['anthropic'] = {'apiKey': secret_ref('anthropic')}
    if providers.get('openai'):
        # Keep API-key turns on OpenClaw's own runtime; the native Codex harness needs a Codex login and binary.
        cfg['models']['providers']['openai'] = {'apiKey': secret_ref('openai'), 'agentRuntime': {'id': 'openclaw'}}
    if not cfg['models']['providers']:
        del cfg['models']['providers']
    if model:
        cfg['agents']['defaults']['model'] = {'primary': model}

    for name, on in sorted(settings['channels'].items()):
        if not on:
            continue
        entry = {'enabled': True, 'dmPolicy': CHANNEL_DM_POLICY}
        for field, secret in common.CHANNEL_SECRETS[name].items():
            if secret in channel_secrets:
                entry[field] = secret_ref(secret)
        cfg['channels'][name] = entry
    if not cfg['channels']:
        del cfg['channels']

    if settings['linux_node']:
        cfg['plugins']['entries']['linux-node'] = {'enabled': True, 'config': {
            'notify': {'enabled': True}, 'camera': {'enabled': False}, 'location': {'enabled': False}}}
    if not cfg['plugins']['entries']:
        del cfg['plugins']
    return cfg


def render(cfg):
    return json.dumps(cfg, indent=2, sort_keys=False) + '\n'


def assert_no_secrets(text):
    """Defence in depth: refuse to write a config that looks like it holds a credential."""
    for pattern in ('sk-ant-', 'sk-proj-', 'xoxb-', 'xapp-'):
        if pattern in text:
            raise AgentError('refusing to write a configuration that contains something that looks like a key')


# ---------------------------------------------------------------------------------------------------------- files
def ensure_resolver(paths):
    """Install the user-owned secret resolver shim.

    OpenClaw only runs an exec secret provider whose command is a regular file (not a symlink) owned by the current user
    and not writable by others, so the root-owned /usr/bin/amerika-agent-secret cannot be named directly.
    The shim holds no secret; it just runs the packaged helper.
    """
    text = f'#!/bin/sh\nexec "{common.SECRET_BIN}" resolve\n'
    try:
        if paths.resolver.read_text() == text and (paths.resolver.stat().st_mode & 0o777) == 0o700 \
                and not paths.resolver.is_symlink() and paths.resolver.stat().st_uid == os.getuid():
            return paths.resolver
    except OSError:
        pass
    paths.libexec_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.libexec_dir, 0o700)
    if paths.resolver.is_symlink():
        paths.resolver.unlink()
    common.atomic_write(paths.resolver, text, 0o700)
    return paths.resolver


def template_dir():
    for candidate in (common.SHARE / 'workspace', Path(__file__).resolve().parent.parent / 'workspace'):
        if candidate.is_dir():
            return candidate
    raise AgentError('workspace templates are missing (is amerika-agent installed correctly?)')


BLOCK_BEGIN = '<!-- amerika:begin'
BLOCK_END = '<!-- amerika:end -->'


def _managed_block(text):
    start = text.find(BLOCK_BEGIN)
    end = text.find(BLOCK_END)
    if start < 0 or end < start:
        return None
    return start, end + len(BLOCK_END)


def seed_workspace(paths):
    """Create the workspace and install the Amerika prompt files.

    Files the user already has are left alone. AGENTS.md carries a managed block (between the amerika:begin / amerika:end
    markers) that describes the OS to the agent; it is refreshed on every update while everything outside it stays the user's.
    """
    paths.workspace.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.workspace, 0o700)
    written = []
    for src in sorted(template_dir().glob('*.md')):
        dst = paths.workspace / src.name
        template = src.read_text()
        if not dst.exists():
            text = template
        elif src.name == 'AGENTS.md':
            new_span, old_span = _managed_block(template), None
            current = dst.read_text()
            old_span = _managed_block(current)
            block = template[new_span[0]:new_span[1]]
            if old_span:
                text = current[:old_span[0]] + block + current[old_span[1]:]
            else:
                text = block + '\n\n' + current
            if text == current:
                continue
        else:
            continue
        common.atomic_write(dst, text, 0o600)
        written.append(src.name)
    return written


def write_config(paths, settings=None, providers=None, channel_secrets=None):
    """Generate, sanity-check and atomically write openclaw.json. Returns the config dict."""
    settings = validate_settings(settings if settings is not None else load_settings(paths))
    resolver = ensure_resolver(paths)
    cfg = build_config(settings, providers, channel_secrets, paths, resolver)
    text = render(cfg)
    assert_no_secrets(text)
    json.loads(text)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.config_dir, 0o700)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.state_dir, 0o700)
    seed_workspace(paths)
    common.atomic_write(paths.openclaw_config, text, 0o600)
    return cfg


def validate_with_engine(paths, timeout=60):
    """Ask OpenClaw itself whether the generated file is valid (`openclaw config validate`). Returns (ok, output)."""
    entry = paths.engine_entry()
    if not entry.exists():
        return None, f'engine not found at {entry}'
    env = common.clean_engine_env(paths)
    r = common.run([common.NODE_BIN, entry, 'config', 'validate'], env=env, timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def sync_shell_mode(paths, mode):
    """CLI and GTK use the same broker policy; preserve every unrelated setting."""
    if mode not in common.MODES:
        raise AgentError('invalid permission mode')
    path=paths.config_dir.parent/'amerika-os/settings.json'
    settings=common.read_json(path,{})
    if not isinstance(settings,dict) or not isinstance(settings.get('ai',{}),dict):
        raise AgentError('Amerika desktop settings are unreadable; policy was not changed')
    settings.setdefault('ai',{})['mode']=mode
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    common.atomic_write(path,json.dumps(settings,indent=2)+'\n',0o600)
