import sys

from . import pageindex


def main(argv):
    if '--list' in argv:  # JSON for the agent; needs no display
        print(pageindex.list_json())
        return 0
    if '--help' in argv or '-h' in argv:
        print('usage: amerika-settings [--list] [PAGE]\n  PAGE is one of: ' + ', '.join(pageindex.page_ids()))
        return 0
    from .app import main as run
    return run()


sys.exit(main(sys.argv[1:]))
