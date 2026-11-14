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

// mockHTTPClient answers every request with the same body. sdkFind calls
// DescribeLogGroups first; DescribeSubscriptionFilters and
// ListTagsForResource, which follow only when a log group was found, decode
// the same body to empty results.
type mockHTTPClient struct {
	body string
}

func (m *mockHTTPClient) Do(req *http.Request) (*http.Response, error) {
	return &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"application/x-amz-json-1.1"}},
		Body:       io.NopCloser(bytes.NewBufferString(m.body)),
	}, nil
}

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

func logGroupNamed(name string) *resource {
	return &resource{
		ko: &svcapitypes.LogGroup{
			Spec: svcapitypes.LogGroupSpec{
				Name: aws.String(name),
			},
		},
	}
}

// TestSdkFind_OnlyLongerNamedLogGroup_ReturnsNotFound verifies that a log
// group whose name only starts with the CR's name is not taken for the CR's
// log group. DescribeLogGroups filters by name prefix, so for a CR named
// "/app" it also returns "/app-worker".
func TestSdkFind_OnlyLongerNamedLogGroup_ReturnsNotFound(t *testing.T) {
	rm := newTestResourceManager(&mockHTTPClient{
		body: `{"logGroups":[{
			"logGroupName":"/app-worker",
			"arn":"arn:aws:logs:us-east-1:111122223333:log-group:/app-worker:*",
			"logGroupArn":"arn:aws:logs:us-east-1:111122223333:log-group:/app-worker"
		}]}`,
	})

	latest, err := rm.sdkFind(context.Background(), logGroupNamed("/app"))

	assert.Nil(t, latest)
	assert.Equal(t, ackerr.NotFound, err)
}

// TestSdkFind_PicksLogGroupWithSameName verifies that sdkFind reads the log
// group with the CR's name, not the first one in the response.
func TestSdkFind_PicksLogGroupWithSameName(t *testing.T) {
	rm := newTestResourceManager(&mockHTTPClient{
		body: `{"logGroups":[{
			"logGroupName":"/app-worker",
			"arn":"arn:aws:logs:us-east-1:111122223333:log-group:/app-worker:*",
			"logGroupArn":"arn:aws:logs:us-east-1:111122223333:log-group:/app-worker"
		},{
			"logGroupName":"/app",
			"arn":"arn:aws:logs:us-east-1:111122223333:log-group:/app:*",
			"logGroupArn":"arn:aws:logs:us-east-1:111122223333:log-group:/app"
		}]}`,
	})

	latest, err := rm.sdkFind(context.Background(), logGroupNamed("/app"))

	require.NoError(t, err)
	require.NotNil(t, latest)
	assert.Equal(t, "/app", *latest.ko.Spec.Name)
	require.NotNil(t, latest.ko.Status.ACKResourceMetadata)
	assert.Equal(t,
		"arn:aws:logs:us-east-1:111122223333:log-group:/app",
		string(*latest.ko.Status.ACKResourceMetadata.ARN),
	)
}
