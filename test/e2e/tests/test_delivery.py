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
import contextlib
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
UPDATE_WAIT_AFTER_SECONDS = 10

# Tags reconcile out of band and can lag Synced=True, so poll instead of
# asserting once after a fixed sleep.
TAGS_CONVERGE_TIMEOUT_SECONDS = 120
TAGS_CONVERGE_INTERVAL_SECONDS = 5


def wait_for_user_tags(delivery_arn, expected_user_tags):
    """Polls until the user (non-ACK) tags equal expected_user_tags, then
    returns the full live tag dict. Fails on timeout."""
    deadline = time.time() + TAGS_CONVERGE_TIMEOUT_SECONDS
    latest_tags = None
    while True:
        latest_tags = delivery.get_tags(delivery_arn)
        if latest_tags is not None:
            # clean() strips the ACK system tags, leaving only user tags.
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
    """Creates a DeliverySource and DeliveryDestination via boto3 (not ACK
    CRs) so the test exercises only the Delivery resource. Yields
    (delivery_source_name, delivery_destination_arn)."""
    cwl = boto3.client("logs")
    bootstrap = get_bootstrap_resources()

    # Dedicated NLB so this source does not collide with the DeliverySource
    # test on the same resourceArn under parallel execution.
    nlb_arn = bootstrap.DeliveryNLB.arn
    ds_name = random_suffix_name("ack-dlvr-ds", 30)

    lg_arn = bootstrap.DeliveryDestinationLogGroup.arn
    dd_name = random_suffix_name("ack-dlvr-dd", 30)

    cwl.put_delivery_source(
        name=ds_name,
        logType="NLB_ACCESS_LOGS",
        resourceArn=nlb_arn,
    )

    dd_resp = cwl.put_delivery_destination(
        name=dd_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": lg_arn,
        },
        outputFormat="json",
    )
    dd_arn = dd_resp["deliveryDestination"]["arn"]

    yield (ds_name, dd_arn)

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

    # resource_data marker may override the template and add replacements.
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

    # Capture the delivery ID before the test body, so teardown can wait for
    # AWS deletion even if the CR is already gone.
    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.get_resource(ref)
    delivery_id = (cr.get("status") or {}).get("id")

    yield (ref, cr)

    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except Exception:
        pass

    if delivery_id:
        delivery.wait_until_deleted(delivery_id)


@pytest.fixture(scope="module")
def _delivery_s3_prerequisites():
    """Creates a DeliverySource and two S3 DeliveryDestinations via boto3 so
    the S3 update paths can be exercised. An S3 destination is required
    because suffixPath and fieldDelimiter are only mutable there. The two
    destinations (json and plain outputFormat) share one bucket and one source
    (source->delivery is one-to-many); the plain destination is needed because
    fieldDelimiter is only valid on a delimited format. Yields
    (delivery_source_name, dd_json_arn, dd_plain_arn)."""
    cwl = boto3.client("logs")
    bootstrap = get_bootstrap_resources()

    # Dedicated NLB so this source does not collide with the CWL-destination
    # test on the same resourceArn under parallel execution.
    nlb_arn = bootstrap.DeliveryS3NLB.arn
    ds_name = random_suffix_name("ack-dlvr-s3-ds", 30)

    # The Bucket helper exposes only .name, so build the ARN.
    bucket_name = bootstrap.DeliveryS3Bucket.name
    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    dd_json_name = random_suffix_name("ack-dlvr-s3-dd", 30)
    dd_plain_name = random_suffix_name("ack-dlvr-s3-dd-plain", 30)

    cwl.put_delivery_source(
        name=ds_name,
        logType="NLB_ACCESS_LOGS",
        resourceArn=nlb_arn,
    )

    # json destination: used by the suffixPath update.
    dd_json_resp = cwl.put_delivery_destination(
        name=dd_json_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": bucket_arn,
        },
        outputFormat="json",
    )
    dd_json_arn = dd_json_resp["deliveryDestination"]["arn"]

    # plain (delimited) destination: used by the fieldDelimiter update.
    dd_plain_resp = cwl.put_delivery_destination(
        name=dd_plain_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": bucket_arn,
        },
        outputFormat="plain",
    )
    dd_plain_arn = dd_plain_resp["deliveryDestination"]["arn"]

    yield (ds_name, dd_json_arn, dd_plain_arn)

    try:
        cwl.delete_delivery_destination(name=dd_json_name)
    except Exception:
        pass
    try:
        cwl.delete_delivery_destination(name=dd_plain_name)
    except Exception:
        pass
    try:
        cwl.delete_delivery_source(name=ds_name)
    except Exception:
        pass


@contextlib.contextmanager
def _delivery_cr(ds_name, dd_arn, resource_file, extra_replacements=None):
    """Creates a Delivery CR against the given destination, yields (ref, cr),
    and on exit (including a mid-phase failure) deletes the CR and waits for
    the delivery to disappear from AWS. Lets one sequential test drive several
    short-lived CRs in series against the single bootstrapped source."""
    delivery_name = random_suffix_name("ack-test-s3dlvr", 30)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_NAME"] = delivery_name
    replacements["DELIVERY_SOURCE_NAME"] = ds_name
    replacements["DELIVERY_DESTINATION_ARN"] = dd_arn
    if extra_replacements:
        replacements.update(extra_replacements)

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

    # Capture the delivery ID before the test body, so teardown can wait for
    # AWS deletion even if the CR is already gone.
    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.get_resource(ref)
    delivery_id = (cr.get("status") or {}).get("id")

    try:
        yield (ref, cr)
    finally:
        # finally, so a mid-phase failure still tears the CR down before the
        # next phase creates another one.
        try:
            _, deleted = k8s.delete_custom_resource(ref, 3, 10)
            assert deleted
        except Exception:
            pass

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

        # --- Create (tags inline) ---
        condition.assert_synced(ref)

        cr = k8s.get_resource(ref)
        assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
        delivery_arn = cr["status"]["ackResourceMetadata"]["arn"]

        assert cr["status"].get("id") is not None
        delivery_id = cr["status"]["id"]

        assert cr["status"].get("deliveryDestinationType") is not None

        aws_delivery = delivery.get(delivery_id)
        assert aws_delivery is not None
        assert aws_delivery["id"] == delivery_id

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

        # --- Update tags: change one value (TagResource), remove one key
        # (UntagResource) ---
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

        # --- Delete: handled by fixture teardown ---

    # All three S3 update paths share one delivery source, whose resourceArn
    # backs only one source at a time. Keeping them in ONE test item pins the
    # sequence to a single xdist worker so no two workers race to create the
    # source. xdist_group is not used: CI runs --dist load, under which it is
    # a no-op (effective only with --dist loadgroup).
    def test_s3_delivery_lifecycle(self, _delivery_s3_prerequisites):
        ds_name, dd_json_arn, dd_plain_arn = _delivery_s3_prerequisites

        # --- Phase 1: suffixPath update ---
        with _delivery_cr(
            ds_name, dd_json_arn, "delivery_s3",
            {"SUFFIX_PATH": "ack-e2e-initial/"},
        ) as (ref, cr):
            condition.assert_synced(ref)

            cr = k8s.get_resource(ref)
            assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
            assert cr["status"].get("id") is not None
            delivery_id = cr["status"]["id"]

            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery is not None
            assert aws_delivery["id"] == delivery_id
            assert (aws_delivery.get("s3DeliveryConfiguration") or {}).get(
                "suffixPath"
            ) == "ack-e2e-initial/"

            # --- Update suffixPath. Full replace so the controller sees the
            # changed nested scalar in desired. ---
            new_suffix = "ack-e2e-updated/"
            cr = k8s.get_resource(ref)
            cr["spec"]["s3DeliveryConfiguration"]["suffixPath"] = new_suffix
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)

            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery is not None
            assert (aws_delivery.get("s3DeliveryConfiguration") or {}).get(
                "suffixPath"
            ) == new_suffix

            # No persistent delta: re-read after a settle window.
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)
            aws_delivery = delivery.get(delivery_id)
            assert (aws_delivery.get("s3DeliveryConfiguration") or {}).get(
                "suffixPath"
            ) == new_suffix

        # --- Phase 2: fieldDelimiter update (plain-format destination) ---
        # fieldDelimiter is only valid on a delimited format, and only an
        # allowlisted value (tab, space, comma).
        with _delivery_cr(
            ds_name, dd_plain_arn, "delivery_s3_plain",
            {"FIELD_DELIMITER": " "},
        ) as (ref, cr):
            condition.assert_synced(ref)

            cr = k8s.get_resource(ref)
            assert cr["status"].get("ackResourceMetadata", {}).get("arn") is not None
            assert cr["status"].get("id") is not None
            delivery_id = cr["status"]["id"]

            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery is not None
            assert aws_delivery["id"] == delivery_id
            assert aws_delivery.get("fieldDelimiter") == " "

            # --- Update fieldDelimiter (space -> comma): a real
            # UpdateDeliveryConfiguration. Full replace so desired changes. ---
            cr = k8s.get_resource(ref)
            cr["spec"]["fieldDelimiter"] = ","
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)

            # No terminal error. A healthy Delivery emits no ACK.Terminal
            # condition, so treat ABSENT as success (assert_type_status fails
            # on an absent condition, so it cannot be used here).
            term = k8s.get_resource_condition(ref, condition.CONDITION_TYPE_TERMINAL)
            assert term is None or str(term.get("status")) != "True"

            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery is not None
            assert aws_delivery.get("fieldDelimiter") == ","

            # No persistent delta: re-read after a settle window.
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)
            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery.get("fieldDelimiter") == ","

        # --- Phase 3: recordFields reorder is a no-op ---
        with _delivery_cr(
            ds_name, dd_json_arn, "delivery_s3",
            {"SUFFIX_PATH": "ack-e2e-reorder/"},
        ) as (ref, cr):
            # AWS populates all mandatory recordFields; sdkFind reads them back.
            condition.assert_synced(ref)

            cr = k8s.get_resource(ref)
            assert cr["status"].get("id") is not None
            delivery_id = cr["status"]["id"]

            aws_delivery = delivery.get(delivery_id)
            assert aws_delivery is not None
            live_fields = aws_delivery.get("recordFields")
            assert live_fields is not None and len(live_fields) > 0

            # Full-replace recordFields with the REVERSED order. SliceStringPEqual
            # (delta.go) sorts before comparing, so a reorder yields no delta and
            # no UpdateDeliveryConfiguration.
            reversed_fields = list(reversed(live_fields))
            assert reversed_fields != live_fields  # sanity: order differs
            cr = k8s.get_resource(ref)
            cr["spec"]["recordFields"] = reversed_fields
            k8s.replace_custom_resource(ref, cr)
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)
            term = k8s.get_resource_condition(ref, condition.CONDITION_TYPE_TERMINAL)
            assert term is None or str(term.get("status")) != "True"

            # Discriminating check: read the DESIRED spec, not live GetDelivery.
            # With no delta the controller never overwrote desired, so the
            # reversed order persists. An order-sensitive comparator would churn
            # and never settle on it; GetDelivery's canonical order cannot tell
            # the two apart, the CR spec can.
            cr = k8s.get_resource(ref)
            assert cr["spec"].get("recordFields") == reversed_fields

            # No churn across a second settle window.
            time.sleep(UPDATE_WAIT_AFTER_SECONDS)
            condition.assert_synced(ref)
            cr = k8s.get_resource(ref)
            assert cr["spec"].get("recordFields") == reversed_fields
