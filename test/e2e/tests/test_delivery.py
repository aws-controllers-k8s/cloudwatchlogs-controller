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

"""Integration tests for the CloudWatch Logs Delivery resource"""

import time
import pytest
import boto3
from acktest import tags
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import delivery
from e2e.bootstrap_resources import get_bootstrap_resources

RESOURCE_PLURAL = "deliveries"

DELETE_WAIT_AFTER_SECONDS = 10
CREATE_WAIT_AFTER_SECONDS = 10

# Tag reconciliation happens out of band via rm.syncTags (standalone
# TagResource/UntagResource calls) and can lag a short while behind the
# Synced=True condition. Poll the live tags until the user (non-ACK) tags
# converge to the expected set rather than asserting once after a fixed sleep.
TAGS_CONVERGE_TIMEOUT_SECONDS = 120
TAGS_CONVERGE_INTERVAL_SECONDS = 5


def wait_for_user_tags(delivery_arn, expected_user_tags):
    """Polls the delivery's live tags until the non-ACK (user) tags
    equal expected_user_tags, then returns the full live tag dict (including
    ACK system tags). Fails via pytest on timeout.
    """
    deadline = time.time() + TAGS_CONVERGE_TIMEOUT_SECONDS
    latest_tags = None
    while True:
        latest_tags = delivery.get_tags(delivery_arn)
        if latest_tags is not None:
            # clean() strips every services.k8s.aws/* tag by prefix, leaving
            # only the user tags to compare against the expected set.
            if tags.clean(tags=latest_tags) == dict(expected_user_tags):
                return latest_tags
        if time.time() >= deadline:
            pytest.fail(
                f"Timed out after {TAGS_CONVERGE_TIMEOUT_SECONDS}s waiting for "
                f"delivery tags to converge. expected user tags="
                f"{expected_user_tags}, latest={latest_tags}"
            )
        time.sleep(TAGS_CONVERGE_INTERVAL_SECONDS)


@pytest.fixture(scope="module")
def _delivery_prerequisites():
    """Creates the prerequisite DeliverySource and DeliveryDestination
    AWS resources needed to create a Delivery. These are created directly
    via boto3 (not ACK CRs) to isolate the test to the Delivery resource.

    Yields a tuple of (delivery_source_name, delivery_destination_arn).

    Tears down the prerequisites after the test module completes.
    """
    cwl = boto3.client("logs")
    bootstrap = get_bootstrap_resources()

    # Use the dedicated Delivery NLB (separate from DeliverySourceNLB which is
    # used by test_delivery_source.py) so the two tests can run in parallel
    # without conflicting on the same NLB ResourceId.
    nlb_arn = bootstrap.DeliveryNLB.arn
    ds_name = random_suffix_name("ack-dlvr-ds", 30)

    # Use a bootstrapped log group as the delivery destination
    lg_arn = bootstrap.DeliveryDestinationLogGroup.arn
    dd_name = random_suffix_name("ack-dlvr-dd", 30)

    # Create the delivery source
    cwl.put_delivery_source(
        name=ds_name,
        logType="NLB_ACCESS_LOGS",
        resourceArn=nlb_arn,
    )

    # Create the delivery destination
    dd_resp = cwl.put_delivery_destination(
        name=dd_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": lg_arn,
        },
        outputFormat="json",
    )
    dd_arn = dd_resp["deliveryDestination"]["arn"]

    yield (ds_name, dd_arn)

    # Cleanup: delete the delivery destination and source
    try:
        cwl.delete_delivery_destination(name=dd_name)
    except Exception:
        pass
    try:
        cwl.delete_delivery_source(name=ds_name)
    except Exception:
        pass


@pytest.fixture
def _delivery(request, _delivery_prerequisites):
    ds_name, dd_arn = _delivery_prerequisites

    delivery_name = random_suffix_name("ack-test-dlvr", 30)

    resource_file = "delivery_with_tags"

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_NAME"] = delivery_name
    replacements["DELIVERY_SOURCE_NAME"] = ds_name
    replacements["DELIVERY_DESTINATION_ARN"] = dd_arn

    # A test may select an alternate resource template and supply extra
    # replacement keys via the resource_data marker.
    marker = request.node.get_closest_marker("resource_data")
    if marker is not None:
        data = marker.args[0]
        if "resource_file" in data:
            resource_file = data["resource_file"]
        if "replacements" in data:
            replacements.update(data["replacements"])

    resource_data = load_resource(
        resource_file,
        additional_replacements=replacements,
    )

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        delivery_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    # Capture the delivery ID early (before the test body runs) so the
    # teardown can wait for AWS deletion even if the CR is already gone
    # by the time we reach cleanup.
    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.get_resource(ref)
    delivery_id = (cr.get("status") or {}).get("id")

    yield (ref, cr)

    # Cleanup: delete the K8s resource; the controller will call DeleteDelivery.
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except Exception:
        pass

    # Wait for the delivery to disappear from the AWS API.
    if delivery_id:
        delivery.wait_until_deleted(delivery_id)


@service_marker
@pytest.mark.canary
class TestDelivery:
    @pytest.mark.resource_data({
        "resource_file": "delivery_with_tags",
        "replacements": {
            "TAG_KEY_1": "environment",
            "TAG_VALUE_1": "dev",
            "TAG_KEY_2": "team",
            "TAG_VALUE_2": "observability",
        },
    })
    def test_crud_and_tags(self, _delivery):
        (ref, cr) = _delivery

        # --- Create (with tags inline) -------------------------------------
        # CreateDelivery accepts tags inline. Verify the resource syncs,
        # exists in AWS with the expected identity, and has its status
        # populated (including the AWS-assigned Id).
        condition.assert_synced(ref)

        cr = k8s.get_resource(ref)
        assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
        delivery_arn = cr["status"]["ackResourceMetadata"]["arn"]

        assert cr["status"].get("id") is not None
        delivery_id = cr["status"]["id"]

        assert cr["status"].get("deliveryDestinationType") is not None

        # Verify the delivery exists in AWS
        aws_delivery = delivery.get(delivery_id)
        assert aws_delivery is not None
        assert aws_delivery["id"] == delivery_id

        # Verify tags at create: user tags + ACK system tags must be present.
        create_tags = {
            "environment": "dev",
            "team": "observability",
        }
        latest_tags = wait_for_user_tags(delivery_arn, create_tags)
        tags.assert_ack_system_tags(tags=latest_tags)
        tags.assert_equal_without_ack_tags(
            expected=create_tags,
            actual=latest_tags,
        )

        # --- Update tags (change one value, remove one key) ----------------
        # This exercises TagResource (value change) and UntagResource (key
        # removal) via rm.syncTags.
        updated_tags = {
            "environment": "prod",
        }
        cr = k8s.get_resource(ref)
        cr["spec"]["tags"] = updated_tags
        k8s.replace_custom_resource(ref, cr)
        condition.assert_synced(ref)

        latest_tags = wait_for_user_tags(delivery_arn, updated_tags)
        tags.assert_ack_system_tags(tags=latest_tags)
        tags.assert_equal_without_ack_tags(
            expected=updated_tags,
            actual=latest_tags,
        )
        assert "team" not in latest_tags
        assert latest_tags.get("environment") == "prod"

        # --- Delete --------------------------------------------------------
        # Handled by the fixture teardown, which asserts the resource is gone
        # from both the cluster and the CloudWatch Logs API.
