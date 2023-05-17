# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the CloudWatch Logs API LogGroup resource
"""

import time

import pytest

from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import condition
from e2e import log_group

RESOURCE_PLURAL = 'loggroups'

DELETE_WAIT_AFTER_SECONDS = 5

@pytest.fixture
def _log_group():
    log_group_name = random_suffix_name("ack-test-log-group", 20)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["LOG_GROUP_NAME"] = log_group_name
    resource_data = load_resource(
        "log_group",
        additional_replacements=replacements,
    )

    # Create the k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        log_group_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Try to delete, if doesn't already exist
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
    except:
        pass
    log_group.wait_until_deleted(log_group_name)


@service_marker
@pytest.mark.canary
class TestLogGroup:
    def test_crud(self, _log_group):
        (ref, cr) = _log_group
        log_group_name = ref.name

        condition.assert_synced(ref)

        assert log_group.exists(log_group_name)
