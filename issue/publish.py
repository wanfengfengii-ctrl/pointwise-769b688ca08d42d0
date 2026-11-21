import uuid

from issue.issued_store import IssuedRecord
from issue.manifest import build_manifest
from issue.manifest_wire import encode_manifest
from issue.package import build_package, encode_package


def issue(revision_store, issued_store, revision_id):
    revision = revision_store.get_revision(revision_id)
    issue_id = 'issue-' + uuid.uuid4().hex
    manifest = build_manifest(issue_id, revision.revision_id, revision.frames, revision.volume)
    package = build_package(manifest, revision.volume)
    record = IssuedRecord(issue_id, revision.revision_id, encode_manifest(manifest), encode_package(package))
    issued_store.commit_issue(record)
    return record
