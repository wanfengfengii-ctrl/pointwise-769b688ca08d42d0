import uuid

from receive.ledger import ReceiptLedger
from review.dispatch import build_dispatch
from review.report_store import ReportStore, SignedReport
from review.thresholds import evaluate_threshold


def report(store: ReportStore, ledger: ReceiptLedger, receipt_id, threshold):
    accepted = ledger.get_acceptance(receipt_id)
    result = evaluate_threshold(accepted.readings, threshold)
    signed = SignedReport('report-' + uuid.uuid4().hex, receipt_id, threshold, result.peak, build_dispatch(result.anomalies))
    store.commit_report(signed)
    return signed


def get_report(store: ReportStore, report_id):
    return store.get_report(report_id)
