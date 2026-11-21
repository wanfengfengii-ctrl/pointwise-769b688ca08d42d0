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


def attach_provenance(verified: VerifiedVolume):
    if not isinstance(verified, VerifiedVolume):
        raise TypeError('verified must be a VerifiedVolume')
    readings = []
    for position, value in zip(verified.decoded.positions, verified.decoded.readings):
        manifest_frame = verified.manifest.frames[position.frame_index]
        readings.append(ReceivedReading(verified.manifest.issue_id, verified.manifest.revision_id, position, value, manifest_frame.source))
    return tuple(readings)
