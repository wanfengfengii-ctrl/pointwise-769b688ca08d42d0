from station.frame_validation import validate_frames


def submit(store, batch_id, frames, parent_revision_id=None):
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise ValueError('batch_id must be a non-empty string')
    normalized = validate_frames(frames)
    if parent_revision_id is not None:
        parent = store.get_revision(parent_revision_id)
        if parent.batch_id != batch_id:
            raise ValueError('parent revision belongs to another batch')
    return store.add_draft(batch_id, normalized, parent_revision_id)
