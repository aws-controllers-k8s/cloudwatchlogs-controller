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

package resource_policy

import (
	"context"

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/cloudwatchlogs"
)

// customUpdateResourcePolicy updates the resource policy by calling
// PutResourcePolicy (which is an idempotent upsert operation).
func (rm *resourceManager) customUpdateResourcePolicy(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) (updated *resource, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.customUpdateResourcePolicy")
	defer func(err error) { exit(err) }(err)

	ko := desired.ko.DeepCopy()
	ko.Status = latest.ko.Status
	rm.setStatusDefaults(ko)

	input := &svcsdk.PutResourcePolicyInput{}
	if desired.ko.Spec.PolicyName != nil {
		input.PolicyName = desired.ko.Spec.PolicyName
	}
	if desired.ko.Spec.PolicyDocument != nil {
		input.PolicyDocument = desired.ko.Spec.PolicyDocument
	}
	if desired.ko.Spec.ResourceARN != nil {
		input.ResourceArn = desired.ko.Spec.ResourceARN
		// Resource-scoped policies require the current revision ID to prevent
		// concurrent modification errors.
		if latest.ko.Status.RevisionID != nil {
			input.ExpectedRevisionId = latest.ko.Status.RevisionID
		}
	}

	resp, err := rm.sdkapi.PutResourcePolicy(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "PutResourcePolicy", err)
	if err != nil {
		return &resource{ko}, err
	}

	if resp.ResourcePolicy != nil {
		if resp.ResourcePolicy.LastUpdatedTime != nil {
			ko.Status.LastUpdatedTime = resp.ResourcePolicy.LastUpdatedTime
		}
		if resp.ResourcePolicy.PolicyDocument != nil {
			ko.Spec.PolicyDocument = resp.ResourcePolicy.PolicyDocument
		}
		if resp.ResourcePolicy.RevisionId != nil {
			ko.Status.RevisionID = resp.ResourcePolicy.RevisionId
		}
		policyScope := string(resp.ResourcePolicy.PolicyScope)
		if policyScope != "" {
			ko.Status.PolicyScope = &policyScope
		}
	}

	return &resource{ko}, nil
}
