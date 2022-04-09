import bpy


def get_fade_curve(context, sequence, create=False):
    #Returns the fade curve for a given sequence.  If create is True, a curve will always be returned, if False, None will be returned if no curve is found.
    if sequence.type == 'SOUND':
        fade_variable = 'volume'
    else:
        fade_variable = 'blend_alpha'

    #Search through all curves and find the fade curve
    animation_data = context.scene.animation_data
    if not animation_data:
        if create:
            context.scene.animation_data_create()
            animation_data = context.scene.animation_data
        else:
            return None
    action = animation_data.action
    if not action:
        if create:
            action = bpy.data.actions.new(sequence.name+'Action')
            animation_data.action = action
        else:
            return None

    all_curves = action.fcurves
    fade_curve = None  #curve for the fades
    for curve in all_curves:
        if curve.data_path == 'sequence_editor.sequences_all["'+sequence.name+'"].'+fade_variable:
            #keyframes found
            fade_curve = curve
            break

    #Create curve if needed
    if fade_curve is None and create:
        fade_curve = all_curves.new(data_path=sequence.path_from_id(fade_variable))

        #add a single keyframe to prevent blender from making the waveform invisible (bug)
        if sequence.type == 'SOUND':
            value = sequence.volume
        else:
            value = sequence.blend_alpha
        fade_curve.keyframe_points.add(1)
        point = fade_curve.keyframe_points[0]
        point.co = (sequence.frame_final_start, value)

    return fade_curve
