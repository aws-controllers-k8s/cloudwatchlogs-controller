	// GetDeliveryDestination may not reliably populate the Tags field in the
	// response wrapper. Read the live tags from the standalone
	// ListTagsForResource API (the same source rm.syncTags reconciles toward).
	if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
		ko.Spec.Tags, err = getTags(ctx, rm.sdkapi, rm.metrics, string(*ko.Status.ACKResourceMetadata.ARN))
		if err != nil {
			return nil, err
		}
	}
