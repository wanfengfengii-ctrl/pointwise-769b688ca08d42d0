import base64
import json
from dataclasses import dataclass

from issue.manifest import IssueManifest
from media.framing import EncodedVolume


@dataclass(frozen=True)
class PackageFrame:
    frame_index: int
    data: bytes


@dataclass(frozen=True)
class VolumePackage:
    issue_id: str
    revision_id: str
    version: int
    header: bytes
    frames: tuple[PackageFrame, ...]


def build_package(manifest: IssueManifest, volume: EncodedVolume):
    if manifest.frame_count != len(volume.frames):
        raise ValueError('package frame count mismatch')
    frames = tuple(PackageFrame(index, data) for index, data in enumerate(volume.frames))
    return VolumePackage(manifest.issue_id, manifest.revision_id, manifest.version, volume.header, frames)


def encode_package(package):
    value = {
        'frames': [{'data': base64.b64encode(frame.data).decode('ascii'), 'frame_index': frame.frame_index} for frame in package.frames],
        'header': base64.b64encode(package.header).decode('ascii'),
        'issue_id': package.issue_id,
        'revision_id': package.revision_id,
        'version': package.version,
    }
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def decode_package(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid package') from error
    if not isinstance(value, dict) or not isinstance(value.get('frames'), list):
        raise ValueError('invalid package')
    frames = []
    for expected_index, item in enumerate(value['frames']):
        if not isinstance(item, dict) or item.get('frame_index') != expected_index:
            raise ValueError('package frame order mismatch')
        try:
            frame_data = base64.b64decode(item['data'].encode('ascii'), validate=True)
        except (KeyError, ValueError) as error:
            raise ValueError('invalid package frame') from error
        frames.append(PackageFrame(expected_index, frame_data))
    try:
        header = base64.b64decode(value['header'].encode('ascii'), validate=True)
    except (KeyError, ValueError) as error:
        raise ValueError('invalid package header') from error
    return VolumePackage(value['issue_id'], value['revision_id'], value['version'], header, tuple(frames))
