import hashlib
import json
from dataclasses import dataclass

from issue.manifest import ManifestFrame, digest_bytes

REPLACEMENT_VERSION = 2


@dataclass(frozen=True)
class FrameState:
    """Original-stream continuation state around one original frame.

    ``entry_*`` is the stream state before the frame is decoded and
    ``exit_*`` the state after it, expressed as (previous value, previous
    first delta). Empty frames keep the same state on both sides.
    """

    frame_index: int
    entry_value: int
    entry_delta: int
    exit_value: int
    exit_delta: int


@dataclass(frozen=True)
class ContinuationBasis:
    """Seam evidence binding the continuation basis to a revision and window."""

    revision_id: str
    first_frame: int
    last_frame: int
    frame_states: tuple[FrameState, ...]
    digest: str


@dataclass(frozen=True)
class ReplacementManifest:
    issue_id: str
    revision_id: str
    version: int
    header_digest: str
    frame_count: int
    total_readings: int
    frames: tuple[ManifestFrame, ...]
    first_frame: int
    last_frame: int
    correction_id: str
    correction_digest: str
    continuation: ContinuationBasis


def canonical_correction_readings(readings):
    return json.dumps(readings, ensure_ascii=True, separators=(',', ':'), sort_keys=True)


def correction_digest(readings):
    return hashlib.sha256(canonical_correction_readings(readings).encode('ascii')).hexdigest()


def canonical_continuation(basis: ContinuationBasis):
    return json.dumps(
        {
            'revision_id': basis.revision_id,
            'first_frame': basis.first_frame,
            'last_frame': basis.last_frame,
            'frame_states': [
                {
                    'frame_index': state.frame_index,
                    'entry_value': state.entry_value,
                    'entry_delta': state.entry_delta,
                    'exit_value': state.exit_value,
                    'exit_delta': state.exit_delta,
                }
                for state in basis.frame_states
            ],
        },
        ensure_ascii=True,
        separators=(',', ':'),
        sort_keys=True,
    )


def continuation_digest(basis: ContinuationBasis):
    return hashlib.sha256(canonical_continuation(basis).encode('ascii')).hexdigest()


def build_replacement_manifest(issue_id, revision, volume, first_frame, last_frame, readings, correction_id):
    manifest_frames = tuple(
        ManifestFrame(index, len(frame.readings), digest_bytes(data), frame.source)
        for index, (frame, data) in enumerate(zip(revision.frames, volume.frames))
    )
    from media.stream import stream_frame_states

    states = stream_frame_states(volume)
    basis = ContinuationBasis(
        revision.revision_id,
        first_frame,
        last_frame,
        tuple(
            FrameState(index, entry_value, entry_delta, exit_value, exit_delta)
            for index, (entry_value, entry_delta, exit_value, exit_delta) in enumerate(states)
        ),
        '',
    )
    basis = ContinuationBasis(
        basis.revision_id,
        basis.first_frame,
        basis.last_frame,
        basis.frame_states,
        continuation_digest(basis),
    )
    return ReplacementManifest(
        issue_id,
        revision.revision_id,
        REPLACEMENT_VERSION,
        digest_bytes(volume.header),
        len(manifest_frames),
        sum(item.reading_count for item in manifest_frames),
        manifest_frames,
        first_frame,
        last_frame,
        correction_id,
        correction_digest(readings),
        basis,
    )
