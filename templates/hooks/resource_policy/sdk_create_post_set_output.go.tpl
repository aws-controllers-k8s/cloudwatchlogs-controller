	// PutResourcePolicy returns the revision ID of the created policy at the top
	// level of the response, and only for resource-scoped policies. The nested
	// ResourcePolicy shape does not carry it on writes, so the generated mapping
	// above nulls Status.RevisionID. Prefer the top-level value so the status
	// reflects the revision immediately after create without waiting for a
	// subsequent read.
	if resp.RevisionId != nil {
		ko.Status.RevisionID = resp.RevisionId
	}
