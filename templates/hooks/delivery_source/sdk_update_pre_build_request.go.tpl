	// Tags are reconciled out of band through the standalone Tag API, not
	// through PutDeliverySource (which rejects tags on update with
	// ConflictException). custom_sync would wire this automatically but also
	// emits an unconditional post-create requeue this resource does not want,
	// so the update-path tag sync is wired here instead.
	if delta.DifferentAt("Spec.Tags") {
		if err = rm.syncTags(ctx, desired, latest); err != nil {
			return nil, err
		}
	}
	// When Spec.Tags is the ONLY field that differs, syncTags has already
	// applied the change and there is nothing left for PutDeliverySource to do
	// (and issuing it would risk resending tags). Return the desired state with
	// the latest status merged in, mirroring the generated update's success
	// path, without calling PutDeliverySource.
	if !delta.DifferentExcept("Spec.Tags") {
		updatedDesired := desired.DeepCopy()
		updatedDesired.SetStatus(latest)
		return rm.concreteResource(updatedDesired), nil
	}
