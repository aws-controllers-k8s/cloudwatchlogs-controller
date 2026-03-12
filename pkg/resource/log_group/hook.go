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
	svcsdk "github.com/aws/aws-sdk-go-v2/service/cloudwatchlogs"
	svcsdktypes "github.com/aws/aws-sdk-go-v2/service/cloudwatchlogs/types"
	"github.com/aws/aws-sdk-go/aws"

	svcapitypes "github.com/aws-controllers-k8s/cloudwatchlogs-controller/apis/v1alpha1"
	"github.com/aws-controllers-k8s/cloudwatchlogs-controller/pkg/sync"
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
			RetentionInDays: aws.Int32(int32(*desired.ko.Spec.RetentionDays)),
			LogGroupName:    desired.ko.Spec.Name,
		}

		_, err = rm.sdkapi.PutRetentionPolicy(ctx, input)
		rm.metrics.RecordAPICall("UPDATE", "PutRetentionPolicy", err)
		if err != nil {
			return err
		}
		return nil
	}

	input := &svcsdk.DeleteRetentionPolicyInput{
		LogGroupName: desired.ko.Spec.Name,
	}

	_, err = rm.sdkapi.DeleteRetentionPolicy(ctx, input)
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
	}
	if subscriptionFilter.Distribution != nil {
		input.Distribution = svcsdktypes.Distribution(*subscriptionFilter.Distribution)
	}

	output, err = rm.sdkapi.PutSubscriptionFilter(ctx, input)
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

	output, err = rm.sdkapi.DeleteSubscriptionFilter(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "DeleteSubscriptionFilter", err)
	if err != nil {
		return nil, err
	}
	return output, nil
}

var getTags = sync.GetResourceTags

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
	ko.Status = latest.ko.Status
	rm.setStatusDefaults(ko)

	if delta.DifferentAt("Spec.Tags") {
		err = sync.SyncResourceTags(ctx, rm.sdkapi, rm.metrics, string(*latest.ko.Status.ACKResourceMetadata.ARN), desired.ko.Spec.Tags, latest.ko.Spec.Tags, convertToOrderedACKTags)
		if err != nil {
			return &resource{ko}, err
		}
	}
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
	if delta.DifferentAt("Spec.MetricFilters") {
		if err := rm.updateMetricFilters(ctx, desired, latest); err != nil {
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
		resp, err = rm.sdkapi.DescribeSubscriptionFilters(ctx, input)
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
				Distribution:   aws.String(string(subscriptionFilter.Distribution)),
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

func (rm *resourceManager) updateMetricFilters(
	ctx context.Context,
	desired, latest *resource,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.updateMetricFilters")
	defer func(err error) {
		exit(err)
	}(err)

	toAdd, toRemove := compareMetricFilters(desired.ko.Spec.MetricFilters, latest.ko.Spec.MetricFilters)
	for _, metricFilter := range toRemove {
		_, err = rm.removeMetricFilter(ctx, desired, metricFilter.FilterName)
		if err != nil {
			return err
		}
	}
	for _, metricFilter := range toAdd {
		_, err = rm.addMetricFilter(ctx, desired, metricFilter)
		if err != nil {
			return err
		}
	}
	return nil
}

// addMetricFilter calls the AWS API to add a metric filter.
func (rm *resourceManager) addMetricFilter(
	ctx context.Context,
	desired *resource,
	metricFilter *svcapitypes.PutMetricFilterInput,
) (output *svcsdk.PutMetricFilterOutput, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.addMetricFilter")
	defer func(err error) { exit(err) }(err)

	input := &svcsdk.PutMetricFilterInput{
		LogGroupName:  desired.ko.Spec.Name,
		FilterName:    metricFilter.FilterName,
		FilterPattern: metricFilter.FilterPattern,
	}
	if metricFilter.MetricTransformations != nil {
		transformations := make([]svcsdktypes.MetricTransformation, 0, len(metricFilter.MetricTransformations))
		for _, mt := range metricFilter.MetricTransformations {
			t := svcsdktypes.MetricTransformation{}
			if mt.MetricName != nil {
				t.MetricName = mt.MetricName
			}
			if mt.MetricNamespace != nil {
				t.MetricNamespace = mt.MetricNamespace
			}
			if mt.MetricValue != nil {
				t.MetricValue = mt.MetricValue
			}
			if mt.DefaultValue != nil {
				t.DefaultValue = mt.DefaultValue
			}
			if mt.Unit != nil {
				t.Unit = svcsdktypes.StandardUnit(*mt.Unit)
			}
			if mt.Dimensions != nil {
				dims := make(map[string]string, len(mt.Dimensions))
				for k, v := range mt.Dimensions {
					if v != nil {
						dims[k] = *v
					}
				}
				t.Dimensions = dims
			}
			transformations = append(transformations, t)
		}
		input.MetricTransformations = transformations
	}

	output, err = rm.sdkapi.PutMetricFilter(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "PutMetricFilter", err)
	if err != nil {
		return nil, err
	}
	return output, nil
}

// removeMetricFilter calls the AWS API to delete a metric filter.
func (rm *resourceManager) removeMetricFilter(
	ctx context.Context,
	desired *resource,
	filterName *string,
) (output *svcsdk.DeleteMetricFilterOutput, err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.removeMetricFilter")
	defer func(err error) { exit(err) }(err)

	input := &svcsdk.DeleteMetricFilterInput{
		FilterName:   filterName,
		LogGroupName: desired.ko.Spec.Name,
	}

	output, err = rm.sdkapi.DeleteMetricFilter(ctx, input)
	rm.metrics.RecordAPICall("UPDATE", "DeleteMetricFilter", err)
	if err != nil {
		return nil, err
	}
	return output, nil
}

func (rm *resourceManager) getMetricFilters(ctx context.Context, name *string) ([]*svcapitypes.PutMetricFilterInput, error) {
	var err error
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.getMetricFilters")
	defer func(err error) { exit(err) }(err)

	metricFilters := make([]*svcapitypes.PutMetricFilterInput, 0)
	input := &svcsdk.DescribeMetricFiltersInput{
		LogGroupName: name,
	}

	for {
		var resp *svcsdk.DescribeMetricFiltersOutput
		resp, err = rm.sdkapi.DescribeMetricFilters(ctx, input)
		rm.metrics.RecordAPICall("READ_MANY", "DescribeMetricFilters", err)
		if err != nil {
			return nil, err
		}

		for _, mf := range resp.MetricFilters {
			pmfi := &svcapitypes.PutMetricFilterInput{
				FilterName:    mf.FilterName,
				FilterPattern: mf.FilterPattern,
			}
			if mf.MetricTransformations != nil {
				transformations := make([]*svcapitypes.MetricTransformation, 0, len(mf.MetricTransformations))
				for _, mt := range mf.MetricTransformations {
					t := &svcapitypes.MetricTransformation{
						MetricName:      mt.MetricName,
						MetricNamespace: mt.MetricNamespace,
						MetricValue:     mt.MetricValue,
						DefaultValue:    mt.DefaultValue,
					}
					if mt.Unit != "" {
						unit := string(mt.Unit)
						t.Unit = &unit
					}
					if mt.Dimensions != nil {
						dims := make(map[string]*string, len(mt.Dimensions))
						for k, v := range mt.Dimensions {
							vCopy := v
							dims[k] = &vCopy
						}
						t.Dimensions = dims
					}
					transformations = append(transformations, t)
				}
				pmfi.MetricTransformations = transformations
			}
			metricFilters = append(metricFilters, pmfi)
		}
		if resp.NextToken == nil {
			break
		}
		input.NextToken = resp.NextToken
	}

	return metricFilters, nil
}

func compareMetricFilters(
	desired, observed []*svcapitypes.PutMetricFilterInput,
) (toAdd, toRemove []*svcapitypes.PutMetricFilterInput) {
	for _, d := range desired {
		found := false
		for _, o := range observed {
			if *d.FilterName == *o.FilterName {
				if !equalMetricFilters(*d, *o) {
					break
				}
				found = true
				break
			}
		}
		if !found {
			toAdd = append(toAdd, d)
		}
	}
	for _, o := range observed {
		found := false
		for _, d := range desired {
			if *o.FilterName == *d.FilterName {
				found = true
				break
			}
		}
		if !found {
			toRemove = append(toRemove, o)
		}
	}
	return
}

func equalMetricFilters(a, b svcapitypes.PutMetricFilterInput) bool {
	if !equalStrings(a.FilterName, b.FilterName) {
		return false
	}
	if !equalStrings(a.FilterPattern, b.FilterPattern) {
		return false
	}
	if len(a.MetricTransformations) != len(b.MetricTransformations) {
		return false
	}
	for i := range a.MetricTransformations {
		if !equalMetricTransformations(a.MetricTransformations[i], b.MetricTransformations[i]) {
			return false
		}
	}
	return true
}

func equalMetricTransformations(a, b *svcapitypes.MetricTransformation) bool {
	if a == nil && b == nil {
		return true
	}
	if a == nil || b == nil {
		return false
	}
	if !equalStrings(a.MetricName, b.MetricName) {
		return false
	}
	if !equalStrings(a.MetricNamespace, b.MetricNamespace) {
		return false
	}
	if !equalStrings(a.MetricValue, b.MetricValue) {
		return false
	}
	if !equalStrings(a.Unit, b.Unit) {
		return false
	}
	// Compare DefaultValue
	if (a.DefaultValue == nil) != (b.DefaultValue == nil) {
		return false
	}
	if a.DefaultValue != nil && *a.DefaultValue != *b.DefaultValue {
		return false
	}
	return true
}
