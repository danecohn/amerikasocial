"""Registers the Amerika system MCP server with the Claude and ChatGPT/Codex desktop apps, and removes it again.

Only the user does this, from Amerika Settings > AI. Existing config content is preserved; Claude's file is backed up
once, and the Codex entry sits between marker comments so it can be removed exactly.
"""
import json
import os
import re
from pathlib import Path

MCP_COMMAND = os.environ.get('AMERIKA_MCP_COMMAND', '/usr/bin/amerika-mcp')
MARK_START = '# >>> amerika-os (managed) >>>'
MARK_END = '# <<< amerika-os (managed) <<<'


def claude_path():
    return Path(os.environ.get('AMERIKA_CLAUDE_CONFIG') or Path.home() / '.config/Claude/claude_desktop_config.json')


def codex_path():
    return Path(os.environ.get('AMERIKA_CODEX_CONFIG') or Path.home() / '.codex/config.toml')


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def status():
    out = {'claude': False, 'chatgpt': False}
    try:
        out['claude'] = 'amerika' in _read_json(claude_path()).get('mcpServers', {})
    except (OSError, ValueError):
        pass
    try:
        out['chatgpt'] = MARK_START in codex_path().read_text()
    except OSError:
        pass
    return out


def connect_claude():
    path = claude_path()
    data = _read_json(path)  # raises ValueError on malformed JSON: we never overwrite a file we cannot read
    if path.exists():
        backup = path.with_name(path.name + '.amerika-backup')
        if not backup.exists():
            backup.write_text(path.read_text())
    data.setdefault('mcpServers', {})['amerika'] = {'command': MCP_COMMAND, 'args': ['--client', 'claude']}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def disconnect_claude():
    path = claude_path()
    data = _read_json(path)
    if 'amerika' in data.get('mcpServers', {}):
        del data['mcpServers']['amerika']
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)


BLOCK = f'''{MARK_START}
[mcp_servers.amerika]
command = "{{command}}"
args = ["--client", "chatgpt"]
{MARK_END}
'''


def connect_chatgpt():
    path = codex_path()
    text = path.read_text() if path.exists() else ''
    if MARK_START in text:
        return
    if re.search(r'^\[mcp_servers\.amerika\]', text, re.M):
        raise ValueError('an "amerika" MCP server is already configured by hand; remove it first')
    path.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith('\n'):
        text += '\n'
    path.write_text(text + '\n' + BLOCK.replace('{command}', MCP_COMMAND))


def disconnect_chatgpt():
    path = codex_path()
    if not path.exists():
        return
    text = path.read_text()
    new = re.sub(rf'\n?{re.escape(MARK_START)}.*?{re.escape(MARK_END)}\n?', '\n', text, flags=re.S)
    if new != text:
        path.write_text(new)


# ---- claude-os skills block: Claude skills and plugin (explicit user action only; see src/os/claude/amerika_claude/core.py) ----
def _skills_core():
    try:
        from amerika_claude import core
    except ImportError:
        return None
    return core


def skills_status():
    """Settings UI: what is installed. `available` is False when the amerika-claude package is not installed."""
    core = _skills_core()
    if core is None:
        return {'available': False, 'installed': False, 'installed_skills': [], 'plugin_installed': False,
                'message': 'Install the amerika-claude package to get the Claude skills.'}
    return core.status()


def install_skills(skills=True, plugin=True):
    """Install the skills (and plugin marketplace) with backup and manifest. Raises ValueError with a user-fit message."""
    core = _skills_core()
    if core is None:
        raise ValueError('The amerika-claude package is not installed.')
    try:
        return core.install(skills=skills, plugin=plugin)
    except core.InstallError as error:
        raise ValueError(str(error)) from error


def remove_skills(force=False):
    core = _skills_core()
    if core is None:
        raise ValueError('The amerika-claude package is not installed.')
    return core.remove(force=force)


def export_skills(directory):
    """Write one zip per skill plus custom-instructions.md into `directory` (for Claude Desktop's Skills upload)."""
    core = _skills_core()
    if core is None:
        raise ValueError('The amerika-claude package is not installed.')
    try:
        return core.export(directory)
    except core.InstallError as error:
        raise ValueError(str(error)) from error
