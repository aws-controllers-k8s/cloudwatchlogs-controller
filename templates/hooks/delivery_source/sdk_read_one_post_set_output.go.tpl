	// PutDeliverySource takes a single ResourceArn on input but GetDeliverySource
	// returns it inside the ResourceArns array. The generated mapping only
	// populates Status.ResourceARNs, leaving Spec.ResourceARN nil after a read,
	// so delta.go sees a permanent desired(set)-vs-latest(nil) diff and calls
	// PutDeliverySource on every reconcile. Mirror the first returned ARN back
	// into Spec.ResourceARN.
	if resp.DeliverySource != nil && len(resp.DeliverySource.ResourceArns) > 0 {
		ko.Spec.ResourceARN = &resp.DeliverySource.ResourceArns[0]
	}
	// GetDeliverySource never returns a tags field, so the generated mapping
	// would leave Spec.Tags nil and produce a permanent Spec.Tags delta against
	// any desired tags. Read the live tags from the standalone
	// ListTagsForResource API (the same source rm.syncTags reconciles toward).
	if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
		ko.Spec.Tags, err = getTags(ctx, rm.sdkapi, rm.metrics, string(*ko.Status.ACKResourceMetadata.ARN))
		if err != nil {
			return nil, err
		}
	}
