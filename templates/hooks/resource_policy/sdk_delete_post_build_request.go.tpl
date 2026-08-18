	// ExpectedRevisionId is required when deleting a resource-scoped policy to
	// guard against concurrent modification. Account-scoped policies do not
	// carry a revision ID, so leave the field unset for them.
	if r.ko.Spec.ResourceARN != nil && r.ko.Status.RevisionID != nil {
		input.ExpectedRevisionId = r.ko.Status.RevisionID
	}
