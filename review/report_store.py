import json
import sqlite3
from dataclasses import dataclass

from media.positions import ReadingPosition
from review.dispatch import RetestRow
from station.provenance import FrameSource


@dataclass(frozen=True)
class SignedReport:
    report_id: str
    receipt_id: str
    threshold: int
    peak: int | None
    rows: tuple[RetestRow, ...]


def _rows_json(rows):
    return json.dumps([{'value': row.value, 'position': {'frame_index': row.position.frame_index, 'reading_index': row.position.reading_index, 'ordinal': row.position.ordinal}, 'source': row.source.as_dict()} for row in rows], separators=(',', ':'), sort_keys=True)


def _rows_from_json(value):
    raw = json.loads(value)
    return tuple(RetestRow(item['value'], ReadingPosition(item['position']['frame_index'], item['position']['reading_index'], item['position']['ordinal']), FrameSource(item['source']['object_id'], item['source']['frame_index'])) for item in raw)


class ReportStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self.fail_next_commit = False
        self.initialize()

    def initialize(self):
        self._connection.execute('CREATE TABLE IF NOT EXISTS reports (report_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL, threshold INTEGER NOT NULL, peak INTEGER, rows_json TEXT NOT NULL)')
        self._connection.commit()

    def commit_report(self, report):
        should_fail = self.fail_next_commit
        self.fail_next_commit = False
        try:
            self._connection.execute('BEGIN')
            self._connection.execute('INSERT INTO reports VALUES (?, ?, ?, ?, ?)', (report.report_id, report.receipt_id, report.threshold, report.peak, _rows_json(report.rows)))
            if should_fail:
                raise RuntimeError('simulated report commit failure')
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def get_report(self, report_id):
        row = self._connection.execute('SELECT report_id, receipt_id, threshold, peak, rows_json FROM reports WHERE report_id = ?', (report_id,)).fetchone()
        if row is None:
            raise KeyError('unknown report')
        return SignedReport(row[0], row[1], row[2], row[3], _rows_from_json(row[4]))
