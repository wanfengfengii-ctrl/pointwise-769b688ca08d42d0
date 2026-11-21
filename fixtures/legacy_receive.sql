BEGIN;
CREATE TABLE IF NOT EXISTS acceptances (receipt_id TEXT PRIMARY KEY, issue_id TEXT NOT NULL, revision_id TEXT NOT NULL, frame_count INTEGER NOT NULL, reading_count INTEGER NOT NULL, manifest BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS readings (receipt_id TEXT NOT NULL, ordinal INTEGER NOT NULL, frame_index INTEGER NOT NULL, reading_index INTEGER NOT NULL, value INTEGER NOT NULL, object_id TEXT NOT NULL, source_frame_index INTEGER NOT NULL, PRIMARY KEY(receipt_id, ordinal));
INSERT INTO acceptances VALUES ('legacy-receipt-1', 'legacy-issue-1', 'legacy-revision-1', 2, 3, '{}');
INSERT INTO readings VALUES ('legacy-receipt-1', 0, 0, 0, 0, 'legacy-meter', 0);
INSERT INTO readings VALUES ('legacy-receipt-1', 1, 0, 1, -3, 'legacy-meter', 0);
INSERT INTO readings VALUES ('legacy-receipt-1', 2, 1, 0, 4, 'legacy-meter', 1);
COMMIT;
