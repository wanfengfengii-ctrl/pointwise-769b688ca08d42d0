import json
import tempfile
from pathlib import Path

from issue.publish import issue
from receive.intake import accept
from receive.ledger import ReceiptLedger
from review.report_store import ReportStore
from review.signoff import report
from station.intake import submit
from station.revisions import freeze_input
from station.revision_store import RevisionStore
from issue.issued_store import IssuedStore


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = RevisionStore(root / 'source.sqlite')
        issued = IssuedStore(root / 'issued.sqlite')
        receiver = ReceiptLedger(root / 'receive.sqlite')
        reports = ReportStore(root / 'reports.sqlite')
        frames = [
            {'readings': [0, -3], 'source': {'object_id': 'meter-A', 'frame_index': 0}},
            {'readings': [4], 'source': {'object_id': 'meter-A', 'frame_index': 1}},
        ]
        draft_id = submit(source, 'batch-demo', frames)
        revision = freeze_input(source, draft_id)
        issued_record = issue(source, issued, revision.revision_id)
        accepted = accept(receiver, issued_record.manifest, issued_record.package)
        signed = report(reports, receiver, accepted.receipt.receipt_id, 3)
        actual_readings = [reading.value for reading in accepted.readings]
        actual_anomalies = [row.value for row in signed.rows]
        payload = {
            'case_id': 'V1',
            'input': frames,
            'expected': [0, -3, 4],
            'actual': actual_readings,
            'downstream_expected': {'anomalies': [-3, 4], 'peak': 4},
            'downstream_actual': {'anomalies': actual_anomalies, 'peak': signed.peak},
            'code_paths': ['station/intake.py', 'station/revisions.py', 'media/encode.py', 'media/decode.py', 'issue/publish.py', 'receive/intake.py', 'review/signoff.py'],
            'oracle': '手算二阶差分并按绝对值大于等于 3 复核全量实收',
        }
        print('POINTWISE_SCENARIO ' + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
