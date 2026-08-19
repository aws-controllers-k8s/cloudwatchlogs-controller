	// PutResourcePolicy returns the revision ID of the updated policy at the top
	// level of the response, and only for resource-scoped policies. The nested
	// ResourcePolicy shape does not carry it on writes, so the generated mapping
	// above nulls Status.RevisionID. Prefer the top-level value so the status
	// reflects the new revision after an update and the delete guard has the
	// current ExpectedRevisionId.
	if resp.RevisionId != nil {
		ko.Status.RevisionID = resp.RevisionId
	}
