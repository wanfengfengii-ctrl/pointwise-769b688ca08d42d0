import dataclasses
import os
import tempfile
import unittest
from pathlib import Path

from issue.manifest import digest_bytes
from issue.manifest_wire import decode_manifest
from issue.publish import issue, make_replacement
from issue.replacement_manifest_wire import decode_replacement_manifest
from issue.replacement_package import (
    CorrectedFrame,
    ReplacementPackage,
    RetainedFrame,
    decode_replacement_package,
    encode_replacement_package,
)
from receive.intake import accept, receive_replacement, receipt
from station.intake import submit
from station.revisions import freeze_input
from tests.support import make_environment


RIG_FRAMES = [
    {'readings': [1], 'source': {'object_id': 'rig-A', 'frame_index': 20}},
    {'readings': [2], 'source': {'object_id': 'rig-A', 'frame_index': 21}},
    {'readings': [3], 'source': {'object_id': 'rig-A', 'frame_index': 22}},
    {'readings': [4], 'source': {'object_id': 'rig-A', 'frame_index': 23}},
]


def freeze(environment, batch_id, frames, parent_revision_id=None):
    draft_id = submit(environment['source'], batch_id, frames, parent_revision_id)
    return freeze_input(environment['source'], draft_id)


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.environment = make_environment(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def _rig_revision(self, frames=None):
        return freeze(self.environment, 'rig-day', RIG_FRAMES if frames is None else frames)

    def test_second_frame_correction_matches_readme_sample(self):
        revision = self._rig_revision()
        original_volume = revision.volume
        record = make_replacement(
            self.environment['source'],
            self.environment['issued'],
            revision.revision_id,
            1,
            1,
            [[10]],
            'QC-17',
        )
        self.assertEqual(self.environment['issued'].get_issue(record.issue_id).package, record.package)
        manifest = decode_replacement_manifest(record.manifest)
        package = decode_replacement_package(record.package)
        self.assertEqual(manifest.version, 2)
        self.assertEqual(package.version, 2)
        self.assertEqual((manifest.first_frame, manifest.last_frame), (1, 1))
        self.assertEqual(manifest.correction_id, 'QC-17')
        self.assertEqual([type(frame).__name__ for frame in package.frames],
                         ['RetainedFrame', 'CorrectedFrame', 'RetainedFrame', 'RetainedFrame'])
        # Retained frames are byte-for-byte identical to the original volume.
        for index in (0, 2, 3):
            self.assertEqual(package.frames[index].data, original_volume.frames[index])
        self.assertEqual(package.header, original_volume.header)
        # Window manifest entries still describe original counts, digests and sources.
        self.assertEqual(manifest.frames[1].reading_count, 1)
        self.assertEqual(manifest.frames[1].frame_digest, digest_bytes(original_volume.frames[1]))
        self.assertEqual(manifest.frames[1].source.frame_index, 21)

        accepted = receive_replacement(self.environment['receiver'], record.manifest, record.package)
        self.assertEqual([row.value for row in accepted.readings], [1, 10, 3, 4])
        self.assertEqual([row.position.ordinal for row in accepted.readings], [0, 1, 2, 3])
        self.assertEqual([row.position.frame_index for row in accepted.readings], [0, 1, 2, 3])
        self.assertEqual([row.source.frame_index for row in accepted.readings], [20, 21, 22, 23])
        self.assertEqual([row.source.object_id for row in accepted.readings], ['rig-A'] * 4)
        self.assertEqual([row.correction_id for row in accepted.readings], [None, 'QC-17', None, None])
        self.assertEqual(accepted.receipt.reading_count, 4)
        self.assertEqual(accepted.receipt.frame_count, 4)

    def test_reopen_ledger_returns_correction_provenance(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        accepted = receive_replacement(self.environment['receiver'], record.manifest, record.package)
        reopened = type(self.environment['receiver'])(self.environment['receiver'].db_path)
        restored = receipt(reopened, accepted.receipt.receipt_id)
        self.assertEqual([row.value for row in restored.readings], [1, 10, 3, 4])
        self.assertEqual([row.correction_id for row in restored.readings], [None, 'QC-17', None, None])
        self.assertEqual(restored.manifest, record.manifest)

    def test_offline_receipt_after_source_removed(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        os.remove(self.environment['source'].db_path)
        os.remove(self.environment['issued'].db_path)
        accepted = receive_replacement(self.environment['receiver'], record.manifest, record.package)
        self.assertEqual([row.value for row in accepted.readings], [1, 10, 3, 4])

    def test_next_revision_same_retained_bytes_different_decode(self):
        first = self._rig_revision()
        first_record = make_replacement(self.environment['source'], self.environment['issued'], first.revision_id, 1, 1, [[10]], 'QC-17')
        second = freeze(
            self.environment,
            'rig-day',
            [
                {'readings': [2], 'source': {'object_id': 'rig-A', 'frame_index': 20}},
                {'readings': [4], 'source': {'object_id': 'rig-A', 'frame_index': 21}},
                {'readings': [6], 'source': {'object_id': 'rig-A', 'frame_index': 22}},
                {'readings': [8], 'source': {'object_id': 'rig-A', 'frame_index': 23}},
            ],
            first.revision_id,
        )
        second_record = make_replacement(self.environment['source'], self.environment['issued'], second.revision_id, 1, 1, [[40]], 'QC-18')
        first_package = decode_replacement_package(first_record.package)
        second_package = decode_replacement_package(second_record.package)
        # Frames 2 and 3 carry identical original encoded bytes across revisions.
        self.assertEqual(first_package.frames[2].data, second_package.frames[2].data)
        self.assertEqual(first_package.frames[3].data, second_package.frames[3].data)
        accepted = receive_replacement(self.environment['receiver'], second_record.manifest, second_record.package)
        self.assertEqual([row.value for row in accepted.readings], [2, 40, 6, 8])

    def test_crossed_continuation_basis_is_rejected(self):
        first = self._rig_revision()
        first_record = make_replacement(self.environment['source'], self.environment['issued'], first.revision_id, 1, 1, [[10]], 'QC-17')
        second = freeze(
            self.environment,
            'rig-day',
            [
                {'readings': [2], 'source': {'object_id': 'rig-A', 'frame_index': 20}},
                {'readings': [4], 'source': {'object_id': 'rig-A', 'frame_index': 21}},
                {'readings': [6], 'source': {'object_id': 'rig-A', 'frame_index': 22}},
                {'readings': [8], 'source': {'object_id': 'rig-A', 'frame_index': 23}},
            ],
            first.revision_id,
        )
        second_record = make_replacement(self.environment['source'], self.environment['issued'], second.revision_id, 1, 1, [[40]], 'QC-18')
        # First revision's continuation basis spliced into the second issue.
        first_manifest = decode_replacement_manifest(first_record.manifest)
        second_package = decode_replacement_package(second_record.package)
        tampered_package = dataclasses.replace(second_package, continuation_digest=first_manifest.continuation.digest)
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], second_record.manifest, tampered_package)
        # And the reverse direction: second basis with the first issue.
        second_manifest = decode_replacement_manifest(second_record.manifest)
        first_package = decode_replacement_package(first_record.package)
        tampered_first = dataclasses.replace(first_package, continuation_digest=second_manifest.continuation.digest)
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], first_record.manifest, tampered_first)

    def test_empty_frames_window_sample(self):
        frames = [
            {'readings': [], 'source': {'object_id': 'rig-B', 'frame_index': 0}},
            {'readings': [1, 2], 'source': {'object_id': 'rig-B', 'frame_index': 1}},
            {'readings': [], 'source': {'object_id': 'rig-B', 'frame_index': 2}},
            {'readings': [3, 4], 'source': {'object_id': 'rig-B', 'frame_index': 3}},
        ]
        revision = freeze(self.environment, 'rig-empty', frames)
        record = make_replacement(
            self.environment['source'],
            self.environment['issued'],
            revision.revision_id,
            0,
            2,
            [[], [7, -2], []],
            'QC-E',
        )
        package = decode_replacement_package(record.package)
        self.assertEqual([type(frame).__name__ for frame in package.frames],
                         ['CorrectedFrame', 'CorrectedFrame', 'CorrectedFrame', 'RetainedFrame'])
        accepted = receive_replacement(self.environment['receiver'], record.manifest, record.package)
        self.assertEqual([row.value for row in accepted.readings], [7, -2, 3, 4])
        self.assertEqual([row.position.frame_index for row in accepted.readings], [1, 1, 3, 3])
        self.assertEqual([row.position.ordinal for row in accepted.readings], [0, 1, 2, 3])
        self.assertEqual([row.source.frame_index for row in accepted.readings], [1, 1, 3, 3])
        self.assertEqual([row.correction_id for row in accepted.readings], ['QC-E', 'QC-E', None, None])
        self.assertEqual(accepted.receipt.frame_count, 4)

    def test_window_covering_first_last_and_full_volume(self):
        revision = self._rig_revision()
        first_record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 0, 0, [[9]], 'QC-F')
        first_accepted = receive_replacement(self.environment['receiver'], first_record.manifest, first_record.package)
        self.assertEqual([row.value for row in first_accepted.readings], [9, 2, 3, 4])

        last_record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 3, 3, [[99]], 'QC-L')
        last_accepted = receive_replacement(self.environment['receiver'], last_record.manifest, last_record.package)
        self.assertEqual([row.value for row in last_accepted.readings], [1, 2, 3, 99])

        full_record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 0, 3, [[-1], [-2], [-3], [-4]], 'QC-ALL')
        full_package = decode_replacement_package(full_record.package)
        self.assertTrue(all(isinstance(frame, CorrectedFrame) for frame in full_package.frames))
        full_accepted = receive_replacement(self.environment['receiver'], full_record.manifest, full_record.package)
        self.assertEqual([row.value for row in full_accepted.readings], [-1, -2, -3, -4])
        self.assertEqual([row.correction_id for row in full_accepted.readings], ['QC-ALL'] * 4)

    def test_reject_tampered_retained_bytes(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        package = decode_replacement_package(record.package)
        from media.framing import pack_frame

        tampered_frames = list(package.frames)
        tampered_frames[2] = RetainedFrame(2, pack_frame([123]))
        tampered = dataclasses.replace(package, frames=tuple(tampered_frames))
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, tampered)

    def test_reject_tampered_corrected_content(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        package = decode_replacement_package(record.package)
        tampered_frames = list(package.frames)
        tampered_frames[1] = CorrectedFrame(1, (11,))
        tampered = dataclasses.replace(package, frames=tuple(tampered_frames))
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, tampered)

    def test_reject_window_and_identity_mismatches(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        package = decode_replacement_package(record.package)
        manifest = decode_replacement_manifest(record.manifest)

        wrong_window = dataclasses.replace(package, first_frame=0)
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, wrong_window)
        wrong_correction = dataclasses.replace(package, correction_id='QC-99')
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, wrong_correction)

        another = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 2, 2, [[30]], 'QC-18')
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], another.manifest, record.package)
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, another.package)
        # V1 and V2 materials must not be mixed.
        v1_record = issue(self.environment['source'], self.environment['issued'], revision.revision_id)
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, v1_record.package)
        with self.assertRaises(ValueError):
            accept(self.environment['receiver'], record.manifest, record.package)
        self.assertEqual(manifest.issue_id, record.issue_id)

    def test_reject_missing_and_duplicate_frames(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        package = decode_replacement_package(record.package)
        missing = dataclasses.replace(package, frames=package.frames[:3])
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, encode_replacement_package(missing))
        duplicated = dataclasses.replace(package, frames=package.frames[:3] + (package.frames[2],))
        with self.assertRaises(ValueError):
            receive_replacement(self.environment['receiver'], record.manifest, encode_replacement_package(duplicated))

    def test_invalid_window_arguments(self):
        revision = self._rig_revision()
        empty_revision = freeze(
            self.environment,
            'rig-empty-volume',
            [],
        )
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 2, 1, [[1]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, -1, 1, [[1]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 0, 4, [[1]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 0, 0, [], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10, 11]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10.0]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[True]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [['10']], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], '  ')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], empty_revision.revision_id, 0, 0, [[]], 'QC')
        with self.assertRaises(ValueError):
            make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[1 << 63]], 'QC')
        with self.assertRaises(KeyError):
            make_replacement(self.environment['source'], self.environment['issued'], 'revision-missing', 1, 1, [[10]], 'QC')

    def test_commit_failure_leaves_no_partial_acceptance(self):
        revision = self._rig_revision()
        record = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[10]], 'QC-17')
        self.environment['receiver'].fail_next_commit = True
        with self.assertRaises(RuntimeError):
            receive_replacement(self.environment['receiver'], record.manifest, record.package)
        with self.assertRaises(KeyError):
            receipt(self.environment['receiver'], 'receipt-that-was-not-created')
        accepted = receive_replacement(self.environment['receiver'], record.manifest, record.package)
        self.assertEqual(accepted.receipt.reading_count, 4)

    def test_v1_chain_and_legacy_library_remain_intact(self):
        from tests.support import publish_frames, receive_record

        revision, v1_record = publish_frames(self.environment)
        v1_manifest = decode_manifest(v1_record.manifest)
        self.assertEqual(v1_manifest.version, 1)
        accepted = receive_record(self.environment, v1_record)
        self.assertEqual([row.correction_id for row in accepted.readings], [None, None, None])
        reopened = type(self.environment['receiver'])(self.environment['receiver'].db_path)
        restored = receipt(reopened, accepted.receipt.receipt_id)
        self.assertEqual([row.value for row in restored.readings], [0, -3, 4])
        # A V2 receipt and a V1 receipt coexist in the same ledger.
        replacement = make_replacement(self.environment['source'], self.environment['issued'], revision.revision_id, 1, 1, [[4]], 'QC-X')
        v2_accepted = receive_replacement(self.environment['receiver'], replacement.manifest, replacement.package)
        self.assertEqual(len(self.environment['receiver']._connection.execute('SELECT receipt_id FROM acceptances').fetchall()), 2)
        again = receipt(reopened, v2_accepted.receipt.receipt_id)
        self.assertEqual([row.value for row in again.readings], [0, -3, 4])


if __name__ == '__main__':
    unittest.main()
