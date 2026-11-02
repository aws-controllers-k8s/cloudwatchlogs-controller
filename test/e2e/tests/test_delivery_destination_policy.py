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

"""Integration tests for the CloudWatch Logs DeliveryDestinationPolicy resource"""

import json
import time

import boto3
import pytest
from acktest.aws.identity import get_account_id, get_region
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import delivery_destination
from e2e import delivery_destination_policy
from e2e.bootstrap_resources import get_bootstrap_resources

RESOURCE_PLURAL = "deliverydestinationpolicies"
DELIVERY_DESTINATION_RESOURCE_PLURAL = "deliverydestinations"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10
# wait_on_condition polls every 15s per period.
SYNC_WAIT_PERIODS = 8


def _policy_document(
    account_id: str,
    destination_arn: str,
    actions,
    sid: str = "AllowLogDeliveryActions",
) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": sid,
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
            "Action": actions,
            "Resource": destination_arn,
        }],
    }


def _delivery_destination_arn(name: str) -> str:
    return (
        f"arn:aws:logs:{get_region()}:{get_account_id()}:"
        f"delivery-destination:{name}"
    )


def _log_group_arn() -> str:
    arn = get_bootstrap_resources().DeliveryDestinationLogGroup.arn
    if arn.endswith(":*"):
        arn = arn[:-len(":*")]
    return arn


def _assert_aws_policy(dd_name: str, expected: dict):
    aws_policy = delivery_destination_policy.get(dd_name)
    assert aws_policy is not None
    assert json.loads(aws_policy) == expected


@pytest.fixture(scope="module")
def _delivery_destination_prerequisite():
    """Creates a DeliveryDestination directly via boto3 (not an ACK CR) so the
    name-based test exercises only the DeliveryDestinationPolicy resource.
    Yields (delivery_destination_name, delivery_destination_arn)."""
    cwl = boto3.client("logs")
    dd_name = random_suffix_name("ack-ddp-dd", 30)
    resp = cwl.put_delivery_destination(
        name=dd_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": _log_group_arn(),
        },
        outputFormat="json",
    )
    dd_arn = resp["deliveryDestination"]["arn"]

    yield (dd_name, dd_arn)

    try:
        cwl.delete_delivery_destination(name=dd_name)
    except Exception:
        pass


@pytest.fixture
def _delivery_destination_policy(_delivery_destination_prerequisite):
    dd_name, dd_arn = _delivery_destination_prerequisite
    policy_cr_name = random_suffix_name("ack-test-ddp", 30)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_DESTINATION_POLICY_NAME"] = policy_cr_name
    replacements["DELIVERY_DESTINATION_NAME"] = dd_name
    replacements["DELIVERY_DESTINATION_ARN"] = dd_arn
    replacements["AWS_ACCOUNT_ID"] = str(get_account_id())

    resource_data = load_resource(
        "delivery_destination_policy",
        additional_replacements=replacements,
    )

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        policy_cr_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, dd_name, dd_arn)

    if k8s.get_resource_exists(ref):
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    delivery_destination_policy.wait_until_deleted(dd_name)


@pytest.fixture
def _delivery_destination_policy_with_ref():
    """Creates the DeliveryDestinationPolicy CR (referencing its parent via
    deliveryDestinationRef) BEFORE the parent DeliveryDestination CR, so the
    policy must wait on reference resolution and recover without going
    terminal."""
    dd_name = random_suffix_name("ack-ddp-ref-dd", 30)
    policy_cr_name = random_suffix_name("ack-test-ddp-ref", 30)
    account_id = str(get_account_id())

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_DESTINATION_POLICY_NAME"] = policy_cr_name
    replacements["DELIVERY_DESTINATION_CR_NAME"] = dd_name
    replacements["DELIVERY_DESTINATION_NAME"] = dd_name
    replacements["DELIVERY_DESTINATION_ARN"] = _delivery_destination_arn(dd_name)
    replacements["DESTINATION_RESOURCE_ARN"] = _log_group_arn()
    replacements["OUTPUT_FORMAT"] = "json"
    replacements["AWS_ACCOUNT_ID"] = account_id

    policy_ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        policy_cr_name, namespace="default",
    )
    k8s.create_custom_resource(
        policy_ref,
        load_resource("delivery_destination_policy_ref", additional_replacements=replacements),
    )
    k8s.wait_resource_consumed_by_controller(policy_ref)

    # Parent is created only after the policy, to exercise the reference wait.
    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    dd_ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, DELIVERY_DESTINATION_RESOURCE_PLURAL,
        dd_name, namespace="default",
    )
    k8s.create_custom_resource(
        dd_ref,
        load_resource("delivery_destination_plain", additional_replacements=replacements),
    )
    k8s.wait_resource_consumed_by_controller(dd_ref)

    yield (policy_ref, dd_ref, dd_name, account_id)

    if k8s.get_resource_exists(policy_ref):
        _, deleted = k8s.delete_custom_resource(policy_ref, 3, 10)
        assert deleted
    delivery_destination_policy.wait_until_deleted(dd_name)

    if k8s.get_resource_exists(dd_ref):
        _, deleted = k8s.delete_custom_resource(dd_ref, 3, 10)
        assert deleted
    delivery_destination.wait_until_deleted(dd_name)


@service_marker
@pytest.mark.canary
class TestDeliveryDestinationPolicy:
    def test_crud(self, _delivery_destination_policy):
        (ref, cr, dd_name, dd_arn) = _delivery_destination_policy
        account_id = str(get_account_id())

        # The ARN built for the reference test must match the real format.
        assert _delivery_destination_arn(dd_name) == dd_arn

        # --- Create --------------------------------------------------------
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True",
            wait_periods=SYNC_WAIT_PERIODS,
        )

        cr = k8s.get_resource(ref)
        assert cr["spec"]["deliveryDestinationName"] == dd_name
        created_doc = _policy_document(account_id, dd_arn, "logs:CreateDelivery")
        assert json.loads(cr["spec"]["policy"]) == created_doc
        _assert_aws_policy(dd_name, created_doc)

        # --- Update policy document ----------------------------------------
        # Delivery destination policies only accept logs:CreateDelivery as an
        # action (anything else is rejected with a terminal ValidationException),
        # so exercise the update path by changing the statement Sid instead.
        updated_doc = _policy_document(
            account_id, dd_arn, "logs:CreateDelivery",
            sid="AllowCrossAccountCreateDelivery",
        )
        k8s.patch_custom_resource(ref, {"spec": {"policy": json.dumps(updated_doc)}})
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(
            ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True",
            wait_periods=SYNC_WAIT_PERIODS,
        )
        _assert_aws_policy(dd_name, updated_doc)

        # The policy comparison is semantic (is_iam_policy), so AWS
        # re-serialising the document must not leave a lingering diff.
        assert k8s.get_resource_condition(ref, condition.CONDITION_TYPE_TERMINAL) is None

        # --- Delete --------------------------------------------------------
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)
        delivery_destination_policy.wait_until_deleted(dd_name)
        assert delivery_destination_policy.get(dd_name) is None

        # The parent destination must survive policy deletion.
        assert delivery_destination.get(dd_name) is not None

    def test_crud_with_reference(self, _delivery_destination_policy_with_ref):
        (policy_ref, dd_ref, dd_name, account_id) = _delivery_destination_policy_with_ref

        # --- Create (parent created after the policy) ----------------------
        assert k8s.wait_on_condition(
            dd_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True",
            wait_periods=SYNC_WAIT_PERIODS,
        )
        assert k8s.wait_on_condition(
            policy_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True",
            wait_periods=SYNC_WAIT_PERIODS,
        )
        # Waiting on the reference / parent must not have been terminal.
        assert k8s.get_resource_condition(
            policy_ref, condition.CONDITION_TYPE_TERMINAL,
        ) is None

        dd_cr = k8s.get_resource(dd_ref)
        dd_arn = dd_cr["status"]["ackResourceMetadata"]["arn"]

        _assert_aws_policy(
            dd_name, _policy_document(account_id, dd_arn, "logs:CreateDelivery"),
        )

        # --- Delete --------------------------------------------------------
        # Handled by fixture teardown: the policy is deleted first and
        # verified gone in AWS, then the parent destination.
