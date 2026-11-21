import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class IssuedRecord:
    issue_id: str
    revision_id: str
    manifest: bytes
    package: bytes


class IssuedStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self.fail_next_commit = False
        self.initialize()

    def initialize(self):
        self._connection.execute('CREATE TABLE IF NOT EXISTS issues (issue_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, manifest BLOB NOT NULL, package BLOB NOT NULL)')
        self._connection.commit()

    def commit_issue(self, record):
        should_fail = self.fail_next_commit
        self.fail_next_commit = False
        try:
            self._connection.execute('BEGIN')
            self._connection.execute('INSERT INTO issues VALUES (?, ?, ?, ?)', (record.issue_id, record.revision_id, record.manifest, record.package))
            if should_fail:
                raise RuntimeError('simulated issue commit failure')
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def get_issue(self, issue_id):
        row = self._connection.execute('SELECT issue_id, revision_id, manifest, package FROM issues WHERE issue_id = ?', (issue_id,)).fetchone()
        if row is None:
            raise KeyError('unknown issue')
        return IssuedRecord(row[0], row[1], bytes(row[2]), bytes(row[3]))
