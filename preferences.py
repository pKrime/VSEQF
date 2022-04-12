import bpy
from bpy.props import FloatVectorProperty


class VolumeMeterPrefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    bg_color: FloatVectorProperty(
        name='Background Color',
        description='Background Color',
        subtype='COLOR',
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
    )

    bar_color: FloatVectorProperty(
        name='Bar Color',
        description='Bar Color',
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
    )

    warn_color: FloatVectorProperty(
        name='Warning Color',
        description='Warning Color',
        subtype='COLOR',
        default=(1.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
    )

    high_color: FloatVectorProperty(
        name='High Color',
        description='High Color',
        subtype='COLOR',
        default=(1.0, 1.0, 0.5),
        min=0.0,
        max=1.0,
    )

    very_high_color: FloatVectorProperty(
        name='Very High Color',
        description='Very High Color',
        subtype='COLOR',
        default=(1.0, 0.6, 0.6),
        min=0.0,
        max=1.0,
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        box = column.box()
        column = box.column()
        split = column.split()

        col = split.column()
        col.prop(self, 'bg_color')
        col.prop(self, 'bar_color')

        col = split.column()
        col.prop(self, 'high_color')
        col.prop(self, 'very_high_color')
        col.prop(self, 'warn_color')
        
        row = layout.row()
        row.label(text="End of Volume Meter Preferences")


def register():
    bpy.utils.register_class(VolumeMeterPrefs)


def unregister():
    bpy.utils.unregister_class(VolumeMeterPrefs)
