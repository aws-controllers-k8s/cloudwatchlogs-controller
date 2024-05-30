	if err := rm.updateRetentionPeriod(ctx, desired); err != nil {
		return nil, err
	}
	if desired.ko.Spec.RetentionDays != nil {
		ko.Status.RetentionInDays = desired.ko.Spec.RetentionDays
	} else {
		var retention int64 = 0
		ko.Status.RetentionInDays = &retention
	}
	// Well well, the ack runtime logic does some desired on latest data merge
	// which is later persisted in the api-server. This behaviour causes the
	// controller to deleted the conttent of subscription filters in the api-server
	// and detect no delta triggering no updates to the SubscriptionFilters.
	//
	// It's the first we see this issue. @a-hilaly to investigate and determine
	// whether this is a bug everywhere or something specific to cloudwatch.
	if len(desired.ko.Spec.SubscriptionFilters) > 0 {
		return &resource{ko}, &ackrequeue.RequeueNeeded{}
	}
