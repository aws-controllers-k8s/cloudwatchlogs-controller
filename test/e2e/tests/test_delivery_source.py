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
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import delivery_source
from e2e.bootstrap_resources import get_bootstrap_resources

RESOURCE_PLURAL = "deliverysources"

DELETE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
CREATE_WAIT_AFTER_SECONDS = 10


@pytest.fixture
def _delivery_source():
    bootstrap = get_bootstrap_resources()
    nlb_arn = bootstrap.DeliverySourceNLB.arn

    ds_name = random_suffix_name("ack-test-ds", 30)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["DELIVERY_SOURCE_NAME"] = ds_name
    replacements["LOG_TYPE"] = "NLB_ACCESS_LOGS"
    replacements["RESOURCE_ARN"] = nlb_arn

    resource_data = load_resource(
        "delivery_source",
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

    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
    except Exception:
        pass
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
