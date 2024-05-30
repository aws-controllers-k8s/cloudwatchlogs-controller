	if err := rm.addRetentionToSpec(ctx, r, ko); err != nil {
		return nil, err
	}
	ko.Spec.SubscriptionFilters, err = rm.getSubscriptionFilters(ctx, r.ko.Spec.Name)
	if err != nil {
		return nil, err
	}