// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

package delivery_source

import (
	"context"

	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"

	"github.com/aws-controllers-k8s/cloudwatchlogs-controller/pkg/sync"
)

// getTags reads the live tags of a delivery source via the standalone
// ListTagsForResource API. PutDeliverySource/GetDeliverySource do not expose
// tags on an existing resource, so this is the authoritative drift source for
// both the read path and syncTags.
var getTags = sync.GetResourceTags

// syncTags reconciles a delivery source's tags using the standalone
// TagResource/UntagResource API. It is invoked from the sdk_update_pre_build_request
// hook (see generator.yaml): when Spec.Tags differs the hook calls this, and
// when Spec.Tags is the only field that differs the hook then short-circuits
// before PutDeliverySource, which rejects tags on update with ConflictException.
//
// The add/remove diff is computed against the LIVE tags read from AWS via
// getTags (ListTagsForResource), not against latest.ko.Spec.Tags. latest is
// the reconciler's view, and PutDeliverySource/GetDeliverySource never return
// tags, so Spec.Tags reflects live state only on the sdkFind path. On the
// create/update path it can be nil or already equal to desired (EnsureTags
// merges the controller default tags into desired before the delta is taken),
// which nets added/removed to empty and silently no-ops. Reading live tags
// here makes the diff authoritative regardless of which path invoked syncTags.
func (rm *resourceManager) syncTags(
	ctx context.Context,
	desired *resource,
	latest *resource,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.syncTags")
	defer func() { exit(err) }()

	arn := string(*latest.ko.Status.ACKResourceMetadata.ARN)
	currentTags, err := getTags(ctx, rm.sdkapi, rm.metrics, arn)
	if err != nil {
		return err
	}
	return sync.SyncResourceTags(
		ctx,
		rm.sdkapi,
		rm.metrics,
		arn,
		desired.ko.Spec.Tags,
		currentTags,
		convertToOrderedACKTags,
	)
}
