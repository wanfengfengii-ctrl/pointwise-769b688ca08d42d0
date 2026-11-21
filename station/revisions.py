from media.encode import encode_volume


def freeze_input(store, draft_id):
    draft = store.get_pending_draft(draft_id)
    volume = encode_volume(draft.frames)
    return store.commit_freeze(draft_id, volume)
