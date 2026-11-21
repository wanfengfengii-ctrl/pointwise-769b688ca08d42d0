from dataclasses import dataclass

from issue.manifest import IssueManifest, digest_bytes
from issue.manifest_wire import decode_manifest
from issue.package import VolumePackage, decode_package
from media.decode import DecodedVolume, decode_volume
from media.framing import EncodedVolume, V1_VERSION, unpack_header, unpack_frame


@dataclass(frozen=True)
class VerifiedVolume:
    manifest: IssueManifest
    package: VolumePackage
    decoded: DecodedVolume


def _manifest(value):
    return decode_manifest(value) if isinstance(value, (bytes, bytearray, memoryview)) else value


def _package(value):
    return decode_package(value) if isinstance(value, (bytes, bytearray, memoryview)) else value


def verify_volume(manifest, package):
    manifest = _manifest(manifest)
    package = _package(package)
    if not isinstance(manifest, IssueManifest) or not isinstance(package, VolumePackage):
        raise ValueError('manifest and package types are invalid')
    if manifest.version != V1_VERSION or package.version != V1_VERSION:
        raise ValueError('unsupported V1 version')
    if manifest.issue_id != package.issue_id or manifest.revision_id != package.revision_id:
        raise ValueError('manifest and package identity mismatch')
    if digest_bytes(package.header) != manifest.header_digest:
        raise ValueError('header digest mismatch')
    if len(package.frames) != manifest.frame_count:
        raise ValueError('package frame coverage mismatch')
    decoded_frames = []
    for expected_index, (manifest_frame, package_frame) in enumerate(zip(manifest.frames, package.frames)):
        if manifest_frame.frame_index != expected_index or package_frame.frame_index != expected_index:
            raise ValueError('frame index mismatch')
        if digest_bytes(package_frame.data) != manifest_frame.frame_digest:
            raise ValueError('frame digest mismatch')
        values = unpack_frame(package_frame.data)
        if len(values) != manifest_frame.reading_count:
            raise ValueError('frame reading count mismatch')
        decoded_frames.append(package_frame.data)
    volume = EncodedVolume(unpack_header(package.header), tuple(decoded_frames))
    decoded = decode_volume(volume)
    if decoded.frame_counts != tuple(frame.reading_count for frame in manifest.frames):
        raise ValueError('decoded frame count mismatch')
    return VerifiedVolume(manifest, package, decoded)
