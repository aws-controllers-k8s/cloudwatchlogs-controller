	// PutDeliverySource rejects an update that carries tags with
	// ConflictException ("Tags can only be provided when a resource is being
	// created, not updated."). Tags are reconciled out of band by rm.syncTags
	// (custom_sync on the Tags field), so strip them from the update payload.
	// This guards the case where a non-tag field changes alongside tags: the
	// generated sdkUpdate still falls through to PutDeliverySource, and without
	// this the generated newUpdateRequestPayload would resend Spec.Tags.
	input.Tags = nil
