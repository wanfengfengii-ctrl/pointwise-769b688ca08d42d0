import json

from issue.manifest import IssueManifest, ManifestFrame
from station.provenance import FrameSource


def encode_manifest(manifest):
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
    }
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def decode_manifest(data):
    try:
        value = json.loads(bytes(data).decode('ascii'))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid manifest') from error
    if not isinstance(value, dict):
        raise ValueError('invalid manifest')
    frames = value.get('frames')
    if not isinstance(frames, list):
        raise ValueError('manifest frames must be a list')
    if value.get('frame_count') != len(frames):
        raise ValueError('manifest frame count mismatch')
    parsed = []
    for expected_index, item in enumerate(frames):
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
        parsed.append(ManifestFrame(expected_index, count, digest, FrameSource(source['object_id'], source['frame_index'])))
    total = value.get('total_readings')
    if total != sum(item.reading_count for item in parsed):
        raise ValueError('manifest total reading count mismatch')
    return IssueManifest(value['issue_id'], value['revision_id'], value['version'], value['header_digest'], value['frame_count'], total, tuple(parsed))
