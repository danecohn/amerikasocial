"""Dev-time generator: builds theme/amerika.xml (Blender interface theme preset) from the AltStack Desktop palette.

    blender -b --factory-startup --python tools/make_theme.py -- theme/amerika.xml

Run inside Blender (needs bpy). The result is committed; the builder only copies it.
"""
import os
import sys

import bpy

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'amerika.xml'


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# palette taken from the AltStack Desktop icons: warm night sky, hot-pink sun, amber neon, chrome rim
BG = hexc('#e7edf3')
BG2 = hexc('#eef3f8')
HEADER = hexc('#cbd5df')
PANEL = hexc('#f8fafc')
PANEL_HI = hexc('#d5eaff')
OUTLINE = hexc('#aebdcb')
TEXT = hexc('#233649')
TEXT_DIM = hexc('#51677c')
CHROME = hexc('#233649')
AMBER = hexc('#ffb02e')
PINK = hexc('#1764bd')
CYAN = hexc('#237dcc')
GRID = hexc('#aebdcb')

MAP = {
    # generic space colours
    'back': BG2, 'header': HEADER, 'header_text': TEXT, 'header_text_hi': AMBER, 'title': CHROME, 'text': TEXT, 'text_hi': AMBER,
    'button': PANEL, 'button_title': CHROME, 'button_text': TEXT, 'button_text_hi': AMBER,
    'tab_active': PANEL_HI, 'tab_inactive': HEADER, 'tab_back': BG, 'tab_outline': OUTLINE,
    'navigation_bar': BG, 'execution_buts': PANEL, 'tab_active_text': AMBER,
    # widgets
    'outline': OUTLINE, 'inner': PANEL, 'inner_sel': hexc('#1764bd'), 'item': AMBER, 'text_sel': (1, 1, 1),
    # 3D view and friends
    'object_selected': AMBER, 'object_active': hexc('#fff0cf'), 'vertex_select': AMBER, 'edge_select': AMBER, 'face_select': PINK,
    'grid': GRID, 'wire': hexc('#000000'), 'wire_edit': hexc('#000000'), 'transform': PINK, 'light': hexc('#ffb02e'),
    'selected_highlight': PANEL_HI, 'active': PINK, 'selected': AMBER, 'handle_vertex_select': AMBER,
    'frame_current': PINK, 'time_marker_line_selected': AMBER, 'cursor': AMBER, 'space_active': PINK,
    'lastsel_point': hexc('#fff0cf'), 'dopesheet_channel': PANEL, 'summary': HEADER,
    'panel_back': hexc('#eef3f8'), 'panel_header': HEADER, 'panel_sub_back': hexc('#e3ebf3'), 'panel_title': CHROME, 'panel_text': TEXT,
    'row_alternate': (1, 1, 1),
}
KEEP_ALPHA = True
count = 0


def paint(struct, depth=0):
    global count
    if depth > 6 or struct is None:
        return
    for prop in struct.bl_rna.properties:
        key = prop.identifier
        if key in ('rna_type',):
            continue
        try:
            val = getattr(struct, key)
        except Exception:
            continue
        if prop.type == 'POINTER' and val is not None and not isinstance(val, bpy.types.ID):
            paint(val, depth + 1)
        elif prop.type == 'FLOAT' and prop.subtype in ('COLOR', 'COLOR_GAMMA') and key in MAP:
            if key == 'row_alternate':
                continue
            c = MAP[key]
            try:
                if prop.array_length == 4:
                    setattr(struct, key, (*c, val[3]))
                else:
                    setattr(struct, key, c)
                count += 1
            except Exception:
                pass


theme = bpy.context.preferences.themes[0]
paint(theme)
# a distinctive 3D viewport backdrop
try:
    g = theme.view_3d.space.gradients
    g.background_type = 'LINEAR'
    g.high_gradient = hexc('#2a1a3a')
    g.gradient = hexc('#e7edf3')
    count += 2
except Exception as e:
    print('gradient skipped', e)
# rounder, flatter widgets
ui = theme.user_interface
try:
    ui.widget_emboss = (1, 1, 1, 0.04)
    ui.menu_shadow_fac = 0.3
    ui.editor_outline = OUTLINE
except Exception:
    pass

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
import _rna_xml as rna_xml
rna_xml.xml_file_write(bpy.context, OUT, bpy.types.USERPREF_MT_interface_theme_presets.preset_xml_map)
print(f'amerika theme: {count} colours set, wrote {OUT}')
