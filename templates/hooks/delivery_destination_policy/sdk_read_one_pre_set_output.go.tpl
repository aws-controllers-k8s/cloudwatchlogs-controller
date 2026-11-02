	// GetDeliveryDestinationPolicyOutput.Policy is an optional pointer. The
	// generated output-setting code dereferences resp.Policy without a nil
	// check, so guard against a 200 response with an empty body (e.g. a
	// destination that exists but has no policy attached yet). Treat that as
	// NotFound so the reconciler runs sdkCreate instead of panicking.
	// This hook runs after the API error handling, so resp is non-nil here.
	// Confirmed: AWS returns HTTP 200 with {"policy":{}} for a destination that
	// exists but has no policy; ResourceNotFoundException is only returned when
	// the destination itself does not exist.
	if resp.Policy == nil || resp.Policy.DeliveryDestinationPolicy == nil {
		return nil, ackerr.NotFound
	}
