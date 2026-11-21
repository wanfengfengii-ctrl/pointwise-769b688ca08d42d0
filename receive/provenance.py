from dataclasses import dataclass

from issue.manifest import IssueManifest
from media.positions import ReadingPosition
from receive.verify import VerifiedVolume
from station.provenance import FrameSource


@dataclass(frozen=True)
class ReceivedReading:
    issue_id: str
    revision_id: str
    position: ReadingPosition
    value: int
    source: FrameSource
    correction_id: str | None = None


def attach_provenance(verified: VerifiedVolume):
    if not isinstance(verified, VerifiedVolume):
        raise TypeError('verified must be a VerifiedVolume')
    readings = []
    for position, value in zip(verified.decoded.positions, verified.decoded.readings):
        manifest_frame = verified.manifest.frames[position.frame_index]
        readings.append(ReceivedReading(verified.manifest.issue_id, verified.manifest.revision_id, position, value, manifest_frame.source))
    return tuple(readings)


def attach_replacement_provenance(verified):
    from receive.replacement_verify import VerifiedReplacement

    if not isinstance(verified, VerifiedReplacement):
        raise TypeError('verified must be a VerifiedReplacement')
    manifest = verified.manifest
    readings = []
    ordinal = 0
    for frame_index, frame_values in enumerate(verified.frame_readings):
        source = manifest.frames[frame_index].source
        in_window = manifest.first_frame <= frame_index <= manifest.last_frame
        correction_id = manifest.correction_id if in_window else None
        for reading_index, value in enumerate(frame_values):
            position = ReadingPosition(frame_index, reading_index, ordinal)
            readings.append(ReceivedReading(manifest.issue_id, manifest.revision_id, position, value, source, correction_id))
            ordinal += 1
    return tuple(readings)
