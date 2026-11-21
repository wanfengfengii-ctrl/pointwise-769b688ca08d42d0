import tempfile
import unittest
from pathlib import Path

from issue.manifest_wire import decode_manifest
from station.intake import submit
from station.revisions import freeze_input

from tests.support import make_environment, publish_frames


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.environment = make_environment(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def test_signed_values_and_frame_order(self):
        revision, record = publish_frames(self.environment)
        manifest = decode_manifest(record.manifest)
        self.assertEqual(revision.volume.header_seed, (0, 0))
        self.assertEqual(manifest.frame_count, 2)
        self.assertEqual(manifest.total_readings, 3)
        self.assertEqual([frame.reading_count for frame in manifest.frames], [2, 1])
        self.assertEqual([frame.source.frame_index for frame in manifest.frames], [0, 1])

    def test_snapshot_is_immutable_after_submit(self):
        frames = [{'readings': [1], 'source': {'object_id': 'meter-A', 'frame_index': 0}}]
        draft_id = submit(self.environment['source'], 'batch-snapshot', frames)
        frames[0]['readings'][0] = 99
        revision = freeze_input(self.environment['source'], draft_id)
        self.assertEqual(revision.frames[0].readings, (1,))

    def test_repeat_measurement_keeps_parent(self):
        parent, parent_record = publish_frames(self.environment)
        child_frames = [{'readings': [7, 8], 'source': {'object_id': 'meter-B', 'frame_index': 0}}]
        child, child_record = publish_frames(self.environment, 'batch-A', child_frames, parent.revision_id)
        parent_manifest = decode_manifest(parent_record.manifest)
        child_manifest = decode_manifest(child_record.manifest)
        self.assertNotEqual(parent.revision_id, child.revision_id)
        self.assertEqual(parent_manifest.revision_id, parent.revision_id)
        self.assertEqual(child_manifest.revision_id, child.revision_id)
        self.assertEqual(parent_manifest.total_readings, 3)
        self.assertEqual(child_manifest.total_readings, 2)
        self.assertEqual(self.environment['source'].get_revision(parent.revision_id).frames[0].source.object_id, 'meter-A')

    def test_reject_foreign_parent(self):
        revision_a, _ = publish_frames(self.environment, 'batch-A')
        with self.assertRaises(ValueError):
            submit(self.environment['source'], 'batch-B', [{'readings': [2], 'source': {'object_id': 'meter-B', 'frame_index': 0}}], revision_a.revision_id)
        self.assertEqual(self.environment['source'].get_revision(revision_a.revision_id).batch_id, 'batch-A')

    def test_freeze_commit_failure_can_retry(self):
        frames = [{'readings': [5], 'source': {'object_id': 'meter-A', 'frame_index': 0}}]
        draft_id = submit(self.environment['source'], 'batch-retry', frames)
        self.environment['source'].fail_next_commit = True
        with self.assertRaises(RuntimeError):
            freeze_input(self.environment['source'], draft_id)
        revision = freeze_input(self.environment['source'], draft_id)
        self.assertEqual(revision.frames[0].readings, (5,))
