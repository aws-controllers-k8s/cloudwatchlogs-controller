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

// customCheckRequiredFieldsMissing returns true when the resource does not
// carry enough information to uniquely identify a ResourcePolicy in the
// DescribeResourcePolicies (ReadMany) call.
//
// DescribeResourcePolicies has no required input fields, so without this check
// an empty resource would match the first policy the API returns. During
// adoption that means an arbitrary account-scoped policy is adopted when the
// user supplies neither identifier. Account-scoped policies are keyed by
// PolicyName and resource-scoped policies by ResourceARN, so require at least
// one of them before attempting the lookup; otherwise sdkFind returns NotFound.
func (rm *resourceManager) customCheckRequiredFieldsMissing(
	r *resource,
) bool {
	return r.ko.Spec.PolicyName == nil && r.ko.Spec.ResourceARN == nil
}
