import json
import sqlite3
import uuid
from dataclasses import dataclass

from media.framing import EncodedVolume
from station.frame_validation import SubmittedFrame
from station.provenance import FrameSource


@dataclass(frozen=True)
class DraftRecord:
    draft_id: str
    batch_id: str
    frames: tuple[SubmittedFrame, ...]
    parent_revision_id: str | None


@dataclass(frozen=True)
class FrozenRevision:
    revision_id: str
    batch_id: str
    frames: tuple[SubmittedFrame, ...]
    parent_revision_id: str | None
    volume: EncodedVolume


def _frames_json(frames):
    return json.dumps([{'readings': list(frame.readings), 'source': frame.source.as_dict()} for frame in frames], separators=(',', ':'), sort_keys=True)


def _frames_from_json(value):
    raw = json.loads(value)
    return tuple(SubmittedFrame(index, tuple(item['readings']), FrameSource(item['source']['object_id'], item['source']['frame_index'])) for index, item in enumerate(raw))


def _volume_json(volume):
    return json.dumps({'header_seed': list(volume.header_seed), 'frames': [data.decode('ascii') for data in volume.frames]}, separators=(',', ':'), sort_keys=True)


def _volume_from_json(value):
    raw = json.loads(value)
    return EncodedVolume(tuple(raw['header_seed']), tuple(data.encode('ascii') for data in raw['frames']))


class RevisionStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self.fail_next_commit = False
        self.initialize()

    def initialize(self):
        self._connection.executescript('''
            CREATE TABLE IF NOT EXISTS drafts (
                draft_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                parent_revision_id TEXT,
                frames_json TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                parent_revision_id TEXT,
                frames_json TEXT NOT NULL,
                volume_json TEXT NOT NULL
            );
        ''')
        self._connection.commit()

    def add_draft(self, batch_id, frames, parent_revision_id=None):
        draft_id = 'draft-' + uuid.uuid4().hex
        self._connection.execute('INSERT INTO drafts VALUES (?, ?, ?, ?, ?)', (draft_id, batch_id, parent_revision_id, _frames_json(frames), 'pending'))
        self._connection.commit()
        return draft_id

    def get_pending_draft(self, draft_id):
        row = self._connection.execute('SELECT draft_id, batch_id, frames_json, parent_revision_id, status FROM drafts WHERE draft_id = ?', (draft_id,)).fetchone()
        if row is None:
            raise KeyError('unknown draft')
        if row[4] != 'pending':
            raise ValueError('draft is no longer pending')
        return DraftRecord(row[0], row[1], _frames_from_json(row[2]), row[3])

    def commit_freeze(self, draft_id, volume):
        if not isinstance(volume, EncodedVolume):
            raise TypeError('volume must be an EncodedVolume')
        row = self._connection.execute('SELECT batch_id, parent_revision_id, frames_json, status FROM drafts WHERE draft_id = ?', (draft_id,)).fetchone()
        if row is None:
            raise KeyError('unknown draft')
        if row[3] != 'pending':
            raise ValueError('draft is no longer pending')
        revision_id = 'revision-' + uuid.uuid4().hex
        should_fail = self.fail_next_commit
        self.fail_next_commit = False
        try:
            self._connection.execute('BEGIN')
            self._connection.execute('INSERT INTO revisions VALUES (?, ?, ?, ?, ?)', (revision_id, row[0], row[1], row[2], _volume_json(volume)))
            self._connection.execute('UPDATE drafts SET status = ? WHERE draft_id = ?', ('frozen', draft_id))
            if should_fail:
                raise RuntimeError('simulated freeze commit failure')
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return FrozenRevision(revision_id, row[0], _frames_from_json(row[2]), row[1], volume)

    def get_revision(self, revision_id):
        row = self._connection.execute('SELECT revision_id, batch_id, parent_revision_id, frames_json, volume_json FROM revisions WHERE revision_id = ?', (revision_id,)).fetchone()
        if row is None:
            raise KeyError('unknown revision')
        return FrozenRevision(row[0], row[1], _frames_from_json(row[3]), row[2], _volume_from_json(row[4]))
