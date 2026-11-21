import os
import tempfile
import unittest
from pathlib import Path

from issue.package import PackageFrame, VolumePackage, decode_package, encode_package
from media.framing import pack_frame
from receive.intake import accept, receipt
from tests.support import make_environment, publish_frames, receive_record


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.environment = make_environment(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def test_decode_offline_in_order(self):
        revision, record = publish_frames(self.environment)
        os.remove(self.environment['source'].db_path)
        accepted = receive_record(self.environment, record)
        self.assertEqual([reading.value for reading in accepted.readings], [0, -3, 4])
        self.assertEqual([(reading.position.frame_index, reading.position.reading_index) for reading in accepted.readings], [(0, 0), (0, 1), (1, 0)])
        reopened = type(self.environment['receiver'])(self.environment['receiver'].db_path)
        restored = receipt(reopened, accepted.receipt.receipt_id)
        self.assertEqual([reading.value for reading in restored.readings], [0, -3, 4])
        self.assertEqual(restored.receipt.revision_id, revision.revision_id)

    def test_reject_payload_mismatch(self):
        _, record = publish_frames(self.environment)
        package = decode_package(record.package)
        altered = VolumePackage(package.issue_id, package.revision_id, package.version, package.header, (package.frames[0], PackageFrame(1, pack_frame([11]))))
        with self.assertRaises(ValueError):
            accept(self.environment['receiver'], record.manifest, encode_package(altered))
        with self.assertRaises(KeyError):
            receipt(self.environment['receiver'], 'missing-receipt')

    def test_commit_failure_then_retry(self):
        _, record = publish_frames(self.environment)
        self.environment['receiver'].fail_next_commit = True
        with self.assertRaises(RuntimeError):
            receive_record(self.environment, record)
        with self.assertRaises(KeyError):
            receipt(self.environment['receiver'], 'receipt-that-was-not-created')
        accepted = receive_record(self.environment, record)
        self.assertEqual(accepted.receipt.reading_count, 3)
        reopened = type(self.environment['receiver'])(self.environment['receiver'].db_path)
        self.assertEqual(receipt(reopened, accepted.receipt.receipt_id).receipt.reading_count, 3)

    def test_equal_values_keep_distinct_positions(self):
        frames = [
            {'readings': [2, 2], 'source': {'object_id': 'meter-A', 'frame_index': 0}},
            {'readings': [2], 'source': {'object_id': 'meter-A', 'frame_index': 1}},
        ]
        _, record = publish_frames(self.environment, 'batch-equal', frames)
        accepted = receive_record(self.environment, record)
        self.assertEqual([reading.value for reading in accepted.readings], [2, 2, 2])
        self.assertEqual([reading.position.ordinal for reading in accepted.readings], [0, 1, 2])
        self.assertEqual([reading.source.frame_index for reading in accepted.readings], [0, 0, 1])

    def test_empty_frame_keeps_frame_position(self):
        frames = [
            {'readings': [], 'source': {'object_id': 'meter-A', 'frame_index': 0}},
            {'readings': [4], 'source': {'object_id': 'meter-A', 'frame_index': 1}},
        ]
        _, record = publish_frames(self.environment, 'batch-empty', frames)
        accepted = receive_record(self.environment, record)
        self.assertEqual([reading.value for reading in accepted.readings], [4])
        self.assertEqual(accepted.readings[0].position.frame_index, 1)
        self.assertEqual(accepted.receipt.frame_count, 2)

    def test_reject_mixed_identity(self):
        frames_a = [{'readings': [3], 'source': {'object_id': 'meter-A', 'frame_index': 0}}]
        frames_b = [{'readings': [3], 'source': {'object_id': 'meter-B', 'frame_index': 0}}]
        _, record_a = publish_frames(self.environment, 'batch-A', frames_a)
        _, record_b = publish_frames(self.environment, 'batch-B', frames_b)
        with self.assertRaises(ValueError):
            accept(self.environment['receiver'], record_a.manifest, record_b.package)
