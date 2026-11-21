import uuid

from receive.ledger import ReceiptLedger
from receive.provenance import attach_provenance
from receive.receipt import AcceptedVolume, make_receipt
from receive.verify import verify_volume


def accept(ledger: ReceiptLedger, manifest, package):
    verified = verify_volume(manifest, package)
    readings = attach_provenance(verified)
    receipt_id = 'receipt-' + uuid.uuid4().hex
    receipt = make_receipt(receipt_id, verified, readings)
    accepted = AcceptedVolume(receipt, readings, manifest if isinstance(manifest, bytes) else __import__('issue.manifest_wire', fromlist=['encode_manifest']).encode_manifest(verified.manifest))
    ledger.commit_acceptance(accepted)
    return accepted


def receipt(ledger: ReceiptLedger, receipt_id):
    return ledger.get_acceptance(receipt_id)
