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

package delivery_destination_policy

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"testing"

	ackerr "github.com/aws-controllers-k8s/runtime/pkg/errors"
	ackmetrics "github.com/aws-controllers-k8s/runtime/pkg/metrics"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/cloudwatchlogs"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	svcapitypes "github.com/aws-controllers-k8s/cloudwatchlogs-controller/apis/v1alpha1"
)

// mockHTTPClient is a simple mock implementing svcsdk.HTTPClient (the
// Do(*http.Request) (*http.Response, error) interface). Each test sets the
// response that the mock returns.
type mockHTTPClient struct {
	statusCode int
	body       string
}

func (m *mockHTTPClient) Do(req *http.Request) (*http.Response, error) {
	return &http.Response{
		StatusCode: m.statusCode,
		Header:     http.Header{"Content-Type": []string{"application/x-amz-json-1.1"}},
		Body:       io.NopCloser(bytes.NewBufferString(m.body)),
	}, nil
}

// newTestResourceManager builds a resourceManager backed by a mock HTTP client
// so that sdkFind can be called without hitting AWS.
func newTestResourceManager(mock *mockHTTPClient) *resourceManager {
	client := svcsdk.New(svcsdk.Options{
		Region:     "us-east-1",
		HTTPClient: mock,
	})
	return &resourceManager{
		sdkapi:  client,
		metrics: ackmetrics.NewMetrics("cloudwatchlogs"),
	}
}

func emptyDeliveryDestinationPolicy(ddName string) *resource {
	return &resource{
		ko: &svcapitypes.DeliveryDestinationPolicy{
			Spec: svcapitypes.DeliveryDestinationPolicySpec{
				DeliveryDestinationName: &ddName,
			},
		},
	}
}

// TestSdkFind_EmptyPolicy_ReturnsNotFound verifies that when a delivery
// destination exists but has no policy attached, AWS returns HTTP 200 with
// {"policy":{}}, the SDK output has a non-nil Policy whose
// DeliveryDestinationPolicy is nil, and sdkFind returns ackerr.NotFound.
func TestSdkFind_EmptyPolicy_ReturnsNotFound(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	mock := &mockHTTPClient{
		statusCode: 200,
		body:       `{"policy":{}}`,
	}
	rm := newTestResourceManager(mock)
	r := emptyDeliveryDestinationPolicy("my-destination")

	latest, err := rm.sdkFind(context.Background(), r)

	require.Error(err)
	assert.ErrorIs(err, ackerr.NotFound)
	assert.Nil(latest)
}

// TestSdkFind_ResourceNotFoundException_ReturnsNotFound verifies that when the
// delivery destination itself does not exist, AWS returns
// ResourceNotFoundException and sdkFind returns ackerr.NotFound.
func TestSdkFind_ResourceNotFoundException_ReturnsNotFound(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	mock := &mockHTTPClient{
		statusCode: 400,
		body:       `{"__type":"ResourceNotFoundException","message":"The specified resource does not exist."}`,
	}
	rm := newTestResourceManager(mock)
	r := emptyDeliveryDestinationPolicy("nonexistent-destination")

	latest, err := rm.sdkFind(context.Background(), r)

	require.Error(err)
	assert.ErrorIs(err, ackerr.NotFound)
	assert.Nil(latest)
}

// TestSdkFind_PolicyPresent_ReturnsResource verifies that when a policy is
// present, sdkFind returns the resource with Spec.Policy populated and no
// error.
func TestSdkFind_PolicyPresent_ReturnsResource(t *testing.T) {
	assert := assert.New(t)
	require := require.New(t)

	policyDoc := `{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::123456789012:root"},"Action":"logs:CreateDelivery","Resource":"*"}]}`
	// The deliveryDestinationPolicy value is a JSON-encoded string, so the
	// inner quotes must be escaped in the outer JSON envelope.
	mock := &mockHTTPClient{
		statusCode: 200,
		body:       `{"policy":{"deliveryDestinationPolicy":"{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":\"arn:aws:iam::123456789012:root\"},\"Action\":\"logs:CreateDelivery\",\"Resource\":\"*\"}]}"}}`,
	}
	rm := newTestResourceManager(mock)
	r := emptyDeliveryDestinationPolicy("my-destination")

	latest, err := rm.sdkFind(context.Background(), r)

	require.NoError(err)
	require.NotNil(latest)
	require.NotNil(latest.ko.Spec.Policy)
	assert.Equal(policyDoc, *latest.ko.Spec.Policy)
}

// TestRequiredFieldsMissingFromReadOneInput validates the early NotFound
// bailout in sdkFind. GetDeliveryDestinationPolicy requires
// DeliveryDestinationName; when it is nil the input is incomplete.
func TestRequiredFieldsMissingFromReadOneInput(t *testing.T) {
	rm := &resourceManager{}

	testCases := []struct {
		name                    string
		deliveryDestinationName *string
		expectMissing           bool
	}{
		{
			name:          "name not set",
			expectMissing: true,
		},
		{
			name:                    "name set",
			deliveryDestinationName: aws.String("my-destination"),
			expectMissing:           false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			r := &resource{ko: &svcapitypes.DeliveryDestinationPolicy{}}
			r.ko.Spec.DeliveryDestinationName = tc.deliveryDestinationName

			assert.Equal(t, tc.expectMissing, rm.requiredFieldsMissingFromReadOneInput(r))
		})
	}
}
