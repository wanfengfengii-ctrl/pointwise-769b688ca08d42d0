import json

from issue.manifest import ManifestFrame
from issue.replacement_manifest import (
    ContinuationBasis,
    FrameState,
    ReplacementManifest,
    REPLACEMENT_VERSION,
)
from station.provenance import FrameSource


def _state(value, key):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('continuation state must contain exact integers')
    return value


def encode_replacement_manifest(manifest: ReplacementManifest):
    value = {
        'frame_count': manifest.frame_count,
        'frames': [
            {
                'frame_digest': frame.frame_digest,
                'frame_index': frame.frame_index,
                'reading_count': frame.reading_count,
                'source': frame.source.as_dict(),
            }
            for frame in manifest.frames
        ],
        'header_digest': manifest.header_digest,
        'issue_id': manifest.issue_id,
        'revision_id': manifest.revision_id,
        'total_readings': manifest.total_readings,
        'version': manifest.version,
        'first_frame': manifest.first_frame,
        'last_frame': manifest.last_frame,
        'correction_id': manifest.correction_id,
        'correction_digest': manifest.correction_digest,
        'continuation': {
            'revision_id': manifest.continuation.revision_id,
            'first_frame': manifest.continuation.first_frame,
            'last_frame': manifest.continuation.last_frame,
            'digest': manifest.continuation.digest,
            'frame_states': [
                {
                    'frame_index': state.frame_index,
                    'entry_value': state.entry_value,
                    'entry_delta': state.entry_delta,
                    'exit_value': state.exit_value,
                    'exit_delta': state.exit_delta,
                }
                for state in manifest.continuation.frame_states
            ],
        },
    }
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def decode_replacement_manifest(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid replacement manifest') from error
    if not isinstance(value, dict):
        raise ValueError('invalid replacement manifest')
    if value.get('version') != REPLACEMENT_VERSION:
        raise ValueError('unsupported replacement manifest version')
    frames_raw = value.get('frames')
    if not isinstance(frames_raw, list):
        raise ValueError('manifest frames must be a list')
    if value.get('frame_count') != len(frames_raw):
        raise ValueError('manifest frame count mismatch')
    frames = []
    for expected_index, item in enumerate(frames_raw):
        if not isinstance(item, dict) or item.get('frame_index') != expected_index:
            raise ValueError('manifest frame order mismatch')
        count = item.get('reading_count')
        digest = item.get('frame_digest')
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('manifest reading count is invalid')
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('manifest frame digest is invalid')
        source = item.get('source')
        if not isinstance(source, dict):
            raise ValueError('manifest source is invalid')
        frames.append(ManifestFrame(expected_index, count, digest, FrameSource(source['object_id'], source['frame_index'])))
    total = value.get('total_readings')
    if total != sum(item.reading_count for item in frames):
        raise ValueError('manifest total reading count mismatch')
    continuation_raw = value.get('continuation')
    if not isinstance(continuation_raw, dict):
        raise ValueError('manifest continuation basis is invalid')
    states_raw = continuation_raw.get('frame_states')
    if not isinstance(states_raw, list) or len(states_raw) != len(frames):
        raise ValueError('manifest continuation state coverage mismatch')
    states = []
    for expected_index, item in enumerate(states_raw):
        if not isinstance(item, dict) or item.get('frame_index') != expected_index:
            raise ValueError('manifest continuation state order mismatch')
        states.append(
            FrameState(
                expected_index,
                _state(item.get('entry_value'), 'entry_value'),
                _state(item.get('entry_delta'), 'entry_delta'),
                _state(item.get('exit_value'), 'exit_value'),
                _state(item.get('exit_delta'), 'exit_delta'),
            )
        )
    basis = ContinuationBasis(
        continuation_raw.get('revision_id'),
        continuation_raw.get('first_frame'),
        continuation_raw.get('last_frame'),
        tuple(states),
        continuation_raw.get('digest'),
    )
    if not isinstance(basis.digest, str) or len(basis.digest) != 64:
        raise ValueError('manifest continuation digest is invalid')
    first_frame = value.get('first_frame')
    last_frame = value.get('last_frame')
    correction_id = value.get('correction_id')
    correction_digest = value.get('correction_digest')
    if isinstance(first_frame, bool) or not isinstance(first_frame, int) or first_frame < 0:
        raise ValueError('manifest first_frame is invalid')
    if isinstance(last_frame, bool) or not isinstance(last_frame, int) or last_frame < 0:
        raise ValueError('manifest last_frame is invalid')
    if not isinstance(correction_id, str) or not correction_id.strip():
        raise ValueError('manifest correction_id is invalid')
    if not isinstance(correction_digest, str) or len(correction_digest) != 64:
        raise ValueError('manifest correction digest is invalid')
    return ReplacementManifest(
        value['issue_id'],
        value['revision_id'],
        REPLACEMENT_VERSION,
        value['header_digest'],
        value['frame_count'],
        total,
        tuple(frames),
        first_frame,
        last_frame,
        correction_id,
        correction_digest,
        basis,
    )
