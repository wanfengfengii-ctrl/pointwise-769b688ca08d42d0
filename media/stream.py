from media.framing import unpack_frame


def stream_frame_states(volume):
    """Walk the original second-difference stream and report every frame state.

    The returned tuple holds one ``(entry_value, entry_delta, exit_value,
    exit_delta)`` per frame, in frame order. Empty frames do not advance the
    stream, so their entry and exit states are identical. The walk starts from
    the volume header seed exactly like :func:`media.decode.decode_volume`.
    """
    previous_value, previous_delta = volume.header_seed
    states = []
    for frame_bytes in volume.frames:
        entry_value, entry_delta = previous_value, previous_delta
        for second_delta in unpack_frame(frame_bytes):
            previous_delta += second_delta
            previous_value += previous_delta
        states.append((entry_value, entry_delta, previous_value, previous_delta))
    return tuple(states)
