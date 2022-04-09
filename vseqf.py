import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader


class VSEQFTempSettings(object):
    """Substitute for the addon preferences when this script isn't loaded as an addon"""
    parenting = True
    fades = True
    proxy = True
    markers = True
    tags = True
    cuts = True
    edit = True
    threepoint = True


#Drawing functions
def draw_line(sx, sy, ex, ey, color=(1.0, 1.0, 1.0, 1.0)):
    coords = [(sx, sy), (ex, ey)]
    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {'pos': coords})
    shader.bind()
    shader.uniform_float('color', color)
    batch.draw(shader)


def draw_rect(x, y, w, h, color=(1.0, 1.0, 1.0, 1.0)):
    vertices = ((x, y), (x+w, y), (x, y+h), (x+w, y+h))
    indices = ((0, 1, 2), (2, 1, 3))
    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.bind()
    shader.uniform_float('color', color)
    batch.draw(shader)


def draw_tri(v1, v2, v3, color=(1.0, 1.0, 1.0, 1.0)):
    vertices = (v1, v2, v3)
    indices = ((0, 1, 2), )
    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.bind()
    shader.uniform_float('color', color)
    batch.draw(shader)


def draw_text(x, y, size, text, justify='left', color=(1.0, 1.0, 1.0, 1.0)):
    #Draws basic text at a given location
    font_id = 0
    blf.color(font_id, *color)
    if justify == 'right':
        text_width, text_height = blf.dimensions(font_id, text)
    else:
        text_width = 0
    blf.position(font_id, x - text_width, y, 0)
    blf.size(font_id, size, 72)
    blf.draw(font_id, text)


#Miscellaneous Functions
def get_prefs():
    if __name__ in bpy.context.preferences.addons:
        prefs = bpy.context.preferences.addons[__name__].preferences
    else:
        prefs = VSEQFTempSettings()
    return prefs


def parenting():
    prefs = get_prefs()
    if prefs.parenting and bpy.context.scene.vseqf.children:
        return True
    else:
        return False


def redraw_sequencers():
    for area in bpy.context.screen.areas:
        if area.type == 'SEQUENCE_EDITOR':
            area.tag_redraw()


def get_fps(scene=None):
    if scene is None:
        scene = bpy.context.scene
    return scene.render.fps / scene.render.fps_base

