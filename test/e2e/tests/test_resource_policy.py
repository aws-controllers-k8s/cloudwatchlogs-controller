# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#      http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the CloudWatch Logs ResourcePolicy resource"""

import json
import pytest
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import resource_policy

RESOURCE_PLURAL = "resourcepolicies"

DELETE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10

UPDATED_POLICY_DOCUMENT = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "delivery.logs.amazonaws.com"},
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "*",
    }],
})


@pytest.fixture
def _resource_policy(request):
    policy_name = random_suffix_name("ack-test-rp", 30)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["POLICY_NAME"] = policy_name

    resource_data = load_resource(
        "resource_policy",
        additional_replacements=replacements,
    )

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        policy_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
    except Exception:
        pass
    resource_policy.wait_until_deleted(policy_name)


@service_marker
@pytest.mark.canary
class TestResourcePolicy:
    def test_crud(self, _resource_policy):
        (ref, cr) = _resource_policy
        policy_name = ref.name

        # Verify resource is synced
        condition.assert_synced(ref)

        # Verify policy exists in AWS
        aws_policy = resource_policy.get(policy_name)
        assert aws_policy is not None
        assert aws_policy["policyName"] == policy_name

        # Verify status fields are populated
        cr = k8s.get_resource(ref)
        assert "lastUpdatedTime" in cr["status"]
        assert cr["status"]["lastUpdatedTime"] > 0

        # Update: change the policy document
        updates = {
            "spec": {
                "policyDocument": UPDATED_POLICY_DOCUMENT,
            }
        }
        k8s.patch_custom_resource(ref, updates)
        k8s.wait_resource_consumed_by_controller(ref, wait_periods=5)

        condition.assert_synced(ref)

        # Verify updated document in AWS
        aws_policy = resource_policy.get(policy_name)
        assert aws_policy is not None
        aws_doc = json.loads(aws_policy["policyDocument"])
        expected_doc = json.loads(UPDATED_POLICY_DOCUMENT)
        assert aws_doc == expected_doc

        # Delete: handled by fixture teardown
