"""Amerika Render: an AI modelling assistant inside Blender.

Powered by Blender (GPL-3.0-or-later). Blender is a trademark of the Blender Foundation; not affiliated or endorsed.
Talks only to the local Amerika Studio bridge (127.0.0.1:18890); the add-on never holds an API key.
"""
bl_info = {
    'name': 'Amerika Render',
    'author': 'Amerika LLC',
    'version': (3, 1, 1),
    'blender': (4, 2, 0),
    'location': '3D Viewport > Sidebar > Amerika',
    'description': 'Talk to Blender: an AI modelling assistant (Amerika Studio)',
    'category': 'Interface',
    'warning': '',
    'doc_url': 'https://www.amerika.social',
}

_registered = False


def register():
    global _registered
    if _registered:
        return
    from . import ui
    ui.register()
    _registered = True


def unregister():
    global _registered
    if not _registered:
        return
    from . import ui
    ui.unregister()
    _registered = False
