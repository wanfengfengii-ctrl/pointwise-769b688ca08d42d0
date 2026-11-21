import json
import tempfile
from pathlib import Path

from issue.issued_store import IssuedStore
from issue.publish import issue, make_replacement
from issue.replacement_manifest_wire import decode_replacement_manifest
from issue.replacement_package import decode_replacement_package
from receive.intake import accept, receipt, receive_replacement
from receive.ledger import ReceiptLedger
from review.report_store import ReportStore
from review.signoff import report
from station.intake import submit
from station.revisions import freeze_input
from station.revision_store import RevisionStore


FRAMES = [
    {'readings': [1], 'source': {'object_id': 'rig-A', 'frame_index': 20}},
    {'readings': [2], 'source': {'object_id': 'rig-A', 'frame_index': 21}},
    {'readings': [3], 'source': {'object_id': 'rig-A', 'frame_index': 22}},
    {'readings': [4], 'source': {'object_id': 'rig-A', 'frame_index': 23}},
]


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = RevisionStore(root / 'source.sqlite')
        issued = IssuedStore(root / 'issued.sqlite')
        receiver = ReceiptLedger(root / 'receive.sqlite')
        reports = ReportStore(root / 'reports.sqlite')

        draft_id = submit(source, 'rig-day', FRAMES)
        revision = freeze_input(source, draft_id)
        # The original revision is still issued through the V1 path.
        v1_record = issue(source, issued, revision.revision_id)
        v1_accepted = accept(receiver, v1_record.manifest, v1_record.package)

        # The day shift freezes a frame replacement for the out-of-tolerance
        # second frame (frame_index 1) and publishes the two V2 materials.
        replacement = make_replacement(source, issued, revision.revision_id, 1, 1, [[10]], 'QC-17')
        manifest = decode_replacement_manifest(replacement.manifest)
        package = decode_replacement_package(replacement.package)
        retained_indices = [frame.frame_index for frame in package.frames if type(frame).__name__ == 'RetainedFrame']
        corrected_indices = [frame.frame_index for frame in package.frames if type(frame).__name__ == 'CorrectedFrame']
        seam = manifest.continuation.frame_states[1]
        seam_basis = {
            'revision_id': manifest.continuation.revision_id,
            'window': [manifest.first_frame, manifest.last_frame],
            'frame_1_entry': [seam.entry_value, seam.entry_delta],
            'frame_1_exit': [seam.exit_value, seam.exit_delta],
            'digest': manifest.continuation.digest,
            'package_digest': package.continuation_digest,
        }

        # The night shift has only the independently delivered manifest and
        # package: remove every source-side database before acceptance.
        source_path, issued_path = source.db_path, issued.db_path
        del source, issued
        Path(source_path).unlink()
        Path(issued_path).unlink()
        accepted = receive_replacement(receiver, replacement.manifest, replacement.package)

        # Reopen the night ledger from scratch and reclaim by receipt id.
        receipt_id = accepted.receipt.receipt_id
        del receiver
        reopened = ReceiptLedger(root / 'receive.sqlite')
        restored = receipt(reopened, receipt_id)

        signed = report(reports, reopened, receipt_id, 5)
        payload = {
            'case_id': 'V2-frame-replacement',
            'input': FRAMES,
            'window': [1, 1],
            'correction_id': 'QC-17',
            'expected': [1, 10, 3, 4],
            'actual': [row.value for row in restored.readings],
            'positions': [[row.position.frame_index, row.position.reading_index, row.position.ordinal] for row in restored.readings],
            'sources': [[row.source.object_id, row.source.frame_index] for row in restored.readings],
            'corrections': [row.correction_id for row in restored.readings],
            'retained_frame_indices': retained_indices,
            'corrected_frame_indices': corrected_indices,
            'offline_acceptance': True,
            'reopened_receipt_id': receipt_id,
            'seam_basis': seam_basis,
            'v1_expected': [1, 2, 3, 4],
            'v1_actual': [row.value for row in v1_accepted.readings],
            'downstream_expected': {'anomalies': [10], 'peak': 10},
            'downstream_actual': {'anomalies': [row.value for row in signed.rows], 'peak': signed.peak},
            'code_paths': ['issue/publish.py', 'issue/replacement_manifest.py', 'issue/replacement_package.py', 'receive/replacement_verify.py', 'receive/intake.py', 'receive/ledger.py', 'media/stream.py'],
            'oracle': '手算二阶差分接缝：更正帧只替换实收正文，后缀保留帧按原流帧1出口状态(值=2,一阶差分=1)续解',
        }
        print('POINTWISE_SCENARIO ' + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
