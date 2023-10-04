	if err := rm.addRetentionToSpec(ctx, r, ko); err != nil {
		return nil, err
	}
