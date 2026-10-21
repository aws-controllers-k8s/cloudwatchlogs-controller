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

    resource_file = "delivery_source"

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
    def test_crud(self, _delivery_source):
        (ref, cr) = _delivery_source
        ds_name = ref.name

        # Verify resource is synced
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        condition.assert_synced(ref)

        # Verify delivery source exists in AWS
        aws_ds = delivery_source.get(ds_name)
        assert aws_ds is not None
        assert aws_ds["name"] == ds_name
        assert aws_ds["logType"] == "NLB_ACCESS_LOGS"

        # Verify status fields are populated
        cr = k8s.get_resource(ref)
        assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
        assert cr["status"].get("service") is not None

        # Delete: handled by fixture teardown

    def test_tags(self, _delivery_source):
        (ref, cr) = _delivery_source
        ds_name = ref.name

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        condition.assert_synced(ref)

        cr = k8s.get_resource(ref)
        ds_arn = cr["status"]["ackResourceMetadata"]["arn"]

        # (a) Create carries no user tags yet; patch two user tags onto the
        # spec and assert both the user tags and the ACK default controller
        # tags (services.k8s.aws/*) land on the delivery source. Tags are
        # reconciled out of band by rm.syncTags, so poll until the user tags
        # converge before asserting (removes the fixed-sleep timing flake).
        user_tags = {
            "environment": "dev",
            "team": "observability",
        }
        updates = {"spec": {"tags": user_tags}}
        k8s.patch_custom_resource(ref, updates)
        condition.assert_synced(ref)

        latest_tags = wait_for_user_tags(ds_arn, user_tags)
        tags.assert_ack_system_tags(
            tags=latest_tags,
        )
        tags.assert_equal_without_ack_tags(
            expected=user_tags,
            actual=latest_tags,
        )

        # (b) Change one value and remove one key, then assert the standalone
        # TagResource/UntagResource reconciliation (rm.syncTags) applied both.
        #
        # A merge patch leaves map keys that are omitted from the patch body
        # untouched, so patching spec.tags with only {environment: prod} would
        # NOT remove the "team" key from the CR -- the controller would never
        # see a desired without "team" and UntagResource would never fire.
        # Fully replace the resource so spec.tags is exactly the new map and
        # the removed key genuinely disappears from desired.
        updated_tags = {
            "environment": "prod",
        }
        cr = k8s.get_resource(ref)
        cr["spec"]["tags"] = updated_tags
        k8s.replace_custom_resource(ref, cr)
        condition.assert_synced(ref)

        latest_tags = wait_for_user_tags(ds_arn, updated_tags)
        tags.assert_ack_system_tags(
            tags=latest_tags,
        )
        tags.assert_equal_without_ack_tags(
            expected=updated_tags,
            actual=latest_tags,
        )
        assert "team" not in latest_tags
        assert latest_tags.get("environment") == "prod"

    @pytest.mark.resource_data({
        "resource_file": "delivery_source_with_tags",
        "replacements": {
            "TAG_KEY_1": "environment",
            "TAG_VALUE_1": "dev",
            "TAG_KEY_2": "team",
            "TAG_VALUE_2": "observability",
        },
    })
    def test_create_with_tags(self, _delivery_source):
        (ref, cr) = _delivery_source
        ds_name = ref.name

        # PutDeliverySource accepts tags ONLY at create, so sdkCreate passes
        # spec.tags inline on the create call and then requeues (its
        # `if ko.Spec.Tags != nil { SetSynced(False) }` branch) to reconcile
        # the ACK system tags. Creating with tags set exercises that inline
        # path and the requeue, which the patch-after-create test_tags does
        # not cover.
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        condition.assert_synced(ref)

        cr = k8s.get_resource(ref)
        ds_arn = cr["status"]["ackResourceMetadata"]["arn"]

        expected_tags = {
            "environment": "dev",
            "team": "observability",
        }

        # Tags set at create are reconciled (the inline create tags plus the
        # ACK system tags via the requeue) out of band, so poll until the user
        # tags converge before asserting rather than reading once.
        latest_tags = wait_for_user_tags(ds_arn, expected_tags)
        # Both the user tags supplied at create AND the ACK default controller
        # tags (services.k8s.aws/*) must be present on the delivery source.
        tags.assert_ack_system_tags(
            tags=latest_tags,
        )
        tags.assert_equal_without_ack_tags(
            expected=expected_tags,
            actual=latest_tags,
        )
