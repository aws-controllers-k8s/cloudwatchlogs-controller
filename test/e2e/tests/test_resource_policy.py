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
from e2e import log_group

RESOURCE_PLURAL = "resourcepolicies"
LOG_GROUP_RESOURCE_PLURAL = "loggroups"

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


@pytest.fixture
def dependent_log_group():
    """Creates a LogGroup to serve as the target resource for a resource-scoped
    ResourcePolicy and yields its ARN, tearing the LogGroup down afterward.
    """
    log_group_name = random_suffix_name("ack-test-rp-lg", 20)
    replacements = REPLACEMENT_VALUES.copy()
    replacements["LOG_GROUP_NAME"] = log_group_name
    resource_data = load_resource(
        "log_group",
        additional_replacements=replacements,
    )
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, LOG_GROUP_RESOURCE_PLURAL,
        log_group_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)
    assert cr is not None
    condition.assert_synced(ref)

    cr = k8s.get_resource(ref)
    log_group_arn = cr["status"]["ackResourceMetadata"]["arn"]

    yield log_group_arn

    try:
        _, _ = k8s.delete_custom_resource(ref, 3, 10)
    except Exception:
        pass
    log_group.wait_until_deleted(log_group_name)


@pytest.fixture
def _resource_scoped_policy(dependent_log_group):
    # Create a ResourcePolicy scoped to the dependent LogGroup's ARN. Because
    # this fixture depends on dependent_log_group, pytest tears the policy down
    # before the LogGroup it references.
    log_group_arn = dependent_log_group

    policy_name = random_suffix_name("ack-test-rp-scoped", 30)
    replacements = REPLACEMENT_VALUES.copy()
    replacements["POLICY_NAME"] = policy_name
    replacements["RESOURCE_ARN"] = log_group_arn

    resource_data = load_resource(
        "resource_policy_resource_scoped",
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

    yield (ref, cr, log_group_arn)

    try:
        _, _ = k8s.delete_custom_resource(ref, 3, 10)
    except Exception:
        pass
    resource_policy.wait_until_deleted_resource_scoped(log_group_arn, policy_name)


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

    def test_crud_resource_scoped(self, _resource_scoped_policy):
        (ref, cr, log_group_arn) = _resource_scoped_policy
        policy_name = ref.name

        # Verify resource is synced
        condition.assert_synced(ref)

        # Verify the resource-scoped policy exists in AWS
        aws_policy = resource_policy.get_resource_scoped(log_group_arn, policy_name)
        assert aws_policy is not None
        assert aws_policy["policyName"] == policy_name
        assert aws_policy["policyScope"] == "RESOURCE"
        assert aws_policy["resourceArn"] == log_group_arn

        # Verify status fields are populated, including the revision ID that
        # drives concurrent-modification protection on update.
        cr = k8s.get_resource(ref)
        assert cr["status"]["policyScope"] == "RESOURCE"
        assert cr["status"].get("revisionID")
        original_revision_id = cr["status"]["revisionID"]

        # Update: change the policy document. For resource-scoped policies this
        # exercises the ExpectedRevisionId injection in sdkUpdate.
        updated_policy_document = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "Route53LogsToCloudWatchLogs",
                "Effect": "Allow",
                "Principal": {"Service": "route53.amazonaws.com"},
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"{log_group_arn}:*",
            }],
        })
        updates = {
            "spec": {
                "policyDocument": updated_policy_document,
            }
        }
        k8s.patch_custom_resource(ref, updates)
        k8s.wait_resource_consumed_by_controller(ref, wait_periods=5)

        condition.assert_synced(ref)

        # Verify the updated document is persisted in AWS
        aws_policy = resource_policy.get_resource_scoped(log_group_arn, policy_name)
        assert aws_policy is not None
        aws_doc = json.loads(aws_policy["policyDocument"])
        expected_doc = json.loads(updated_policy_document)
        assert aws_doc == expected_doc

        # The revision ID should advance, proving the revision-guarded update
        # succeeded rather than being rejected as a concurrent modification.
        cr = k8s.get_resource(ref)
        assert cr["status"].get("revisionID")
        assert cr["status"]["revisionID"] != original_revision_id

        # Delete: handled by fixture teardown
