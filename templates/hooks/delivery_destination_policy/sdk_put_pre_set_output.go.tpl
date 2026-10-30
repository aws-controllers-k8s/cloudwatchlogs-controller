	// PutDeliveryDestinationPolicyOutput.Policy is an optional pointer and the
	// generated output-setting code dereferences it without a nil check. If
	// AWS ever returns an empty body, keep the desired spec (the policy has
	// already been written) rather than panicking after the write.
	if resp.Policy == nil {
		rm.setStatusDefaults(ko)
		return &resource{ko}, nil
	}
