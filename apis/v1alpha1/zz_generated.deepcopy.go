//go:build !ignore_autogenerated

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

// Code generated by ack-generate. DO NOT EDIT.

// Code generated by controller-gen. DO NOT EDIT.

package v1alpha1

import (
	corev1alpha1 "github.com/aws-controllers-k8s/runtime/apis/core/v1alpha1"
	runtime "k8s.io/apimachinery/pkg/runtime"
)

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *Destination) DeepCopyInto(out *Destination) {
	*out = *in
	if in.ARN != nil {
		in, out := &in.ARN, &out.ARN
		*out = new(string)
		**out = **in
	}
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.RoleARN != nil {
		in, out := &in.RoleARN, &out.RoleARN
		*out = new(string)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new Destination.
func (in *Destination) DeepCopy() *Destination {
	if in == nil {
		return nil
	}
	out := new(Destination)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *ExportTask) DeepCopyInto(out *ExportTask) {
	*out = *in
	if in.From != nil {
		in, out := &in.From, &out.From
		*out = new(int64)
		**out = **in
	}
	if in.LogGroupName != nil {
		in, out := &in.LogGroupName, &out.LogGroupName
		*out = new(string)
		**out = **in
	}
	if in.To != nil {
		in, out := &in.To, &out.To
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new ExportTask.
func (in *ExportTask) DeepCopy() *ExportTask {
	if in == nil {
		return nil
	}
	out := new(ExportTask)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *ExportTaskExecutionInfo) DeepCopyInto(out *ExportTaskExecutionInfo) {
	*out = *in
	if in.CompletionTime != nil {
		in, out := &in.CompletionTime, &out.CompletionTime
		*out = new(int64)
		**out = **in
	}
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new ExportTaskExecutionInfo.
func (in *ExportTaskExecutionInfo) DeepCopy() *ExportTaskExecutionInfo {
	if in == nil {
		return nil
	}
	out := new(ExportTaskExecutionInfo)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *FilteredLogEvent) DeepCopyInto(out *FilteredLogEvent) {
	*out = *in
	if in.IngestionTime != nil {
		in, out := &in.IngestionTime, &out.IngestionTime
		*out = new(int64)
		**out = **in
	}
	if in.Timestamp != nil {
		in, out := &in.Timestamp, &out.Timestamp
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new FilteredLogEvent.
func (in *FilteredLogEvent) DeepCopy() *FilteredLogEvent {
	if in == nil {
		return nil
	}
	out := new(FilteredLogEvent)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *InputLogEvent) DeepCopyInto(out *InputLogEvent) {
	*out = *in
	if in.Timestamp != nil {
		in, out := &in.Timestamp, &out.Timestamp
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new InputLogEvent.
func (in *InputLogEvent) DeepCopy() *InputLogEvent {
	if in == nil {
		return nil
	}
	out := new(InputLogEvent)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogGroup) DeepCopyInto(out *LogGroup) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ObjectMeta.DeepCopyInto(&out.ObjectMeta)
	in.Spec.DeepCopyInto(&out.Spec)
	in.Status.DeepCopyInto(&out.Status)
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogGroup.
func (in *LogGroup) DeepCopy() *LogGroup {
	if in == nil {
		return nil
	}
	out := new(LogGroup)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyObject is an autogenerated deepcopy function, copying the receiver, creating a new runtime.Object.
func (in *LogGroup) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogGroupList) DeepCopyInto(out *LogGroupList) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ListMeta.DeepCopyInto(&out.ListMeta)
	if in.Items != nil {
		in, out := &in.Items, &out.Items
		*out = make([]LogGroup, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogGroupList.
func (in *LogGroupList) DeepCopy() *LogGroupList {
	if in == nil {
		return nil
	}
	out := new(LogGroupList)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyObject is an autogenerated deepcopy function, copying the receiver, creating a new runtime.Object.
func (in *LogGroupList) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogGroupSpec) DeepCopyInto(out *LogGroupSpec) {
	*out = *in
	if in.KMSKeyID != nil {
		in, out := &in.KMSKeyID, &out.KMSKeyID
		*out = new(string)
		**out = **in
	}
	if in.KMSKeyRef != nil {
		in, out := &in.KMSKeyRef, &out.KMSKeyRef
		*out = new(corev1alpha1.AWSResourceReferenceWrapper)
		(*in).DeepCopyInto(*out)
	}
	if in.Name != nil {
		in, out := &in.Name, &out.Name
		*out = new(string)
		**out = **in
	}
	if in.RetentionDays != nil {
		in, out := &in.RetentionDays, &out.RetentionDays
		*out = new(int64)
		**out = **in
	}
	if in.SubscriptionFilters != nil {
		in, out := &in.SubscriptionFilters, &out.SubscriptionFilters
		*out = make([]*PutSubscriptionFilterInput, len(*in))
		for i := range *in {
			if (*in)[i] != nil {
				in, out := &(*in)[i], &(*out)[i]
				*out = new(PutSubscriptionFilterInput)
				(*in).DeepCopyInto(*out)
			}
		}
	}
	if in.Tags != nil {
		in, out := &in.Tags, &out.Tags
		*out = make(map[string]*string, len(*in))
		for key, val := range *in {
			var outVal *string
			if val == nil {
				(*out)[key] = nil
			} else {
				inVal := (*in)[key]
				in, out := &inVal, &outVal
				*out = new(string)
				**out = **in
			}
			(*out)[key] = outVal
		}
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogGroupSpec.
func (in *LogGroupSpec) DeepCopy() *LogGroupSpec {
	if in == nil {
		return nil
	}
	out := new(LogGroupSpec)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogGroupStatus) DeepCopyInto(out *LogGroupStatus) {
	*out = *in
	if in.ACKResourceMetadata != nil {
		in, out := &in.ACKResourceMetadata, &out.ACKResourceMetadata
		*out = new(corev1alpha1.ResourceMetadata)
		(*in).DeepCopyInto(*out)
	}
	if in.Conditions != nil {
		in, out := &in.Conditions, &out.Conditions
		*out = make([]*corev1alpha1.Condition, len(*in))
		for i := range *in {
			if (*in)[i] != nil {
				in, out := &(*in)[i], &(*out)[i]
				*out = new(corev1alpha1.Condition)
				(*in).DeepCopyInto(*out)
			}
		}
	}
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.DataProtectionStatus != nil {
		in, out := &in.DataProtectionStatus, &out.DataProtectionStatus
		*out = new(string)
		**out = **in
	}
	if in.MetricFilterCount != nil {
		in, out := &in.MetricFilterCount, &out.MetricFilterCount
		*out = new(int64)
		**out = **in
	}
	if in.RetentionInDays != nil {
		in, out := &in.RetentionInDays, &out.RetentionInDays
		*out = new(int64)
		**out = **in
	}
	if in.StoredBytes != nil {
		in, out := &in.StoredBytes, &out.StoredBytes
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogGroupStatus.
func (in *LogGroupStatus) DeepCopy() *LogGroupStatus {
	if in == nil {
		return nil
	}
	out := new(LogGroupStatus)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogGroup_SDK) DeepCopyInto(out *LogGroup_SDK) {
	*out = *in
	if in.ARN != nil {
		in, out := &in.ARN, &out.ARN
		*out = new(string)
		**out = **in
	}
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.DataProtectionStatus != nil {
		in, out := &in.DataProtectionStatus, &out.DataProtectionStatus
		*out = new(string)
		**out = **in
	}
	if in.KMSKeyID != nil {
		in, out := &in.KMSKeyID, &out.KMSKeyID
		*out = new(string)
		**out = **in
	}
	if in.LogGroupName != nil {
		in, out := &in.LogGroupName, &out.LogGroupName
		*out = new(string)
		**out = **in
	}
	if in.MetricFilterCount != nil {
		in, out := &in.MetricFilterCount, &out.MetricFilterCount
		*out = new(int64)
		**out = **in
	}
	if in.RetentionInDays != nil {
		in, out := &in.RetentionInDays, &out.RetentionInDays
		*out = new(int64)
		**out = **in
	}
	if in.StoredBytes != nil {
		in, out := &in.StoredBytes, &out.StoredBytes
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogGroup_SDK.
func (in *LogGroup_SDK) DeepCopy() *LogGroup_SDK {
	if in == nil {
		return nil
	}
	out := new(LogGroup_SDK)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *LogStream) DeepCopyInto(out *LogStream) {
	*out = *in
	if in.ARN != nil {
		in, out := &in.ARN, &out.ARN
		*out = new(string)
		**out = **in
	}
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.FirstEventTimestamp != nil {
		in, out := &in.FirstEventTimestamp, &out.FirstEventTimestamp
		*out = new(int64)
		**out = **in
	}
	if in.LastEventTimestamp != nil {
		in, out := &in.LastEventTimestamp, &out.LastEventTimestamp
		*out = new(int64)
		**out = **in
	}
	if in.LastIngestionTime != nil {
		in, out := &in.LastIngestionTime, &out.LastIngestionTime
		*out = new(int64)
		**out = **in
	}
	if in.StoredBytes != nil {
		in, out := &in.StoredBytes, &out.StoredBytes
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new LogStream.
func (in *LogStream) DeepCopy() *LogStream {
	if in == nil {
		return nil
	}
	out := new(LogStream)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *MetricFilter) DeepCopyInto(out *MetricFilter) {
	*out = *in
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.FilterName != nil {
		in, out := &in.FilterName, &out.FilterName
		*out = new(string)
		**out = **in
	}
	if in.FilterPattern != nil {
		in, out := &in.FilterPattern, &out.FilterPattern
		*out = new(string)
		**out = **in
	}
	if in.LogGroupName != nil {
		in, out := &in.LogGroupName, &out.LogGroupName
		*out = new(string)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new MetricFilter.
func (in *MetricFilter) DeepCopy() *MetricFilter {
	if in == nil {
		return nil
	}
	out := new(MetricFilter)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *OutputLogEvent) DeepCopyInto(out *OutputLogEvent) {
	*out = *in
	if in.IngestionTime != nil {
		in, out := &in.IngestionTime, &out.IngestionTime
		*out = new(int64)
		**out = **in
	}
	if in.Timestamp != nil {
		in, out := &in.Timestamp, &out.Timestamp
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new OutputLogEvent.
func (in *OutputLogEvent) DeepCopy() *OutputLogEvent {
	if in == nil {
		return nil
	}
	out := new(OutputLogEvent)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *PutSubscriptionFilterInput) DeepCopyInto(out *PutSubscriptionFilterInput) {
	*out = *in
	if in.DestinationARN != nil {
		in, out := &in.DestinationARN, &out.DestinationARN
		*out = new(string)
		**out = **in
	}
	if in.Distribution != nil {
		in, out := &in.Distribution, &out.Distribution
		*out = new(string)
		**out = **in
	}
	if in.FilterName != nil {
		in, out := &in.FilterName, &out.FilterName
		*out = new(string)
		**out = **in
	}
	if in.FilterPattern != nil {
		in, out := &in.FilterPattern, &out.FilterPattern
		*out = new(string)
		**out = **in
	}
	if in.RoleARN != nil {
		in, out := &in.RoleARN, &out.RoleARN
		*out = new(string)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new PutSubscriptionFilterInput.
func (in *PutSubscriptionFilterInput) DeepCopy() *PutSubscriptionFilterInput {
	if in == nil {
		return nil
	}
	out := new(PutSubscriptionFilterInput)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *QueryDefinition) DeepCopyInto(out *QueryDefinition) {
	*out = *in
	if in.LastModified != nil {
		in, out := &in.LastModified, &out.LastModified
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new QueryDefinition.
func (in *QueryDefinition) DeepCopy() *QueryDefinition {
	if in == nil {
		return nil
	}
	out := new(QueryDefinition)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *QueryInfo) DeepCopyInto(out *QueryInfo) {
	*out = *in
	if in.CreateTime != nil {
		in, out := &in.CreateTime, &out.CreateTime
		*out = new(int64)
		**out = **in
	}
	if in.LogGroupName != nil {
		in, out := &in.LogGroupName, &out.LogGroupName
		*out = new(string)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new QueryInfo.
func (in *QueryInfo) DeepCopy() *QueryInfo {
	if in == nil {
		return nil
	}
	out := new(QueryInfo)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *ResourcePolicy) DeepCopyInto(out *ResourcePolicy) {
	*out = *in
	if in.LastUpdatedTime != nil {
		in, out := &in.LastUpdatedTime, &out.LastUpdatedTime
		*out = new(int64)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new ResourcePolicy.
func (in *ResourcePolicy) DeepCopy() *ResourcePolicy {
	if in == nil {
		return nil
	}
	out := new(ResourcePolicy)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *SubscriptionFilter) DeepCopyInto(out *SubscriptionFilter) {
	*out = *in
	if in.CreationTime != nil {
		in, out := &in.CreationTime, &out.CreationTime
		*out = new(int64)
		**out = **in
	}
	if in.DestinationARN != nil {
		in, out := &in.DestinationARN, &out.DestinationARN
		*out = new(string)
		**out = **in
	}
	if in.Distribution != nil {
		in, out := &in.Distribution, &out.Distribution
		*out = new(string)
		**out = **in
	}
	if in.FilterName != nil {
		in, out := &in.FilterName, &out.FilterName
		*out = new(string)
		**out = **in
	}
	if in.FilterPattern != nil {
		in, out := &in.FilterPattern, &out.FilterPattern
		*out = new(string)
		**out = **in
	}
	if in.LogGroupName != nil {
		in, out := &in.LogGroupName, &out.LogGroupName
		*out = new(string)
		**out = **in
	}
	if in.RoleARN != nil {
		in, out := &in.RoleARN, &out.RoleARN
		*out = new(string)
		**out = **in
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new SubscriptionFilter.
func (in *SubscriptionFilter) DeepCopy() *SubscriptionFilter {
	if in == nil {
		return nil
	}
	out := new(SubscriptionFilter)
	in.DeepCopyInto(out)
	return out
}
