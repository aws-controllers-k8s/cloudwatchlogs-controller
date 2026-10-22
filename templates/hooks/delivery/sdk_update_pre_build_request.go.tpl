	// Tags are reconciled out of band through the standalone Tag API, not
	// through UpdateDeliveryConfiguration (which does not accept tags).
	if delta.DifferentAt("Spec.Tags") {
		if err = rm.syncTags(ctx, desired, latest); err != nil {
			return nil, err
		}
	}
	// When Spec.Tags is the ONLY field that differs, syncTags has already
	// applied the change and there is nothing left for
	// UpdateDeliveryConfiguration to do. Return the desired state with the
	// latest status merged in, mirroring the generated update's success path,
	// without calling UpdateDeliveryConfiguration.
	if !delta.DifferentExcept("Spec.Tags") {
		updatedDesired := desired.DeepCopy()
		updatedDesired.SetStatus(latest)
		return rm.concreteResource(updatedDesired), nil
	}
