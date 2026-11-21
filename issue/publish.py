import uuid

from issue.issued_store import IssuedRecord
from issue.manifest import build_manifest
from issue.manifest_wire import encode_manifest
from issue.package import build_package, encode_package
from issue.replacement_manifest import build_replacement_manifest
from issue.replacement_manifest_wire import encode_replacement_manifest
from issue.replacement_package import build_replacement_package, encode_replacement_package

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


def issue(revision_store, issued_store, revision_id):
    revision = revision_store.get_revision(revision_id)
    issue_id = 'issue-' + uuid.uuid4().hex
    manifest = build_manifest(issue_id, revision.revision_id, revision.frames, revision.volume)
    package = build_package(manifest, revision.volume)
    record = IssuedRecord(issue_id, revision.revision_id, encode_manifest(manifest), encode_package(package))
    issued_store.commit_issue(record)
    return record


def _validate_window(revision, first_frame, last_frame, readings, correction_id):
    frame_count = len(revision.volume.frames)
    if frame_count == 0:
        raise ValueError('a volume without frames has no valid window')
    if isinstance(first_frame, bool) or not isinstance(first_frame, int):
        raise ValueError('first_frame must be an integer')
    if isinstance(last_frame, bool) or not isinstance(last_frame, int):
        raise ValueError('last_frame must be an integer')
    if not (0 <= first_frame <= last_frame < frame_count):
        raise ValueError('window bounds must satisfy 0 <= first_frame <= last_frame < frame_count')
    if not isinstance(correction_id, str) or not correction_id.strip():
        raise ValueError('correction_id must be a non-empty string')
    if isinstance(readings, (str, bytes)) or not isinstance(readings, (list, tuple)):
        raise ValueError('readings must be a list or tuple of window frames')
    if len(readings) != last_frame - first_frame + 1:
        raise ValueError('readings must provide one entry per window frame')
    normalized = []
    for window_offset, frame_readings in enumerate(readings):
        if isinstance(frame_readings, (str, bytes)) or not isinstance(frame_readings, (list, tuple)):
            raise ValueError('each window frame must carry a list or tuple of readings')
        original_frame = revision.frames[first_frame + window_offset]
        if len(frame_readings) != len(original_frame.readings):
            raise ValueError('corrected frame reading count must match the original frame')
        frame_values = []
        for value in frame_readings:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError('corrected readings must be exact integers')
            if not (INT64_MIN <= value <= INT64_MAX):
                raise ValueError('corrected readings must fit in a signed 64-bit integer')
            frame_values.append(value)
        normalized.append(tuple(frame_values))
    return tuple(normalized)


def make_replacement(revision_store, issued_store, revision_id, first_frame, last_frame, readings, correction_id):
    revision = revision_store.get_revision(revision_id)
    normalized_readings = _validate_window(revision, first_frame, last_frame, readings, correction_id)
    issue_id = 'issue-' + uuid.uuid4().hex
    manifest = build_replacement_manifest(
        issue_id, revision, revision.volume, first_frame, last_frame, normalized_readings, correction_id
    )
    package = build_replacement_package(manifest, revision.volume, normalized_readings)
    record = IssuedRecord(
        issue_id,
        revision.revision_id,
        encode_replacement_manifest(manifest),
        encode_replacement_package(package),
    )
    issued_store.commit_issue(record)
    return record
