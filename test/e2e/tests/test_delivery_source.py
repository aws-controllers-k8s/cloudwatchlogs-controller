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

"""Integration tests for the CloudWatch Logs DeliverySource resource"""

import time
import pytest
from acktest import tags
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import delivery_source
from e2e.bootstrap_resources import get_bootstrap_resources

RESOURCE_PLURAL = "deliverysources"

DELETE_WAIT_AFTER_SECONDS = 10
CREATE_WAIT_AFTER_SECONDS = 10
MODIFY_WAIT_AFTER_SECONDS = 10

# Tag reconciliation happens out of band via rm.syncTags (standalone
# TagResource/UntagResource calls) and can lag a short while behind the
# Synced=True condition. Poll the live tags until the user (non-ACK) tags
# converge to the expected set rather than asserting once after a fixed sleep.
TAGS_CONVERGE_TIMEOUT_SECONDS = 120
TAGS_CONVERGE_INTERVAL_SECONDS = 5


def wait_for_user_tags(ds_arn, expected_user_tags):
    """Polls the delivery source's live tags until the non-ACK (user) tags
    equal expected_user_tags, then returns the full live tag dict (including
    ACK system tags). Fails via pytest on timeout.
    """
    deadline = time.time() + TAGS_CONVERGE_TIMEOUT_SECONDS
    latest_tags = None
    while True:
        latest_tags = delivery_source.get_tags(ds_arn)
        if latest_tags is not None:
            # clean() strips every services.k8s.aws/* tag by prefix, leaving
            # only the user tags to compare against the expected set.
            if tags.clean(tags=latest_tags) == dict(expected_user_tags):
                return latest_tags
        if time.time() >= deadline:
            pytest.fail(
                f"Timed out after {TAGS_CONVERGE_TIMEOUT_SECONDS}s waiting for "
                f"delivery source tags to converge. expected user tags="
                f"{expected_user_tags}, latest={latest_tags}"
            )
        time.sleep(TAGS_CONVERGE_INTERVAL_SECONDS)


@pytest.fixture
def _delivery_source(request):
    bootstrap = get_bootstrap_resources()
    nlb_arn = bootstrap.DeliverySourceNLB.arn

    ds_name = random_suffix_name("ack-test-ds", 30)

    resource_file = "delivery_source_with_tags"

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_SOURCE_NAME"] = ds_name
    replacements["LOG_TYPE"] = "NLB_ACCESS_LOGS"
    replacements["RESOURCE_ARN"] = nlb_arn

    # A test may select an alternate resource template (e.g. one that sets
    # spec.tags at create time) and supply extra replacement keys for it via
    # the resource_data marker.
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
        ds_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    _, deleted = k8s.delete_custom_resource(ref, 3, 10)
    assert deleted
    delivery_source.wait_until_deleted(ds_name)


@service_marker
@pytest.mark.canary
class TestDeliverySource:
    # One consolidated lifecycle test exercises the whole resource against a
    # single NLB. A delivery source's resourceArn (the NLB) can back only one
    # delivery source at a time -- PutDeliverySource rejects a second source on
    # the same ResourceId with ConflictException. The suite runs tests in
    # parallel (pytest -n), so separate test methods each creating a source on
    # the one bootstrapped NLB collided across workers and flaked with
    # Synced=Unknown. Driving create -> tag update/remove -> delete in a single
    # sequential test keeps exactly one source on the NLB at any moment while
    # still covering every path.
    @pytest.mark.resource_data({
        "resource_file": "delivery_source_with_tags",
        "replacements": {
            "TAG_KEY_1": "environment",
            "TAG_VALUE_1": "dev",
            "TAG_KEY_2": "team",
            "TAG_VALUE_2": "observability",
        },
    })
    def test_crud_and_tags(self, _delivery_source):
        (ref, cr) = _delivery_source
        ds_name = ref.name

        # --- Create (with tags inline) -------------------------------------
        # PutDeliverySource accepts tags only at create and persists them, so
        # the create payload carries spec.tags inline. Verify the resource
        # syncs, exists in AWS with the expected identity, and has its status
        # populated.
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        condition.assert_synced(ref)

        aws_ds = delivery_source.get(ds_name)
        assert aws_ds is not None
        assert aws_ds["name"] == ds_name
        assert aws_ds["logType"] == "NLB_ACCESS_LOGS"

        cr = k8s.get_resource(ref)
        assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
        assert cr["status"].get("service") is not None
        ds_arn = cr["status"]["ackResourceMetadata"]["arn"]

        # The user tags supplied at create AND the ACK default controller tags
        # (services.k8s.aws/*) must both be present. Tags are reconciled out of
        # band via rm.syncTags, so poll until the user tags converge rather than
        # reading once after a fixed sleep.
        create_tags = {
            "environment": "dev",
            "team": "observability",
        }
        latest_tags = wait_for_user_tags(ds_arn, create_tags)
        tags.assert_ack_system_tags(tags=latest_tags)
        tags.assert_equal_without_ack_tags(
            expected=create_tags,
            actual=latest_tags,
        )

        # --- Update tags (change one value, remove one key) ----------------
        # A merge patch leaves omitted map keys untouched, so to actually drop
        # the "team" key the resource is fully replaced with spec.tags set to
        # exactly the new map. This exercises both the standalone TagResource
        # (value change) and UntagResource (key removal) paths of rm.syncTags.
        updated_tags = {
            "environment": "prod",
        }
        cr = k8s.get_resource(ref)
        cr["spec"]["tags"] = updated_tags
        k8s.replace_custom_resource(ref, cr)
        condition.assert_synced(ref)

        latest_tags = wait_for_user_tags(ds_arn, updated_tags)
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
