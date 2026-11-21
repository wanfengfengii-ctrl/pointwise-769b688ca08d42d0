from dataclasses import dataclass

from issue.manifest import digest_bytes
from issue.replacement_manifest import (
    ReplacementManifest,
    canonical_continuation,
    correction_digest,
)
from issue.replacement_manifest_wire import decode_replacement_manifest
from issue.replacement_package import (
    CorrectedFrame,
    ReplacementPackage,
    RetainedFrame,
    decode_replacement_package,
)
from media.framing import unpack_frame, unpack_header


@dataclass(frozen=True)
class VerifiedReplacement:
    manifest: ReplacementManifest
    package: ReplacementPackage
    frame_readings: tuple[tuple[int, ...], ...]


def _manifest(value):
    return decode_replacement_manifest(value) if isinstance(value, (bytes, bytearray, memoryview)) else value


def _package(value):
    return decode_replacement_package(value) if isinstance(value, (bytes, bytearray, memoryview)) else value


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_replacement(manifest, package):
    manifest = _manifest(manifest)
    package = _package(package)
    if not isinstance(manifest, ReplacementManifest) or not isinstance(package, ReplacementPackage):
        raise ValueError('replacement manifest and package types are invalid')

    # The two materials must describe the same issue, revision and window.
    _require(manifest.issue_id == package.issue_id, 'issue identity mismatch')
    _require(manifest.revision_id == package.revision_id, 'revision identity mismatch')
    _require(manifest.first_frame == package.first_frame, 'first_frame mismatch')
    _require(manifest.last_frame == package.last_frame, 'last_frame mismatch')
    _require(manifest.correction_id == package.correction_id, 'correction_id mismatch')
    _require(
        manifest.continuation.digest == package.continuation_digest,
        'continuation basis mismatch',
    )

    first_frame = manifest.first_frame
    last_frame = manifest.last_frame
    frame_count = manifest.frame_count
    _require(0 <= first_frame <= last_frame < frame_count, 'window bounds are invalid')
    _require(len(package.frames) == frame_count, 'package frame coverage mismatch')

    # The trusted manifest must describe one continuation state per frame,
    # bound to this revision and the actual window boundaries.
    basis = manifest.continuation
    _require(basis.revision_id == manifest.revision_id, 'continuation revision mismatch')
    _require(basis.first_frame == first_frame and basis.last_frame == last_frame, 'continuation window mismatch')
    _require(len(basis.frame_states) == frame_count, 'continuation state coverage mismatch')
    recomputed_basis_digest = digest_bytes(canonical_continuation(basis).encode('ascii'))
    _require(recomputed_basis_digest == basis.digest, 'continuation basis digest mismatch')

    # The original header is delivered byte-for-byte and cross-checked against
    # the independently delivered manifest.
    _require(digest_bytes(package.header) == manifest.header_digest, 'header digest mismatch')
    header_seed = unpack_header(package.header)
    _require(header_seed == (basis.frame_states[0].entry_value, basis.frame_states[0].entry_delta), 'header seed is not the original stream seed')

    corrected_readings = []
    for index, (manifest_frame, package_frame) in enumerate(zip(manifest.frames, package.frames)):
        _require(manifest_frame.frame_index == index == package_frame.frame_index, 'frame index mismatch')
        in_window = first_frame <= index <= last_frame
        if in_window:
            _require(isinstance(package_frame, CorrectedFrame), 'window frame must carry corrected readings')
            values = package_frame.readings
            _require(len(values) == manifest_frame.reading_count, 'corrected frame reading count mismatch')
            corrected_readings.append(list(values))
        else:
            _require(isinstance(package_frame, RetainedFrame), 'retained frame must carry original bytes')
            _require(digest_bytes(package_frame.data) == manifest_frame.frame_digest, 'retained frame digest mismatch')
            values = unpack_frame(package_frame.data)
            _require(len(values) == manifest_frame.reading_count, 'retained frame reading count mismatch')

    # The actual corrected content must match the independent manifest.
    _require(correction_digest(corrected_readings) == manifest.correction_digest, 'corrected content mismatch')

    # Decode the retained original frames from the verified original stream
    # states, then splice the corrected values at the window. Corrected values
    # never feed the delta stream: the suffix resumes from the original exit
    # state of the last window frame, so the original continuation is preserved.
    output_frames = []
    previous_value, previous_delta = header_seed
    for index, package_frame in enumerate(package.frames):
        state = basis.frame_states[index]
        _require((previous_value, previous_delta) == (state.entry_value, state.entry_delta), 'invalid continuation basis for frame')
        if first_frame <= index <= last_frame:
            output_frames.append(tuple(package_frame.readings))
            previous_value, previous_delta = state.exit_value, state.exit_delta
        else:
            values = []
            for second_delta in unpack_frame(package_frame.data):
                previous_delta += second_delta
                previous_value += previous_delta
                values.append(previous_value)
            output_frames.append(tuple(values))
            _require((previous_value, previous_delta) == (state.exit_value, state.exit_delta), 'retained frame does not match continuation basis')

    return VerifiedReplacement(manifest, package, tuple(output_frames))
