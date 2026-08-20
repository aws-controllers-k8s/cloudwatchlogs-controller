	// A ResourceArn identifies a resource-scoped policy, which must be queried
	// with the RESOURCE policy scope. DescribeResourcePolicies defaults to the
	// ACCOUNT scope and rejects any request that pairs a ResourceArn with it.
	if r.ko.Spec.ResourceARN != nil {
		input.PolicyScope = svcsdktypes.PolicyScopeResource
	}
