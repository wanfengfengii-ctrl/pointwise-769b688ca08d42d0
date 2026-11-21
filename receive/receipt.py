from dataclasses import dataclass

from issue.manifest_wire import encode_manifest
from media.positions import ReadingPosition
from receive.provenance import ReceivedReading
from receive.verify import VerifiedVolume


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    issue_id: str
    revision_id: str
    frame_count: int
    reading_count: int


@dataclass(frozen=True)
class AcceptedVolume:
    receipt: Receipt
    readings: tuple[ReceivedReading, ...]
    manifest: bytes


def make_receipt(receipt_id, verified: VerifiedVolume, readings):
    return Receipt(receipt_id, verified.manifest.issue_id, verified.manifest.revision_id, verified.manifest.frame_count, len(readings))
