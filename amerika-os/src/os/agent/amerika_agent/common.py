"""Paths, constants and small helpers shared by the amerika-agent CLI, the secret helper and the activity feed.

Everything user-specific lives in XDG directories of its own; nothing here ever reads or writes ~/.openclaw.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ENGINE_ENV_DROP = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'OPENAI_API_KEY', 'OPENCLAW_GATEWAY_TOKEN',
                   'OPENCLAW_GATEWAY_PASSWORD', 'OPENCLAW_PROFILE', 'OPENCLAW_CONFIG', 'OPENCLAW_WORKSPACE_DIR')
def clean_engine_env(paths):
    env = {k: v for k, v in os.environ.items() if k not in ENGINE_ENV_DROP and k != 'LD_PRELOAD'}
    env.update(paths.engine_env())
    return env


ENGINE_NAME = 'openclaw'
SERVICE_NAME = 'amerika-agent-gateway.service'
NODE_SERVICE_NAME = 'amerika-agent-node.service'
ACTIVITY_SERVICE_NAME = 'amerika-agent-activity.service'

DEFAULT_PORT = 18790          # upstream's 18789 is left free for anybody who runs their own OpenClaw
MODES = ('ask', 'safe', 'trusted')
DEFAULT_MODE = 'ask'

PROVIDERS = ('anthropic', 'openai')
DEFAULT_MODELS = {'anthropic': 'anthropic/claude-opus-5-5', 'openai': 'openai/gpt-5.5'}
# Offline defaults from the pinned engine's provider docs. The installed engine
# supplies the full catalogue; this list makes no availability or pricing claims.
STATIC_MODELS = {p: [(ident, 'Default')] for p, ident in DEFAULT_MODELS.items()}
MODEL_RE = re.compile(r'^(anthropic|openai)/[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$')

# secret ids understood by amerika-agent-secret (also the `name` attribute in the Secret Service)
GATEWAY_TOKEN = 'gateway-token'
CHANNEL_SECRETS = {   # channel -> {config field: secret name}
    'telegram': {'botToken': 'channel-telegram'},
    'discord': {'token': 'channel-discord'},
    'slack': {'botToken': 'channel-slack-bot', 'appToken': 'channel-slack-app'},
    'whatsapp': {},
    'signal': {},
}
SECRET_NAMES = tuple(PROVIDERS) + (GATEWAY_TOKEN,) + tuple(n for c in CHANNEL_SECRETS.values() for n in c.values())
SECRET_NAME_RE = re.compile(r'^[a-z][a-z0-9-]{0,63}$')

ENGINE_DIR = Path(os.environ.get('AMERIKA_AGENT_ENGINE', '/opt/amerika/agent'))
NODE_BIN = os.environ.get('AMERIKA_AGENT_NODE', '/usr/bin/node')
MCP_COMMAND = os.environ.get('AMERIKA_AGENT_MCP', '/usr/libexec/amerika/amerika-mcp-wrapper')
SECRET_BIN = os.environ.get('AMERIKA_AGENT_SECRET_BIN', '/usr/bin/amerika-agent-secret')
SECRET_TOOL = os.environ.get('AMERIKA_AGENT_SECRET_TOOL', 'secret-tool')
SHARE = Path(os.environ.get('AMERIKA_AGENT_SHARE', '/usr/share/amerika-agent'))


def xdg(env, fallback):
    return Path(os.environ.get(env) or Path.home() / fallback)


class Paths:
    """All per-user locations, resolved lazily so tests can point HOME / XDG_* somewhere else."""

    def __init__(self):
        self.config_dir = xdg('XDG_CONFIG_HOME', '.config') / 'amerika-agent'
        self.state_dir = xdg('XDG_STATE_HOME', '.local/state') / 'amerika-agent'
        self.data_dir = xdg('XDG_DATA_HOME', '.local/share') / 'amerika-agent'
        self.libexec_dir = xdg('XDG_DATA_HOME', '.local/share') / 'amerika-agent' / 'libexec'
        self.settings = self.config_dir / 'settings.json'
        self.openclaw_config = self.config_dir / 'openclaw.json'
        self.workspace = self.data_dir / 'workspace'
        self.resolver = self.libexec_dir / 'secret-resolver'
        self.unit_dir = xdg('XDG_CONFIG_HOME', '.config') / 'systemd' / 'user'
        runtime = os.environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
        self.runtime_dir = Path(runtime) / 'amerika'
        self.activity_file = self.runtime_dir / 'agent-activity.json'
        self.activity_socket = self.runtime_dir / 'agent-activity.sock'

    def engine_entry(self):
        return ENGINE_DIR / 'node_modules' / 'openclaw' / 'openclaw.mjs'

    def engine_env(self):
        """Environment that points OpenClaw at Amerika's directories and away from ~/.openclaw."""
        env = {
            'OPENCLAW_STATE_DIR': str(self.state_dir),
            'OPENCLAW_CONFIG_PATH': str(self.openclaw_config),
            'OPENCLAW_NO_AUTO_UPDATE': '1',
            'OPENCLAW_HOME': str(self.state_dir / 'home'),
        }
        return env


class AgentError(Exception):
    """A problem to show to the user without a traceback."""


def atomic_write(path, text, mode=0o600):
    """Write a file in one step with the given mode (never world readable by default)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def run(args, **kw):
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    return subprocess.run([str(a) for a in args], **kw)
