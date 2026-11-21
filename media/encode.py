from media.framing import EncodedVolume, pack_frame


def encode_volume(frames):
    previous_value = 0
    previous_delta = 0
    encoded_frames = []
    for frame in frames:
        readings = frame.readings if hasattr(frame, 'readings') else frame
        second_deltas = []
        for value in readings:
            current_delta = value - previous_value
            second_deltas.append(current_delta - previous_delta)
            previous_value = value
            previous_delta = current_delta
        encoded_frames.append(pack_frame(second_deltas))
    return EncodedVolume((0, 0), tuple(encoded_frames))
