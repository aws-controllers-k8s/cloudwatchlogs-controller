	// ExpectedRevisionId guards against concurrent modification and is only
	// valid for resource-scoped policies (those with a ResourceArn). Account
	// scoped policies do not carry a revision ID, so leave the field unset.
	if desired.ko.Spec.ResourceARN != nil && latest.ko.Status.RevisionID != nil {
		input.ExpectedRevisionId = latest.ko.Status.RevisionID
	}
