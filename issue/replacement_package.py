import base64
import json
from dataclasses import dataclass

from issue.replacement_manifest import REPLACEMENT_VERSION


@dataclass(frozen=True)
class RetainedFrame:
    frame_index: int
    data: bytes


@dataclass(frozen=True)
class CorrectedFrame:
    frame_index: int
    readings: tuple[int, ...]


@dataclass(frozen=True)
class ReplacementPackage:
    issue_id: str
    revision_id: str
    version: int
    header: bytes
    first_frame: int
    last_frame: int
    correction_id: str
    continuation_digest: str
    frames: tuple


def build_replacement_package(manifest, volume, readings):
    frames = []
    for index, data in enumerate(volume.frames):
        if manifest.first_frame <= index <= manifest.last_frame:
            frames.append(CorrectedFrame(index, tuple(readings[index - manifest.first_frame])))
        else:
            frames.append(RetainedFrame(index, data))
    return ReplacementPackage(
        manifest.issue_id,
        manifest.revision_id,
        REPLACEMENT_VERSION,
        volume.header,
        manifest.first_frame,
        manifest.last_frame,
        manifest.correction_id,
        manifest.continuation.digest,
        tuple(frames),
    )


def encode_replacement_package(package: ReplacementPackage):
    frames = []
    for frame in package.frames:
        if isinstance(frame, RetainedFrame):
            frames.append({'frame_index': frame.frame_index, 'data': base64.b64encode(frame.data).decode('ascii')})
        else:
            frames.append({'frame_index': frame.frame_index, 'readings': list(frame.readings)})
    value = {
        'version': package.version,
        'issue_id': package.issue_id,
        'revision_id': package.revision_id,
        'first_frame': package.first_frame,
        'last_frame': package.last_frame,
        'correction_id': package.correction_id,
        'continuation_digest': package.continuation_digest,
        'header': base64.b64encode(package.header).decode('ascii'),
        'frames': frames,
    }
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def _exact_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('corrected readings must contain exact integers')
    return value


def decode_replacement_package(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid replacement package') from error
    if not isinstance(value, dict) or value.get('version') != REPLACEMENT_VERSION:
        raise ValueError('invalid replacement package')
    frames_raw = value.get('frames')
    if not isinstance(frames_raw, list):
        raise ValueError('replacement package frames must be a list')
    frames = []
    for expected_index, item in enumerate(frames_raw):
        if not isinstance(item, dict) or item.get('frame_index') != expected_index:
            raise ValueError('replacement package frame order mismatch')
        if 'data' in item:
            try:
                frame_data = base64.b64decode(item['data'].encode('ascii'), validate=True)
            except (KeyError, ValueError, AttributeError) as error:
                raise ValueError('invalid retained frame data') from error
            frames.append(RetainedFrame(expected_index, frame_data))
        elif 'readings' in item:
            raw_readings = item['readings']
            if not isinstance(raw_readings, list):
                raise ValueError('corrected frame readings must be a list')
            frames.append(CorrectedFrame(expected_index, tuple(_exact_int(entry) for entry in raw_readings)))
        else:
            raise ValueError('replacement package frame is incomplete')
    try:
        header = base64.b64decode(value['header'].encode('ascii'), validate=True)
    except (KeyError, ValueError, AttributeError) as error:
        raise ValueError('invalid replacement package header') from error
    first_frame = value.get('first_frame')
    last_frame = value.get('last_frame')
    correction_id = value.get('correction_id')
    continuation_digest = value.get('continuation_digest')
    if isinstance(first_frame, bool) or not isinstance(first_frame, int) or first_frame < 0:
        raise ValueError('replacement package first_frame is invalid')
    if isinstance(last_frame, bool) or not isinstance(last_frame, int) or last_frame < 0:
        raise ValueError('replacement package last_frame is invalid')
    if not isinstance(correction_id, str) or not correction_id.strip():
        raise ValueError('replacement package correction_id is invalid')
    if not isinstance(continuation_digest, str) or len(continuation_digest) != 64:
        raise ValueError('replacement package continuation digest is invalid')
    return ReplacementPackage(
        value['issue_id'],
        value['revision_id'],
        REPLACEMENT_VERSION,
        header,
        first_frame,
        last_frame,
        correction_id,
        continuation_digest,
        tuple(frames),
    )
