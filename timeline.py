
def under_cursor(sequence, frame):
    """Check if a sequence is visible on a frame
    Arguments:
        sequence: VSE sequence object to check
        frame: Integer, the frame number

    Returns: True or False"""
    if sequence.frame_final_start < frame and sequence.frame_final_end > frame:
        return True
    else:
        return False
