import tempfile
import unittest
from pathlib import Path

from receive.intake import receipt
from review.signoff import get_report, report
from tests.support import make_environment, publish_frames, receive_record


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.environment = make_environment(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def _accepted(self, frames=None):
        _, record = publish_frames(self.environment, 'batch-report', frames)
        return receive_record(self.environment, record)

    def test_inclusive_threshold(self):
        accepted = self._accepted()
        signed = report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, 3)
        self.assertEqual([row.value for row in signed.rows], [-3, 4])
        self.assertEqual([row.position.ordinal for row in signed.rows], [1, 2])
        self.assertEqual(signed.peak, 4)
        reopened = type(self.environment['reports'])(self.environment['reports'].db_path)
        restored = get_report(reopened, signed.report_id)
        self.assertEqual([row.value for row in restored.rows], [-3, 4])

    def test_peak_below_threshold_is_retained(self):
        accepted = self._accepted()
        signed = report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, 5)
        self.assertEqual(signed.rows, ())
        self.assertEqual(signed.peak, 4)

    def test_zero_threshold_includes_zero(self):
        frames = [{'readings': [0], 'source': {'object_id': 'meter-A', 'frame_index': 0}}]
        accepted = self._accepted(frames)
        signed = report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, 0)
        self.assertEqual([row.value for row in signed.rows], [0])

    def test_empty_volume_has_no_peak(self):
        frames = [
            {'readings': [], 'source': {'object_id': 'meter-A', 'frame_index': 0}},
            {'readings': [], 'source': {'object_id': 'meter-A', 'frame_index': 1}},
        ]
        accepted = self._accepted(frames)
        signed = report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, 0)
        self.assertEqual(signed.rows, ())
        self.assertIsNone(signed.peak)

    def test_negative_threshold_is_rejected(self):
        accepted = self._accepted()
        with self.assertRaises(ValueError):
            report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, -1)
        self.assertEqual(receipt(self.environment['receiver'], accepted.receipt.receipt_id).receipt.reading_count, 3)

    def test_report_commit_failure_leaves_no_report(self):
        accepted = self._accepted()
        self.environment['reports'].fail_next_commit = True
        with self.assertRaises(RuntimeError):
            report(self.environment['reports'], self.environment['receiver'], accepted.receipt.receipt_id, 3)
        with self.assertRaises(KeyError):
            get_report(self.environment['reports'], 'missing-report')
