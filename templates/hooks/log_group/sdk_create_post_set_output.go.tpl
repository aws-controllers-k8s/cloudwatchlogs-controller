	if err := rm.updateRetentionPeriod(ctx, desired); err != nil {
		return nil, err
	}
	if desired.ko.Spec.RetentionDays != nil {
		ko.Status.RetentionInDays = desired.ko.Spec.RetentionDays
	} else {
		var retention int64 = 0
		ko.Status.RetentionInDays = &retention
	}
