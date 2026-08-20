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
import time
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
CREATE_WAIT_AFTER_SECONDS = 10
# When adoption is expected to fail (no identifying fields), give the controller
# enough time to run several reconcile attempts before asserting it never
# adopted an arbitrary policy.
ADOPT_NO_FIELDS_WAIT_SECONDS = 60

# Set by the runtime on the CR once an annotation-based adoption succeeds. The
# annotation adoption path marks the resource adopted via this annotation
# rather than an ACK.Adopted condition (which is specific to the AdoptedResource
# CRD).
ADOPTED_ANNOTATION = "services.k8s.aws/adopted"

UPDATED_POLICY_DOCUMENT = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "delivery.logs.amazonaws.com"},
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "*",
    }],
})

ADOPT_POLICY_DOCUMENT = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "route53.amazonaws.com"},
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "*",
    }],
})


def _adoption_fields(fields: dict) -> str:
    """Renders a dict as the escaped JSON string expected inside the
    double-quoted services.k8s.aws/adoption-fields annotation value after
    $-substitution. An empty dict yields "{}", which adopts nothing.
    """
    parts = [f'\\"{k}\\": \\"{v}\\"' for k, v in fields.items()]
    return "{" + ", ".join(parts) + "}"


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
    resource_policy.wait_until_deleted_resource_scoped(log_group_arn)


@pytest.fixture
def adopt_account_policy():
    """Seeds an account-scoped policy out-of-band, then creates a CR annotated
    to adopt it by policyName. Yields (ref, cr, policy_name).
    """
    policy_name = random_suffix_name("ack-adopt-rp", 30)
    resource_policy.put_account_scoped(policy_name, ADOPT_POLICY_DOCUMENT)

    # Everything after the out-of-band put runs under try/finally so the seeded
    # policy is always cleaned up, even if CR setup below fails before yield.
    adoption_name = random_suffix_name("ack-adopt-rp-cr", 40)
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        adoption_name, namespace="default",
    )
    try:
        replacements = REPLACEMENT_VALUES.copy()
        replacements["ADOPTION_NAME"] = adoption_name
        replacements["ADOPTION_FIELDS"] = _adoption_fields({"policyName": policy_name})

        resource_data = load_resource(
            "resource_policy_adopt",
            additional_replacements=replacements,
        )

        k8s.create_custom_resource(ref, resource_data)
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        yield (ref, cr, policy_name)
    finally:
        try:
            k8s.delete_custom_resource(ref, 3, 10)
        except Exception:
            pass
        # deletion-policy retain leaves the AWS policy in place, so remove it here.
        resource_policy.delete_account_scoped(policy_name)
        resource_policy.wait_until_deleted(policy_name)


@pytest.fixture
def adopt_resource_scoped_policy(dependent_log_group):
    """Seeds a resource-scoped policy out-of-band against a dependent LogGroup,
    then creates a CR annotated to adopt it by resourceARN. Yields
    (ref, cr, log_group_arn).
    """
    log_group_arn = dependent_log_group

    document = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "Route53LogsToCloudWatchLogs",
            "Effect": "Allow",
            "Principal": {"Service": "route53.amazonaws.com"},
            "Action": "logs:PutLogEvents",
            "Resource": f"{log_group_arn}:*",
        }],
    })
    resource_policy.put_resource_scoped(log_group_arn, document)

    # Everything after the out-of-band put runs under try/finally so the seeded
    # policy is always cleaned up, even if CR setup below fails before yield.
    adoption_name = random_suffix_name("ack-adopt-rp-scoped-cr", 40)
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        adoption_name, namespace="default",
    )
    try:
        replacements = REPLACEMENT_VALUES.copy()
        replacements["ADOPTION_NAME"] = adoption_name
        replacements["ADOPTION_FIELDS"] = _adoption_fields({"resourceARN": log_group_arn})

        resource_data = load_resource(
            "resource_policy_adopt",
            additional_replacements=replacements,
        )

        k8s.create_custom_resource(ref, resource_data)
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        yield (ref, cr, log_group_arn)
    finally:
        try:
            k8s.delete_custom_resource(ref, 3, 10)
        except Exception:
            pass
        # deletion-policy retain leaves the AWS policy in place, so remove it here
        # before the dependent_log_group fixture tears down the LogGroup it targets.
        resource_policy.delete_resource_scoped(log_group_arn)
        resource_policy.wait_until_deleted_resource_scoped(log_group_arn)


@pytest.fixture
def adopt_no_fields():
    """Seeds an account-scoped policy out-of-band so an adoptable policy exists,
    then creates a CR annotated to adopt with empty adoption-fields. A correct
    controller must NOT adopt the arbitrary policy. Yields (ref, policy_name).
    """
    policy_name = random_suffix_name("ack-adopt-rp-nofields", 30)
    resource_policy.put_account_scoped(policy_name, ADOPT_POLICY_DOCUMENT)

    # Everything after the out-of-band put runs under try/finally so the seeded
    # policy is always cleaned up, even if CR setup below fails before yield.
    adoption_name = random_suffix_name("ack-adopt-rp-nofields-cr", 40)
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        adoption_name, namespace="default",
    )
    try:
        replacements = REPLACEMENT_VALUES.copy()
        replacements["ADOPTION_NAME"] = adoption_name
        replacements["ADOPTION_FIELDS"] = _adoption_fields({})

        resource_data = load_resource(
            "resource_policy_adopt",
            additional_replacements=replacements,
        )

        k8s.create_custom_resource(ref, resource_data)

        yield (ref, policy_name)
    finally:
        try:
            k8s.delete_custom_resource(ref, 3, 10)
        except Exception:
            pass
        resource_policy.delete_account_scoped(policy_name)
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
        # Let the controller pick up the new generation and reset conditions,
        # then wait for it to finish re-syncing before reading back from AWS.
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5,
        )

        # Verify updated document in AWS
        aws_policy = resource_policy.get(policy_name)
        assert aws_policy is not None
        aws_doc = json.loads(aws_policy["policyDocument"])
        expected_doc = json.loads(UPDATED_POLICY_DOCUMENT)
        assert aws_doc == expected_doc

        # Delete: handled by fixture teardown

    def test_crud_resource_scoped(self, _resource_scoped_policy):
        (ref, cr, log_group_arn) = _resource_scoped_policy

        # Verify resource is synced
        condition.assert_synced(ref)

        # Verify the resource-scoped policy exists in AWS. Resource-scoped
        # policies are keyed by their resource ARN, not a policy name.
        aws_policy = resource_policy.get_resource_scoped(log_group_arn)
        assert aws_policy is not None
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
        # Let the controller pick up the new generation and reset conditions,
        # then wait for it to finish re-syncing before reading back from AWS.
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5,
        )

        # Verify the updated document is persisted in AWS
        aws_policy = resource_policy.get_resource_scoped(log_group_arn)
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

    def test_adopt_by_policy_name(self, adopt_account_policy):
        (ref, cr, policy_name) = adopt_account_policy

        # The controller must adopt the pre-existing account-scoped policy.
        assert cr is not None
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=6,
        )

        # Annotation-based adoption marks the resource adopted by setting the
        # adopted annotation (not an ACK.Adopted condition, which is specific to
        # the AdoptedResource CRD).
        cr = k8s.get_resource(ref)
        annotations = cr["metadata"].get("annotations", {})
        assert annotations.get(ADOPTED_ANNOTATION) == "true"

        # The identifying field supplied via adoption-fields must be reflected
        # back into the resource's Spec.
        assert cr["spec"]["policyName"] == policy_name
        assert cr["status"].get("policyScope") == "ACCOUNT"

        # And the adopted policy is the one that exists in AWS.
        aws_policy = resource_policy.get(policy_name)
        assert aws_policy is not None
        assert aws_policy["policyName"] == policy_name

        # Delete: handled by fixture teardown

    def test_adopt_by_resource_arn(self, adopt_resource_scoped_policy):
        (ref, cr, log_group_arn) = adopt_resource_scoped_policy

        # The controller must adopt the pre-existing resource-scoped policy.
        assert cr is not None
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=6,
        )

        # Annotation-based adoption marks the resource adopted by setting the
        # adopted annotation (not an ACK.Adopted condition, which is specific to
        # the AdoptedResource CRD).
        cr = k8s.get_resource(ref)
        annotations = cr["metadata"].get("annotations", {})
        assert annotations.get(ADOPTED_ANNOTATION) == "true"

        # The resource ARN supplied via adoption-fields must be reflected back
        # into the Spec, and the resource-scoped status fields populated.
        assert cr["spec"]["resourceARN"] == log_group_arn
        assert cr["status"].get("policyScope") == "RESOURCE"
        assert cr["status"].get("revisionID")

        # And the adopted policy is the resource-scoped one that exists in AWS.
        aws_policy = resource_policy.get_resource_scoped(log_group_arn)
        assert aws_policy is not None
        assert aws_policy["resourceArn"] == log_group_arn

        # Delete: handled by fixture teardown

    def test_adopt_no_fields_does_not_adopt(self, adopt_no_fields):
        (ref, existing_policy_name) = adopt_no_fields

        # Give the controller several reconcile attempts. With no identifying
        # fields, requiredFieldsMissingFromReadManyInput returns true so sdkFind
        # yields NotFound; the resource must never be adopted. (Before the fix
        # an arbitrary account-scoped policy would be adopted here.)
        time.sleep(ADOPT_NO_FIELDS_WAIT_SECONDS)

        # The resource must not become synced or adopted.
        synced = k8s.get_resource_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED,
        )
        assert synced is None or str(synced.get("status")) != "True"

        adopted = k8s.get_resource_condition(
            ref, condition.CONDITION_TYPE_ADOPTED,
        )
        assert adopted is None or str(adopted.get("status")) != "True"

        # No arbitrary policy identifier should have been populated into Spec,
        # and no AWS ARN should have been recorded.
        cr = k8s.get_resource(ref)
        spec = cr.get("spec", {}) or {}
        assert spec.get("policyName") is None
        assert spec.get("resourceARN") is None
        status = cr.get("status", {}) or {}
        assert "ackResourceMetadata" not in status or \
            status.get("ackResourceMetadata", {}).get("arn") is None

        # The pre-existing account policy must remain in AWS, untouched by the
        # failed adoption attempt.
        assert resource_policy.get(existing_policy_name) is not None
