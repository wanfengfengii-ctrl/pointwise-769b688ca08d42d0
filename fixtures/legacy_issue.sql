BEGIN;
CREATE TABLE IF NOT EXISTS issues (issue_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, manifest BLOB NOT NULL, package BLOB NOT NULL);
INSERT INTO issues(issue_id, revision_id, manifest, package) VALUES ('legacy-issue-1', 'legacy-revision-1', readfile('fixtures/legacy_manifest.json'), readfile('fixtures/legacy_package.json'));
COMMIT;
