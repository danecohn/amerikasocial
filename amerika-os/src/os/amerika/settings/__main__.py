import sys

from . import pageindex


def main(argv):
    if '--list' in argv:  # JSON for the agent; needs no display
        print(pageindex.list_json())
        return 0
    if '--classic' in argv:  # recovery from a text console: back to the classic desktop (needs no display)
        from .. import common
        from ..shell import home
        common.save_settings(home.apply_style(common.load_settings(), 'off'))
        print('Classic desktop restored: home mode off, dock on, classic top bar.')
        return 0
    if '--help' in argv or '-h' in argv:
        print('usage: amerika-settings [--list] [--classic] [PAGE]\n  PAGE is one of: ' + ', '.join(pageindex.page_ids()))
        return 0
    from .app import main as run
    return run()


sys.exit(main(sys.argv[1:]))
