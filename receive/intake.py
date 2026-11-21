import uuid

from issue.manifest_wire import encode_manifest
from issue.replacement_manifest_wire import encode_replacement_manifest
from receive.ledger import ReceiptLedger
from receive.provenance import attach_provenance, attach_replacement_provenance
from receive.receipt import AcceptedVolume, Receipt, make_receipt
from receive.replacement_verify import verify_replacement
from receive.verify import verify_volume


def accept(ledger: ReceiptLedger, manifest, package):
    verified = verify_volume(manifest, package)
    readings = attach_provenance(verified)
    receipt_id = 'receipt-' + uuid.uuid4().hex
    receipt = make_receipt(receipt_id, verified, readings)
    accepted = AcceptedVolume(receipt, readings, manifest if isinstance(manifest, bytes) else encode_manifest(verified.manifest))
    ledger.commit_acceptance(accepted)
    return accepted


def receive_replacement(ledger: ReceiptLedger, manifest, package):
    verified = verify_replacement(manifest, package)
    readings = attach_replacement_provenance(verified)
    receipt_id = 'receipt-' + uuid.uuid4().hex
    receipt = Receipt(
        receipt_id,
        verified.manifest.issue_id,
        verified.manifest.revision_id,
        verified.manifest.frame_count,
        len(readings),
    )
    manifest_bytes = manifest if isinstance(manifest, bytes) else encode_replacement_manifest(verified.manifest)
    accepted = AcceptedVolume(receipt, readings, manifest_bytes)
    ledger.commit_acceptance(accepted)
    return accepted


def receipt(ledger: ReceiptLedger, receipt_id):
    return ledger.get_acceptance(receipt_id)
