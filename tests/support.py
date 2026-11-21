from issue.issued_store import IssuedStore
from issue.publish import issue
from receive.intake import accept
from receive.ledger import ReceiptLedger
from review.report_store import ReportStore
from station.intake import submit
from station.revisions import freeze_input
from station.revision_store import RevisionStore


def make_environment(root):
    return {
        'source': RevisionStore(root / 'source.sqlite'),
        'issued': IssuedStore(root / 'issued.sqlite'),
        'receiver': ReceiptLedger(root / 'receive.sqlite'),
        'reports': ReportStore(root / 'reports.sqlite'),
    }


def publish_frames(environment, batch_id='batch-A', frames=None, parent_revision_id=None):
    if frames is None:
        frames = [
            {'readings': [0, -3], 'source': {'object_id': 'meter-A', 'frame_index': 0}},
            {'readings': [4], 'source': {'object_id': 'meter-A', 'frame_index': 1}},
        ]
    draft_id = submit(environment['source'], batch_id, frames, parent_revision_id)
    revision = freeze_input(environment['source'], draft_id)
    record = issue(environment['source'], environment['issued'], revision.revision_id)
    return revision, record


def receive_record(environment, record):
    return accept(environment['receiver'], record.manifest, record.package)
