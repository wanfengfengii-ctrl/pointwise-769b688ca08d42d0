import sqlite3
from dataclasses import dataclass

from media.positions import ReadingPosition
from receive.provenance import ReceivedReading
from receive.receipt import AcceptedVolume, Receipt
from station.provenance import FrameSource


class ReceiptLedger:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self.fail_next_commit = False
        self.initialize()

    def initialize(self):
        self._connection.executescript('''
            CREATE TABLE IF NOT EXISTS acceptances (
                receipt_id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                frame_count INTEGER NOT NULL,
                reading_count INTEGER NOT NULL,
                manifest BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS readings (
                receipt_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                frame_index INTEGER NOT NULL,
                reading_index INTEGER NOT NULL,
                value INTEGER NOT NULL,
                object_id TEXT NOT NULL,
                source_frame_index INTEGER NOT NULL,
                PRIMARY KEY (receipt_id, ordinal),
                FOREIGN KEY (receipt_id) REFERENCES acceptances(receipt_id)
            );
        ''')
        columns = {row[1] for row in self._connection.execute('PRAGMA table_info(readings)')}
        if 'correction_id' not in columns:
            self._connection.execute('ALTER TABLE readings ADD COLUMN correction_id TEXT')
        self._connection.commit()

    def commit_acceptance(self, accepted: AcceptedVolume):
        receipt = accepted.receipt
        should_fail = self.fail_next_commit
        self.fail_next_commit = False
        try:
            self._connection.execute('BEGIN')
            self._connection.execute('INSERT INTO acceptances VALUES (?, ?, ?, ?, ?, ?)', (receipt.receipt_id, receipt.issue_id, receipt.revision_id, receipt.frame_count, receipt.reading_count, accepted.manifest))
            for reading in accepted.readings:
                self._connection.execute(
                    'INSERT INTO readings VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (receipt.receipt_id, reading.position.ordinal, reading.position.frame_index, reading.position.reading_index, reading.value, reading.source.object_id, reading.source.frame_index, reading.correction_id),
                )
            if should_fail:
                raise RuntimeError('simulated receipt commit failure')
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def get_acceptance(self, receipt_id):
        row = self._connection.execute('SELECT receipt_id, issue_id, revision_id, frame_count, reading_count, manifest FROM acceptances WHERE receipt_id = ?', (receipt_id,)).fetchone()
        if row is None:
            raise KeyError('unknown receipt')
        rows = self._connection.execute('SELECT ordinal, frame_index, reading_index, value, object_id, source_frame_index, correction_id FROM readings WHERE receipt_id = ? ORDER BY ordinal', (receipt_id,)).fetchall()
        readings = tuple(ReceivedReading(row[1], row[2], ReadingPosition(item[1], item[2], item[0]), item[3], FrameSource(item[4], item[5]), item[6]) for item in rows)
        receipt = Receipt(row[0], row[1], row[2], row[3], row[4])
        manifest = row[5]
        if isinstance(manifest, str):
            manifest = manifest.encode('ascii')
        return AcceptedVolume(receipt, readings, bytes(manifest))
