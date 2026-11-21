from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from station.provenance import FrameSource, normalize_frame_source, validate_unique_origins


@dataclass(frozen=True)
class SubmittedFrame:
    frame_index: int
    readings: tuple[int, ...]
    source: FrameSource


def _readings(raw):
    if not isinstance(raw, (list, tuple)):
        raise ValueError('readings must be a list or tuple')
    values = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('readings must contain exact integers')
        values.append(value)
    return tuple(values)


def _parts(raw):
    if isinstance(raw, SubmittedFrame):
        return raw.readings, raw.source
    if isinstance(raw, Mapping):
        if 'readings' not in raw or 'source' not in raw:
            raise ValueError('frame requires readings and source')
        return raw['readings'], raw['source']
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) == 2:
        return raw[0], raw[1]
    raise ValueError('frame must contain readings and source')


def validate_frames(frames):
    if isinstance(frames, (str, bytes)):
        raise ValueError('frames must be an ordered collection')
    try:
        raw_frames = list(frames)
    except TypeError as error:
        raise ValueError('frames must be an ordered collection') from error
    normalized = []
    for index, raw in enumerate(raw_frames):
        readings, source = _parts(raw)
        normalized.append(SubmittedFrame(index, _readings(readings), normalize_frame_source(source)))
    validate_unique_origins([frame.source for frame in normalized])
    return tuple(normalized)
