from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameSource:
    object_id: str
    frame_index: int

    def as_dict(self):
        return {'object_id': self.object_id, 'frame_index': self.frame_index}


def normalize_frame_source(source):
    if isinstance(source, FrameSource):
        return source
    if isinstance(source, Mapping):
        object_id = source.get('object_id', source.get('source_id'))
        frame_index = source.get('frame_index')
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)) and len(source) == 2:
        object_id, frame_index = source
    else:
        raise ValueError('source must contain an object id and frame index')
    if not isinstance(object_id, str) or not object_id.strip():
        raise ValueError('source object id must be a non-empty string')
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError('source frame index must be a non-negative integer')
    return FrameSource(object_id, frame_index)


def validate_unique_origins(sources):
    seen = set()
    for source in sources:
        normalized = normalize_frame_source(source)
        key = (normalized.object_id, normalized.frame_index)
        if key in seen:
            raise ValueError('source frame position is repeated')
        seen.add(key)
