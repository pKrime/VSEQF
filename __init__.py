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
import bgl
import gpu
import math

from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader

from . import fades
from . import parenting
from . import timeline
from . import vseqf
from . import vu_meter


bl_info = {
    "name": "VSE Quick Functions",
    "description": "Improves functionality of the sequencer by adding new menus and functions for snapping, adding fades, zooming, sequence parenting, ripple editing, playback speed, and more.",
    "author": "Hudson Barkley (Snu/snuq/Aritodo)",
    "version": (3, 1, 1),
    "blender": (3, 1, 0),
    "location": "Sequencer Panels; Sequencer Menus; Sequencer S, F, Shift-F, Z, Ctrl-P, Shift-P, Alt-M, Alt-K Shortcuts",
    "wiki_url": "https://github.com/snuq/VSEQF",
    "tracker_url": "https://github.com/snuq/VSEQF/issues",
    "category": "Sequencer"
}


vseqf_draw_handler = None
vu_meter_draw_handler = None
frame_step_handler = None
continuous_handler = None

classes = []
classes = classes + [vu_meter.VUMeterCheckClipping]


#Functions related to continuous update
@persistent
def vseqf_continuous(scene):
    if not bpy.context.scene or bpy.context.scene != scene:
        return
    if scene.vseqf.last_frame != scene.frame_current:
        #scene frame was changed, assume nothing else happened
        pass
        #scene.vseqf.last_frame = scene.frame_current
    else:
        #something in the scene was changed by the user, figure out what
        try:
            sequencer = scene.sequence_editor
            sequences = sequencer.sequences
        except:
            return
        new_sequences = []
        new_end = scene.frame_current
        build_proxies = False
        for sequence in sequences:
            if sequence.new:
                if not (sequence.type == 'META' or hasattr(sequence, 'input_1')):
                    new_sequences.append(sequence)
                sequence.last_name = sequence.name
                sequence.new = False
            if sequence.last_name != sequence.name:
                #sequence was renamed or duplicated, update parenting if the original doesnt still exist
                if sequence.name and sequence.last_name:
                    original = False
                    for seq in sequences:
                        if seq.name == sequence.last_name:
                            #this sequence was just duplicated or copied, dont do anything
                            original = seq
                            break
                    if not original:
                        #sequence was renamed, update parenting
                        children = parenting.find_children(sequence.last_name, name=True, sequences=sequences)
                        for child in children:
                            child.parent = sequence.name
                sequence.last_name = sequence.name
        if new_sequences:
            for sequence in new_sequences:
                if sequence.type not in ['ADJUSTMENT', 'TEXT', 'COLOR', 'MULTICAM'] and sequence.frame_final_end > new_end:
                    new_end = sequence.frame_final_end
                if vseqf.parenting() and scene.vseqf.autoparent:
                    #autoparent
                    if sequence.type == 'SOUND':
                        for seq in new_sequences:
                            if seq.type == 'MOVIE':
                                if seq.filepath == sequence.sound.filepath:
                                    sequence.parent = seq.name
                                    break
                if vseqf.proxy():
                    #enable proxies on sequence
                    applied_proxies = vseqf.apply_proxy_settings(sequence)
                    if applied_proxies and scene.vseqf.build_proxy:
                        build_proxies = True
            if build_proxies:
                #Build proxies if needed
                last_selected = bpy.context.selected_sequences
                for seq in sequences:
                    if seq in new_sequences:
                        seq.select = True
                    else:
                        seq.select = False
                area = False
                region = False
                for screenarea in bpy.context.window.screen.areas:
                    if screenarea.type == 'SEQUENCE_EDITOR':
                        area = screenarea
                        for arearegion in area.regions:
                            if arearegion.type == 'WINDOW':
                                region = arearegion
                if area and region:
                    override = bpy.context.copy()
                    override['area'] = area
                    override['region'] = region
                    bpy.ops.sequencer.rebuild_proxy(override, 'INVOKE_DEFAULT')
                for seq in sequences:
                    if seq in last_selected:
                        seq.select = True
                    else:
                        seq.select = False
            if scene.vseqf.snap_new_end:
                scene.frame_current = new_end


def vseqf_draw():
    context = bpy.context
    prefs = vseqf.get_prefs()
    colors = bpy.context.preferences.themes[0].user_interface
    text_color = list(colors.wcol_text.text_sel)+[1]
    active_strip = timeline.current_active(context)
    if not active_strip:
        return
    region = bpy.context.region
    view = region.view2d

    #determine pixels per frame and channel
    width = region.width
    height = region.height
    left, bottom = view.region_to_view(0, 0)
    right, top = view.region_to_view(width, height)
    if math.isnan(left):
        return
    shown_width = right - left
    shown_height = top - bottom
    channel_px = height / shown_height
    frame_px = width / shown_width

    min_x = 25
    max_x = width - 10
    fps = vseqf.get_fps()
    draw_strip_info(context, active_strip, fps, frame_px, channel_px, min_x, max_x, view, width, text_color, prefs.fades, prefs.parenting, True, True)
    selected = timeline.current_selected(context)
    for strip in selected:
        if strip != active_strip:
            draw_strip_info(context, strip, fps, frame_px, channel_px, min_x, max_x, view, width, text_color, prefs.fades, prefs.parenting, False, True)


def draw_strip_info(context, active_strip, fps, frame_px, channel_px, min_x, max_x, view, width, text_color, show_fades, show_parenting, show_length, show_markers):
    length = active_strip.frame_final_duration
    active_x = active_strip.frame_final_start + (length / 2)
    active_y = active_strip.channel + 0.5
    active_left, active_top = view.view_to_region(active_strip.frame_final_start, active_strip.channel+1, clip=False)
    active_right, active_bottom = view.view_to_region(active_strip.frame_final_end, active_strip.channel, clip=False)
    active_pos_x, active_pos_y = view.view_to_region(active_x, active_strip.channel + 0.5, clip=False)
    active_width = length * frame_px
    fade_height = channel_px / 20
    text_size = 10
    strip_x = active_pos_x
    if strip_x <= min_x and active_right > min_x:
        strip_x = min_x
    if strip_x >= max_x and active_left < max_x:
        strip_x = max_x

    #display length
    if show_length:
        length_timecode = vseqf.timecode_from_frames(length, fps)
        vseqf.draw_text(strip_x - (strip_x / width) * 40, active_bottom + (channel_px * .1), text_size, '('+length_timecode+')', text_color)

    #display fades
    if show_fades and active_width > text_size * 6:
        fade_curve = fades.get_fade_curve(context, active_strip, create=False)
        if fade_curve:
            fadein = int(fades.fades(fade_curve, active_strip, 'detect', 'in'))
            if fadein and length:
                fadein_percent = fadein / length
                vseqf.draw_rect(active_left, active_top - (fade_height * 2), fadein_percent * active_width, fade_height, color=(.5, .5, 1, .75))
                vseqf.draw_text(active_left, active_top, text_size, 'In: '+str(fadein), text_color)
            fadeout = int(fades.fades(fade_curve, active_strip, 'detect', 'out'))
            if fadeout and length:
                fadeout_percent = fadeout / length
                fadeout_width = active_width * fadeout_percent
                vseqf.draw_rect(active_right - fadeout_width, active_top - (fade_height * 2), fadeout_width, fade_height, color=(.5, .5, 1, .75))
                vseqf.draw_text(active_right - (text_size * 4), active_top, text_size, 'Out: '+str(fadeout), text_color)

    if show_parenting:
        bgl.glEnable(bgl.GL_BLEND)
        children = parenting.find_children(active_strip)
        parent = parenting.find_parent(active_strip)
        if parent:
            parent_x = parent.frame_final_start + (parent.frame_final_duration / 2)
            parent_y = parent.channel + 0.5
            distance_x = parent_x - active_x
            distance_y = parent_y - active_y
            pixel_x_distance = int(distance_x * frame_px)
            pixel_y_distance = int(distance_y * channel_px)
            pixel_x = active_pos_x + pixel_x_distance
            pixel_y = active_pos_y + pixel_y_distance
            vseqf.draw_line(strip_x, active_pos_y, pixel_x, pixel_y, color=(0.0, 0.0, 0.0, 0.2))
        coords = []
        for child in children:
            child_x = child.frame_final_start + (child.frame_final_duration / 2)
            child_y = child.channel + 0.5
            distance_x = child_x - active_x
            distance_y = child_y - active_y
            pixel_x_distance = int(distance_x * frame_px)
            pixel_y_distance = int(distance_y * channel_px)
            pixel_x = active_pos_x + pixel_x_distance
            pixel_y = active_pos_y + pixel_y_distance
            coords.append((strip_x, active_pos_y))
            coords.append((pixel_x, pixel_y))
        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {'pos': coords})
        shader.bind()
        shader.uniform_float('color', (1.0, 1.0, 1.0, 0.2))
        batch.draw(shader)
        bgl.glDisable(bgl.GL_BLEND)

    if show_markers:
        bgl.glEnable(bgl.GL_BLEND)

        bgl.glDisable(bgl.GL_BLEND)


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


def draw_quickspeed_header(self, context):
    """Draws the speed selector in the sequencer header"""
    layout = self.layout
    scene = context.scene
    self.layout_width = 30
    layout.prop(scene.vseqf, 'step', text="Speed Step")


#Classes for settings and variables
class VSEQFSettingsMenu(bpy.types.Menu):
    """Pop-up menu for settings related to QuickContinuous"""
    bl_idname = "VSEQF_MT_settings_menu"
    bl_label = "Quick Settings"

    def draw(self, context):
        prefs = vseqf.get_prefs()

        layout = self.layout
        scene = context.scene
        layout.prop(scene.vseqf, 'vu_show', text='Show VU Meter')
        layout.prop(scene.vseqf, 'snap_cursor_to_edge')
        layout.prop(scene.vseqf, 'snap_new_end')
        layout.prop(scene.vseqf, 'shortcut_skip')
        if prefs.parenting:
            layout.separator()
            layout.label(text='QuickParenting Settings')
            layout.separator()
            layout.prop(scene.vseqf, 'children')
            layout.prop(scene.vseqf, 'move_edges')
            layout.prop(scene.vseqf, 'delete_children')
            layout.prop(scene.vseqf, 'autoparent')
            layout.prop(scene.vseqf, 'select_children')
        if prefs.proxy:
            layout.separator()
            layout.label(text='QuickProxy Settings')
            layout.separator()
            layout.prop(scene.vseqf, 'enable_proxy')
            layout.prop(scene.vseqf, 'build_proxy')
            layout.prop(scene.vseqf, "proxy_quality", text='Proxy Quality')
            layout.prop(scene.vseqf, "proxy_25", text='Generate 25% Proxy')
            layout.prop(scene.vseqf, "proxy_50", text='Generate 50% Proxy')
            layout.prop(scene.vseqf, "proxy_75", text='Generate 75% Proxy')
            layout.prop(scene.vseqf, "proxy_100", text='Generate 100% Proxy')


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

    children: bpy.props.BoolProperty(
        name="Cut/Move Children",
        default=True,
        description="Automatically cut and move child strips along with a parent.")
    autoparent: bpy.props.BoolProperty(
        name="Auto-Parent New Audio To Video",
        default=True,
        description="Automatically parent audio strips to video when importing a movie with both types of strips.")
    select_children: bpy.props.BoolProperty(
        name="Auto-Select Children",
        default=False,
        description="Automatically select child strips when a parent is selected.")
    expanded_children: bpy.props.BoolProperty(default=True)
    delete_children: bpy.props.BoolProperty(
        name="Auto-Delete Children",
        default=False,
        description="Automatically delete child strips when a parent is deleted.")
    move_edges: bpy.props.BoolProperty(
        name="Move Matching Child Edges",
        default=True,
        description="When a child edge matches a parent's, it will be moved when the parent's edge is moved.")

    transition: bpy.props.EnumProperty(
        name="Transition Type",
        default="CROSS",
        items=[("CROSS", "Crossfade", "", 1), ("WIPE", "Wipe", "", 2), ("GAMMA_CROSS", "Gamma Cross", "", 3)])
    fade: bpy.props.IntProperty(
        name="Fade Length",
        default=10,
        min=0,
        description="Default Fade Length In Frames")
    fadein: bpy.props.IntProperty(
        name="Fade In Length",
        default=0,
        min=0,
        description="Current Fade In Length In Frames")
    fadeout: bpy.props.IntProperty(
        name="Fade Out Length",
        default=0,
        min=0,
        description="Current Fade Out Length In Frames")

    enable_proxy: bpy.props.BoolProperty(
        name="Enable Proxy On Import",
        default=False)
    build_proxy: bpy.props.BoolProperty(
        name="Auto-Build Proxy On Import",
        default=False)
    proxy_25: bpy.props.BoolProperty(
        name="25%",
        default=True)
    proxy_50: bpy.props.BoolProperty(
        name="50%",
        default=False)
    proxy_75: bpy.props.BoolProperty(
        name="75%",
        default=False)
    proxy_100: bpy.props.BoolProperty(
        name="100%",
        default=False)
    proxy_quality: bpy.props.IntProperty(
        name="Quality",
        default=90,
        min=1,
        max=100)

    current_marker_frame: bpy.props.IntProperty(
        default=0)
    marker_index: bpy.props.IntProperty(
        name="Marker Display Index",
        default=0)

    expanded_markers: bpy.props.BoolProperty(default=True)
    current_marker: bpy.props.StringProperty(
        name="New Preset",
        default='')
    marker_deselect: bpy.props.BoolProperty(
        name="Deselect New Markers",
        default=True,
        description="Markers added with this interface will not be selected when added")


    step: bpy.props.IntProperty(
        name="Frame Step",
        default=0,
        min=-4,
        max=4)
    skip_index: bpy.props.IntProperty(
        default=0)

    current_tag: bpy.props.StringProperty(
        name="New Tag",
        default='')


    show_selected_tags: bpy.props.BoolProperty(
        name="Show Tags For All Selected Sequences",
        default=False)
    tag_index: bpy.props.IntProperty(
        name="Tag Display Index",
        default=0)
    strip_tag_index: bpy.props.IntProperty(
        name="Strip Tag Display Index",
        default=0)

    quickcuts_insert: bpy.props.IntProperty(
        name="Frames To Insert",
        default=0,
        min=0,
        description='Number of frames to insert when performing an insert cut')
    quickcuts_all: bpy.props.BoolProperty(
        name='Cut All Sequences',
        default=False,
        description='Cut all sequences, regardless of selection (not including locked sequences)')
    snap_new_end: bpy.props.BoolProperty(
        name='Snap Cursor To End Of New Sequences',
        default=False)
    snap_cursor_to_edge: bpy.props.BoolProperty(
        name='Snap Cursor When Dragging Edges',
        default=False)


class VSEQuickFunctionSettings(bpy.types.AddonPreferences):
    """Addon preferences for QuickFunctions, used to enable and disable features"""
    bl_idname = __name__

    parenting: bpy.props.BoolProperty(
        name="Enable Quick Parenting",
        default=True)
    fades: bpy.props.BoolProperty(
        name="Enable Quick Fades",
        default=True)
    proxy: bpy.props.BoolProperty(
        name="Enable Quick Proxy",
        default=True)
    markers: bpy.props.BoolProperty(
        name="Enable Quick Markers",
        default=True)
    tags: bpy.props.BoolProperty(
        name="Enable Quick Tags",
        default=True)
    cuts: bpy.props.BoolProperty(
        name="Enable Quick Cuts",
        default=True)
    edit: bpy.props.BoolProperty(
        name="Enable Compact Edit Panel",
        default=False)
    threepoint: bpy.props.BoolProperty(
        name="Enable Quick Three Point",
        default=True)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "parenting")
        layout.prop(self, "fades")
        layout.prop(self, "proxy")
        layout.prop(self, "markers")
        layout.prop(self, "tags")
        layout.prop(self, "cuts")
        layout.prop(self, "edit")
        layout.prop(self, "threepoint")

        mainrow = layout.row()
        col = mainrow.column()


#Replaced Blender Menus
class SEQUENCER_MT_strip_transform(bpy.types.Menu):
    bl_label = "Transform"

    def draw(self, context):
        layout = self.layout

        #layout.operator("transform.seq_slide", text="Move")
        layout.operator("vseqf.grab", text="Grab/Move")
        #layout.operator("transform.transform", text="Move/Extend from Playhead").mode = 'TIME_EXTEND'
        layout.operator("vseqf.grab", text="Move/Extend from playhead").mode = 'TIME_EXTEND'
        #layout.operator("sequencer.slip", text="Slip Strip Contents")
        layout.operator("vseqf.grab", text="Slip Strip Contents").mode = 'SLIP'

        layout.separator()
        #layout.operator("sequencer.snap")
        layout.operator("sequencer.offset_clear")

        layout.separator()
        layout.operator_menu_enum("sequencer.swap", "side")

        layout.separator()
        layout.operator("sequencer.gap_remove").all = False
        layout.operator("sequencer.gap_insert")

        layout.separator()
        layout.operator('vseqf.quicksnaps', text='Snap Beginning To Cursor').type = 'begin_to_cursor'
        layout.operator('vseqf.quicksnaps', text='Snap End To Cursor').type = 'end_to_cursor'
        layout.operator('vseqf.quicksnaps', text='Snap To Previous Strip').type = 'sequence_to_previous'
        layout.operator('vseqf.quicksnaps', text='Snap To Next Strip').type = 'sequence_to_next'


class SEQUENCER_MT_strip(bpy.types.Menu):
    bl_label = "Strip"

    def draw(self, context):
        layout = self.layout

        layout.operator_context = 'INVOKE_REGION_WIN'

        layout.separator()
        layout.menu("SEQUENCER_MT_strip_transform")

        layout.separator()
        #layout.operator("sequencer.cut", text="Cut").type = 'SOFT'
        #layout.operator("sequencer.cut", text="Hold Cut").type = 'HARD'
        layout.operator("vseqf.cut", text="Cut/Split").type = 'SOFT'
        layout.operator("vseqf.cut", text="Hold Cut/Split").type = 'HARD'

        layout.separator()
        layout.operator("sequencer.copy", text="Copy")
        layout.operator("sequencer.paste", text="Paste")
        layout.operator("sequencer.duplicate_move")
        layout.operator("sequencer.delete", text="Delete...")

        layout.separator()
        layout.menu("SEQUENCER_MT_strip_lock_mute")

        #strip = act_strip(context)
        strip = timeline.current_active(context)

        if strip:
            strip_type = strip.type

            if strip_type != 'SOUND':
                layout.separator()
                layout.operator_menu_enum("sequencer.strip_modifier_add", "type", text="Add Modifier")
                layout.operator("sequencer.strip_modifier_copy", text="Copy Modifiers to Selection")

            if strip_type in {
                    'CROSS', 'ADD', 'SUBTRACT', 'ALPHA_OVER', 'ALPHA_UNDER',
                    'GAMMA_CROSS', 'MULTIPLY', 'OVER_DROP', 'WIPE', 'GLOW',
                    'TRANSFORM', 'COLOR', 'SPEED', 'MULTICAM', 'ADJUSTMENT',
                    'GAUSSIAN_BLUR',
            }:
                layout.separator()
                layout.menu("SEQUENCER_MT_strip_effect")
            elif strip_type == 'MOVIE':
                layout.separator()
                layout.menu("SEQUENCER_MT_strip_movie")
            elif strip_type == 'IMAGE':
                layout.separator()
                layout.operator("sequencer.rendersize")
                layout.operator("sequencer.images_separate")
            elif strip_type == 'TEXT':
                layout.separator()
                layout.menu("SEQUENCER_MT_strip_effect")
            elif strip_type == 'META':
                layout.separator()
                #layout.operator("sequencer.meta_make")
                layout.operator("vseqf.meta_make")
                layout.operator("sequencer.meta_separate")
                layout.operator("sequencer.meta_toggle", text="Toggle Meta")
            if strip_type != 'META':
                layout.separator()
                #layout.operator("sequencer.meta_make")
                layout.operator("vseqf.meta_make")
                layout.operator("sequencer.meta_toggle", text="Toggle Meta")

        layout.separator()
        layout.menu("SEQUENCER_MT_strip_input")

        layout.separator()
        layout.operator("sequencer.rebuild_proxy")


def selected_sequences_len(context):
    try:
        return len(context.selected_sequences) if context.selected_sequences else 0
    except AttributeError:
        return 0


class SEQUENCER_MT_add(bpy.types.Menu):
    bl_label = "Add"

    def draw(self, context):

        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'

        bpy_data_scenes_len = len(bpy.data.scenes)
        if bpy_data_scenes_len > 10:
            layout.operator_context = 'INVOKE_DEFAULT'
            layout.operator("sequencer.scene_strip_add", text="Scene...", icon='SCENE_DATA')
        elif bpy_data_scenes_len > 1:
            layout.operator_menu_enum("sequencer.scene_strip_add", "scene", text="Scene", icon='SCENE_DATA')
        else:
            layout.menu("SEQUENCER_MT_add_empty", text="Scene", icon='SCENE_DATA')
        del bpy_data_scenes_len

        bpy_data_movieclips_len = len(bpy.data.movieclips)
        if bpy_data_movieclips_len > 10:
            layout.operator_context = 'INVOKE_DEFAULT'
            layout.operator("sequencer.movieclip_strip_add", text="Clip...", icon='TRACKER')
        elif bpy_data_movieclips_len > 0:
            layout.operator_menu_enum("sequencer.movieclip_strip_add", "clip", text="Clip", icon='TRACKER')
        else:
            layout.menu("SEQUENCER_MT_add_empty", text="Clip", icon='TRACKER')
        del bpy_data_movieclips_len

        bpy_data_masks_len = len(bpy.data.masks)
        if bpy_data_masks_len > 10:
            layout.operator_context = 'INVOKE_DEFAULT'
            layout.operator("sequencer.mask_strip_add", text="Mask...", icon='MOD_MASK')
        elif bpy_data_masks_len > 0:
            layout.operator_menu_enum("sequencer.mask_strip_add", "mask", text="Mask", icon='MOD_MASK')
        else:
            layout.menu("SEQUENCER_MT_add_empty", text="Mask", icon='MOD_MASK')
        del bpy_data_masks_len

        layout.separator()

        #layout.operator("sequencer.movie_strip_add", text="Movie", icon='FILE_MOVIE')
        layout.operator("vseqf.import_strip", text="Movie", icon="FILE_MOVIE").type = 'MOVIE'
        #layout.operator("sequencer.sound_strip_add", text="Sound", icon='FILE_SOUND')
        layout.operator("sequencer.sound_strip_add", text="Sound", icon='FILE_SOUND')
        #layout.operator("sequencer.image_strip_add", text="Image/Sequence", icon='FILE_IMAGE')
        layout.operator("vseqf.import_strip", text="Image/Sequence", icon="FILE_IMAGE").type = 'IMAGE'

        layout.separator()

        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator("sequencer.effect_strip_add", text="Color", icon='COLOR').type = 'COLOR'
        layout.operator("sequencer.effect_strip_add", text="Text", icon='FONT_DATA').type = 'TEXT'

        layout.separator()

        layout.operator("sequencer.effect_strip_add", text="Adjustment Layer", icon='COLOR').type = 'ADJUSTMENT'

        layout.operator_context = 'INVOKE_DEFAULT'
        layout.menu("SEQUENCER_MT_add_effect", icon='SHADERFX')

        col = layout.column()
        col.menu("SEQUENCER_MT_add_transitions", icon='ARROW_LEFTRIGHT')
        col.enabled = selected_sequences_len(context) >= 2

        col = layout.column()
        col.operator_menu_enum("sequencer.fades_add", "type", text="Fade", icon="IPO_EASE_IN_OUT")
        col.enabled = selected_sequences_len(context) >= 1


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


def remove_continuous_handler(add=False):
    global continuous_handler
    handlers = bpy.app.handlers.depsgraph_update_post
    if continuous_handler:
        try:
            handlers.remove(continuous_handler)
            continuous_handler = None
        except:
            pass
    if add:
        continuous_handler = handlers.append(vseqf_continuous)


#Register properties, operators, menus and shortcuts
classes = classes + [VSEQFSettingsMenu, VSEQFSetting,
                     SEQUENCER_MT_strip, SEQUENCER_MT_strip_transform, SEQUENCER_MT_add]


def register():
    bpy.utils.register_class(VSEQuickFunctionSettings)

    #Register classes
    for cls in classes:
        bpy.utils.register_class(cls)

    #Register toolbar buttons
    #bpy.utils.register_tool(grabs.VSEQFSelectGrabTool, separator=True)

    global vseqf_draw_handler
    if vseqf_draw_handler:
        try:
            bpy.types.SpaceSequenceEditor.draw_handler_remove(vseqf_draw_handler, 'WINDOW')
        except:
            pass
    vseqf_draw_handler = bpy.types.SpaceSequenceEditor.draw_handler_add(vseqf_draw, (), 'WINDOW', 'POST_PIXEL')

    try:
        bpy.types.TIME_HT_editor_buttons.append(draw_quickspeed_header)
    except:
        #Fix for blender 2.91, move the quickspeed header...
        bpy.types.DOPESHEET_HT_header.append(draw_quickspeed_header)

    #New variables
    bpy.types.Scene.vseqf_skip_interval = bpy.props.IntProperty(default=0, min=0)
    bpy.types.Scene.vseqf = bpy.props.PointerProperty(type=VSEQFSetting)
    bpy.types.Sequence.parent = bpy.props.StringProperty()

    bpy.types.Sequence.new = bpy.props.BoolProperty(default=True)
    bpy.types.Sequence.last_name = bpy.props.StringProperty()

    #Register handlers
    remove_frame_step_handler(add=True)
    remove_continuous_handler(add=True)
    remove_vu_draw_handler(add=True)


def unregister():
    global vseqf_draw_handler
    bpy.types.SpaceSequenceEditor.draw_handler_remove(vseqf_draw_handler, 'WINDOW')

    #Unregister menus

    try:
        bpy.types.TIME_HT_editor_buttons.remove(draw_quickspeed_header)
    except:
        bpy.types.DOPESHEET_HT_header.remove(draw_quickspeed_header)

    #Remove shortcuts
    keymapitems = bpy.context.window_manager.keyconfigs.addon.keymaps['Sequencer'].keymap_items
    for keymapitem in keymapitems:
        if (keymapitem.type == 'Z') | (keymapitem.type == 'F') | (keymapitem.type == 'S') | (keymapitem.type == 'G') | (keymapitem.type == 'RIGHTMOUSE') | (keymapitem.type == 'K') | (keymapitem.type == 'E') | (keymapitem.type == 'X') | (keymapitem.type == 'DEL') | (keymapitem.type == 'M') | (keymapitem.type == 'NUMPAD_0') | (keymapitem.type == 'NUMPAD_1') | (keymapitem.type == 'NUMPAD_2') | (keymapitem.type == 'NUMPAD_3') | (keymapitem.type == 'NUMPAD_4') | (keymapitem.type == 'NUMPAD_5') | (keymapitem.type == 'NUMPAD_6') | (keymapitem.type == 'NUMPAD_7') | (keymapitem.type == 'NUMPAD_8') | (keymapitem.type == 'NUMPAD_9'):
            keymapitems.remove(keymapitem)

    #Remove handlers
    remove_vu_draw_handler()
    remove_frame_step_handler()
    remove_continuous_handler()

    try:
        bpy.utils.unregister_class(VSEQuickFunctionSettings)
    except RuntimeError:
        pass

    #Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
