import hashlib
from dataclasses import dataclass

from media.framing import V1_VERSION, pack_frame
from station.provenance import FrameSource


@dataclass(frozen=True)
class ManifestFrame:
    frame_index: int
    reading_count: int
    frame_digest: str
    source: FrameSource


@dataclass(frozen=True)
class IssueManifest:
    issue_id: str
    revision_id: str
    version: int
    header_digest: str
    frame_count: int
    total_readings: int
    frames: tuple[ManifestFrame, ...]


def digest_bytes(data):
    return hashlib.sha256(bytes(data)).hexdigest()


def build_manifest(issue_id, revision_id, frames, volume):
    if len(frames) != len(volume.frames):
        raise ValueError('frame count does not match the volume')
    manifest_frames = tuple(ManifestFrame(index, len(frame.readings), digest_bytes(data), frame.source) for index, (frame, data) in enumerate(zip(frames, volume.frames)))
    return IssueManifest(issue_id, revision_id, V1_VERSION, digest_bytes(volume.header), len(manifest_frames), sum(item.reading_count for item in manifest_frames), manifest_frames)
