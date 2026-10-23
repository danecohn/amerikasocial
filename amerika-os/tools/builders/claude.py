"""amerika-claude: Claude skills, Claude Code plugin and the installer CLI. Nothing touches any home folder at install time."""
import shutil


META_DEPENDS = ["amerika-claude"]  # the Claude-first OS ships its skills; installing them into ~/.claude is a separate opt-in


def register(b):
    def build():
        src = b.OS / 'claude'
        p = b.Pkg('amerika-claude', b.DE_VERSION,
                  'Skills and plugin that let Claude operate AltStack Desktop\nEleven skills, slash commands and the amerika MCP registration for '
                  'Claude Desktop and Claude Code, plus the amerika-claude command to install them (with backup and undo), export them as '
                  'zips for the Skills upload, and check the setup.\nNothing is installed into your home folder until you run '
                  '"amerika-claude install" or press the button in Settings > AI.',
                  arch='all', depends=f'amerika-desktop-shell (>= {b.DE_VERSION}), python3', title='Amerika Claude Skills', category='System')
        ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
        shutil.copytree(src / 'amerika_claude', p.path('/usr/lib/python3/dist-packages/amerika_claude'), ignore=ignore)
        shutil.copytree(src / 'plugin', p.path('/usr/share/amerika-claude/plugin'), ignore=ignore)
        p.copy(src / 'AMERIKA.md', '/usr/share/amerika-claude/AMERIKA.md')
        p.copy(src / 'bin/amerika-claude', '/usr/bin/amerika-claude', 0o755)
        p.copy(b.ROOT / 'docs/claude-os/skills.md', '/usr/share/doc/amerika-claude/skills.md')
        p.copyright('Amerika Claude skills, Copyright AltStack LLC, GPL-3.0-only.\n')
        return p
    return {'amerika-claude': build}
