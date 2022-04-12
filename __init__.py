# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
from bpy.app.handlers import persistent

from . import vu_meter
from . import preferences

from importlib import reload
reload(vu_meter)
reload(preferences)


bl_info = {
    "name": "VSE Volume Meter",
    "description": "Just the volume meter from VSEQF (https://github.com/snuq/VSEQF)",
    "author": "Paolo Acampora, forked from Hudson Barkley (Snu/snuq/Aritodo)",
    "version": (3, 1, 1),
    "blender": (3, 1, 0),
    "location": "Sequencer",
    "wiki_url": "https://github.com/snuq/VSEQF",
    "tracker_url": "https://github.com/snuq/VSEQF/issues",
    "category": "Sequencer"
}


vu_meter_draw_handler = None
frame_step_handler = None


#Functions related to QuickSpeed
@persistent
def frame_step(scene):
    """Handler that skips frames when the speed step value is used, and updates the vu meter
    Argument:
        scene: the current Scene"""

    vu_meter.vu_meter_calculate(scene)
    if bpy.context.scene != scene:
        return
    if scene.vseqf.step in [-1, 0, 1]:
        return
    difference = scene.frame_current - scene.vseqf.last_frame
    if difference == -1 or difference == 1:
        frame_skip = int(difference * (abs(scene.vseqf.step) - 1))
        bpy.ops.screen.frame_offset(delta=frame_skip)
    scene.vseqf.last_frame = scene.frame_current


class VSEQFSetting(bpy.types.PropertyGroup):
    """Property group to store most VSEQF settings.  This will be assigned to scene.vseqf"""

    vu: bpy.props.FloatProperty(
        name="VU Meter Level",
        default=-60)
    vu_show: bpy.props.BoolProperty(
        name="Enable VU Meter",
        default=True)
    vu_max: bpy.props.FloatProperty(
        name="VU Meter Max Level",
        default=-60)

    step: bpy.props.IntProperty(
        name="Frame Step",
        default=0,
        min=-4,
        max=4)


def remove_vu_draw_handler(add=False):
    global vu_meter_draw_handler
    if vu_meter_draw_handler:
        try:
            bpy.types.SpaceSequenceEditor.draw_handler_remove(vu_meter_draw_handler, 'WINDOW')
            vu_meter_draw_handler = None
        except:
            pass
    if add:
        vu_meter_draw_handler = bpy.types.SpaceSequenceEditor.draw_handler_add(vu_meter.vu_meter_draw, (), 'WINDOW', 'POST_PIXEL')


def remove_frame_step_handler(add=False):
    global frame_step_handler
    handlers = bpy.app.handlers.frame_change_post
    if frame_step_handler:
        try:
            handlers.remove(frame_step_handler)
            frame_step_handler = None
        except:
            pass
    if add:
        frame_step_handler = handlers.append(frame_step)


def register():
    bpy.utils.register_class(VSEQFSetting)
    bpy.utils.register_class(vu_meter.VUMeterCheckClipping)
    preferences.register()

    #New variables
    bpy.types.Scene.vseqf_skip_interval = bpy.props.IntProperty(default=0, min=0)
    bpy.types.Scene.vseqf = bpy.props.PointerProperty(type=VSEQFSetting)
    bpy.types.Sequence.parent = bpy.props.StringProperty()

    bpy.types.Sequence.new = bpy.props.BoolProperty(default=True)
    bpy.types.Sequence.last_name = bpy.props.StringProperty()

    #Register handlers
    remove_frame_step_handler(add=True)
    remove_vu_draw_handler(add=True)


def unregister():
    #Remove handlers
    remove_vu_draw_handler()
    remove_frame_step_handler()

    bpy.utils.unregister_class(vu_meter.VUMeterCheckClipping)
    bpy.utils.unregister_class(VSEQFSetting)
    preferences.unregister()


if __name__ == "__main__":
    register()
