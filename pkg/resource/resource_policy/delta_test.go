// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/

package resource_policy

import (
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/stretchr/testify/assert"

	svcapitypes "github.com/aws-controllers-k8s/cloudwatchlogs-controller/apis/v1alpha1"
)

func resourceWithPolicy(name, doc string) *resource {
	return &resource{
		ko: &svcapitypes.ResourcePolicy{
			Spec: svcapitypes.ResourcePolicySpec{
				PolicyName:     aws.String(name),
				PolicyDocument: aws.String(doc),
			},
		},
	}
}

// policyBase and policyReordered are semantically identical IAM policies —
// same statements, different order and formatting. Without is_iam_policy the
// delta comparison would see them as different and trigger a spurious
// PutResourcePolicy call on every reconcile.
const policyBase = `{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowRoute53Logs",
      "Effect": "Allow",
      "Principal": {"Service": "route53.amazonaws.com"},
      "Action": "logs:PutLogEvents",
      "Resource": "arn:aws:logs:*:*:log-group:/aws/route53/*:*"
    },
    {
      "Sid": "AllowCWLogs",
      "Effect": "Allow",
      "Principal": {"Service": "delivery.logs.amazonaws.com"},
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}`

// Same policy — statements reversed, Action for first stmt as array.
const policyReordered = `{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCWLogs",
      "Effect": "Allow",
      "Principal": {"Service": "delivery.logs.amazonaws.com"},
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    },
    {
      "Sid": "AllowRoute53Logs",
      "Effect": "Allow",
      "Principal": {"Service": "route53.amazonaws.com"},
      "Action": ["logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/route53/*:*"
    }
  ]
}`

// Genuinely different policy — one statement removed.
const policyOnlyRoute53 = `{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowRoute53Logs",
      "Effect": "Allow",
      "Principal": {"Service": "route53.amazonaws.com"},
      "Action": "logs:PutLogEvents",
      "Resource": "arn:aws:logs:*:*:log-group:/aws/route53/*:*"
    }
  ]
}`

func TestDelta_PolicyDocument_SemanticEquality(t *testing.T) {
	// Two semantically identical policies must produce zero delta — this is the
	// core regression test for is_iam_policy vs is_document. With is_document
	// (DocumentEqual), statement reordering and Action string-vs-array would
	// produce a spurious delta and trigger PutResourcePolicy every reconcile.
	a := resourceWithPolicy("my-policy", policyBase)
	b := resourceWithPolicy("my-policy", policyReordered)

	delta := newResourceDelta(a, b)
	assert.False(t, delta.DifferentAt("Spec.PolicyDocument"),
		"reordered/reformatted but semantically identical policy should produce no delta")
}

func TestDelta_PolicyDocument_ActualChange(t *testing.T) {
	// A genuinely different policy (one statement removed) must be detected.
	a := resourceWithPolicy("my-policy", policyBase)
	b := resourceWithPolicy("my-policy", policyOnlyRoute53)

	delta := newResourceDelta(a, b)
	assert.True(t, delta.DifferentAt("Spec.PolicyDocument"),
		"policy with a statement removed must produce a delta")
}

func TestDelta_PolicyDocument_NilHandling(t *testing.T) {
	a := resourceWithPolicy("my-policy", policyBase)
	b := &resource{
		ko: &svcapitypes.ResourcePolicy{
			Spec: svcapitypes.ResourcePolicySpec{
				PolicyName:     aws.String("my-policy"),
				PolicyDocument: nil,
			},
		},
	}

	delta := newResourceDelta(a, b)
	assert.True(t, delta.DifferentAt("Spec.PolicyDocument"),
		"nil vs non-nil policy document must produce a delta")
}

func TestDelta_PolicyName_Immutable(t *testing.T) {
	// PolicyName is immutable — a name change must always be detected.
	a := resourceWithPolicy("policy-a", policyBase)
	b := resourceWithPolicy("policy-b", policyBase)

	delta := newResourceDelta(a, b)
	assert.True(t, delta.DifferentAt("Spec.PolicyName"),
		"different policy names must produce a delta")
}

func TestDelta_NoChange(t *testing.T) {
	// Identical resources must produce empty delta.
	a := resourceWithPolicy("my-policy", policyBase)
	b := resourceWithPolicy("my-policy", policyBase)

	delta := newResourceDelta(a, b)
	assert.False(t, delta.DifferentAt("Spec.PolicyDocument"))
	assert.False(t, delta.DifferentAt("Spec.PolicyName"))
	assert.Equal(t, 0, len(delta.Differences))
}
