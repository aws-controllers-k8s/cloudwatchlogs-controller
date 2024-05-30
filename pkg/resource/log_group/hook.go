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

package log_group

import (
	"context"

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"
	svcsdk "github.com/aws/aws-sdk-go/service/cloudwatchlogs"

	svcapitypes "github.com/aws-controllers-k8s/cloudwatchlogs-controller/apis/v1alpha1"
)

func (rm *resourceManager) updateRetentionPeriod(
	ctx context.Context,
	desired *resource,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.updateRetentionPeriod")
	defer func(err error) { exit(err) }(err)

	if desired.ko.Spec.RetentionDays != nil && *desired.ko.Spec.RetentionDays != 0 {
		input := &svcsdk.PutRetentionPolicyInput{
			RetentionInDays: desired.ko.Spec.RetentionDays,
			LogGroupName:    desired.ko.Spec.Name,
		}

		_, err = rm.sdkapi.PutRetentionPolicyWithContext(ctx, input)
		rm.metrics.RecordAPICall("UPDATE", "PutRetentionPolicy", err)
		if err != nil {
			return err
		}
		return nil
	}

	input := &svcsdk.DeleteRetentionPolicyInput{
		LogGroupName: desired.ko.Spec.Name,
	}

	_, err = rm.sdkapi.DeleteRetentionPolicyWithContext(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "DeleteRetentionPolicy", err)
	if err != nil {
		return err
	}
	return nil
}

func (rm *resourceManager) updateSubscriptionFilters(
	ctx context.Context,
	desired, latest *resource,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.updateSubscriptionFilters")
	defer func(err error) {
		exit(err)
	}(err)

	toAdd, toRemove := compareSubscriptionFilters(desired.ko.Spec.SubscriptionFilters, latest.ko.Spec.SubscriptionFilters)
	for _, subscriptionFilter := range toRemove {
		_, err = rm.removeSubscriptionFilter(ctx, desired, subscriptionFilter.FilterName)
		if err != nil {
			return err
		}
	}
	for _, subscriptionFilter := range toAdd {
		_, err = rm.addSubscriptionFilter(ctx, desired, subscriptionFilter)
		if err != nil {
			return err
		}
	}
	return nil
}

// addSubscriptionFilter calls the AWS API to add a subscription filter.
func (rm *resourceManager) addSubscriptionFilter(
	ctx context.Context,
	desired *resource,
	subscriptionFilter *svcapitypes.PutSubscriptionFilterInput,
) (output *svcsdk.PutSubscriptionFilterOutput, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.addSubscriptionFilter")
	defer func(err error) { exit(err) }(err)

	input := &svcsdk.PutSubscriptionFilterInput{
		LogGroupName:   desired.ko.Spec.Name,
		RoleArn:        subscriptionFilter.RoleARN,
		FilterName:     subscriptionFilter.FilterName,
		DestinationArn: subscriptionFilter.DestinationARN,
		FilterPattern:  subscriptionFilter.FilterPattern,
		Distribution:   subscriptionFilter.Distribution,
	}

	output, err = rm.sdkapi.PutSubscriptionFilterWithContext(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "PutSubscriptionFilter", err)
	if err != nil {
		return nil, err
	}
	return output, nil
}

// removeSubscriptionFilter calls the AWS API to delete a subscription filter.
func (rm *resourceManager) removeSubscriptionFilter(
	ctx context.Context,
	desired *resource,
	filterName *string,
) (output *svcsdk.DeleteSubscriptionFilterOutput, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.removeSubscriptionFilter")
	defer func(err error) { exit(err) }(err)

	input := &svcsdk.DeleteSubscriptionFilterInput{
		FilterName:   filterName,
		LogGroupName: desired.ko.Spec.Name,
	}

	output, err = rm.sdkapi.DeleteSubscriptionFilterWithContext(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "DeleteSubscriptionFilter", err)
	if err != nil {
		return nil, err
	}
	return output, nil
}

// customUpdateLogGroup patches each of the resource properties in the backend AWS
// service API and returns a new resource with updated fields.
func (rm *resourceManager) customUpdateLogGroup(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) (updated *resource, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.customUpdateLogGroup")
	defer func(err error) { exit(err) }(err)

	// Merge in the information we read from the API call above to the copy of
	// the original Kubernetes object we passed to the function
	ko := desired.ko.DeepCopy()

	rm.setStatusDefaults(ko)

	if delta.DifferentAt("Spec.RetentionDays") {
		if err := rm.updateRetentionPeriod(ctx, desired); err != nil {
			return &resource{ko}, err
		}
	}
	if delta.DifferentAt("Spec.SubscriptionFilters") {
		if err := rm.updateSubscriptionFilters(ctx, desired, latest); err != nil {
			return &resource{ko}, err
		}
	}

	if desired.ko.Spec.RetentionDays != nil {
		ko.Status.RetentionInDays = desired.ko.Spec.RetentionDays
	} else {
		var retention int64 = 0
		ko.Status.RetentionInDays = &retention
	}

	return &resource{ko}, nil
}

// addRetentionToSpec copies retention value from status to spec so as to
// enable comparison during sdkUpdate phase.
func (rm *resourceManager) addRetentionToSpec(
	ctx context.Context,
	r *resource,
	ko *svcapitypes.LogGroup,
) (err error) {
	ko.Spec.RetentionDays = ko.Status.RetentionInDays
	return
}

// customPreCompare ensures that default values of types are initialised and
// server side defaults are excluded from the delta.
func customPreCompare(
	delta *ackcompare.Delta,
	a *resource,
	b *resource,
) {
	var retention int64 = 0
	if a.ko.Spec.RetentionDays == nil {
		a.ko.Spec.RetentionDays = &retention
	}

	if b.ko.Spec.RetentionDays == nil {
		b.ko.Spec.RetentionDays = &retention
	}
}

func compareSubscriptionFilters(
	desired, observed []*svcapitypes.PutSubscriptionFilterInput,
) (toAdd, toRemove []*svcapitypes.PutSubscriptionFilterInput) {
	for _, subscriptionFilters := range desired {
		found := false
		for _, subscriptionFilters2 := range observed {
			if *subscriptionFilters.FilterName == *subscriptionFilters2.FilterName {
				// if the filter was modified then we need to update it. We do not flag the
				// subscription filter as found, so that we allow the controller to update it.
				if !equalSubscriptionFilters(*subscriptionFilters, *subscriptionFilters2) {
					break
				}
				found = true
				break
			}
		}
		if !found {
			toAdd = append(toAdd, subscriptionFilters)
		}
	}
	for _, subscriptionFilters := range observed {
		found := false
		for _, subscriptionFilters2 := range desired {
			if *subscriptionFilters.FilterName == *subscriptionFilters2.FilterName {
				found = true
				break
			}
		}
		if !found {
			toRemove = append(toRemove, subscriptionFilters)
		}
	}
	return
}

const (
	defaultDistribution = "ByLogStream"
)

func equalSubscriptionFilters(a, b svcapitypes.PutSubscriptionFilterInput) bool {
	if !equalStrings(a.FilterName, b.FilterName) {
		return false
	}
	if !equalStrings(a.DestinationARN, b.DestinationARN) {
		return false
	}
	if !equalStrings(a.FilterPattern, b.FilterPattern) {
		return false
	}
	if !equalStrings(a.RoleARN, b.RoleARN) {
		return false
	}
	if a.Distribution == nil {
		return *b.Distribution == defaultDistribution
	} else {
		return *a.Distribution == *b.Distribution
	}
}

func (rm *resourceManager) getSubscriptionFilters(ctx context.Context, name *string) ([]*svcapitypes.PutSubscriptionFilterInput, error) {
	var err error
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.getSubscriptionFilters")
	defer func(err error) { exit(err) }(err)

	subscriptionFilters := make([]*svcapitypes.PutSubscriptionFilterInput, 0)
	input := &svcsdk.DescribeSubscriptionFiltersInput{
		LogGroupName: name,
	}

	for {
		var resp *svcsdk.DescribeSubscriptionFiltersOutput
		resp, err = rm.sdkapi.DescribeSubscriptionFiltersWithContext(ctx, input)
		rm.metrics.RecordAPICall("READ_MANY", "DescribeSubscriptionFilters", err)
		if err != nil {
			return nil, err
		}

		for _, subscriptionFilter := range resp.SubscriptionFilters {
			subscriptionFilters = append(subscriptionFilters, &svcapitypes.PutSubscriptionFilterInput{
				FilterName:     subscriptionFilter.FilterName,
				DestinationARN: subscriptionFilter.DestinationArn,
				FilterPattern:  subscriptionFilter.FilterPattern,
				RoleARN:        subscriptionFilter.RoleArn,
				Distribution:   subscriptionFilter.Distribution,
			})
		}
		if resp.NextToken == nil {
			break
		}
		input.NextToken = resp.NextToken
	}

	return subscriptionFilters, nil
}

func equalStrings(a, b *string) bool {
	if a == nil {
		return b == nil || *b == ""
	}

	if a != nil && b == nil {
		return false
	}

	return (*a == "" && b == nil) || *a == *b
}
