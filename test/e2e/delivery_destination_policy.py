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

"""Utilities for working with DeliveryDestinationPolicy resources"""

import datetime
import time

import boto3
import pytest

DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 5
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 10


def get(delivery_destination_name: str):
    """Returns the policy document (string) attached to the named delivery
    destination, or None if there is no policy (or no destination).

    Both a ResourceNotFoundException and a successful response with an empty
    policy are treated as "no policy" so the helper is robust to either
    behaviour of GetDeliveryDestinationPolicy.
    """
    cwl = boto3.client("logs")
    try:
        resp = cwl.get_delivery_destination_policy(
            deliveryDestinationName=delivery_destination_name,
        )
    except cwl.exceptions.ResourceNotFoundException:
        return None
    return (resp.get("policy") or {}).get("deliveryDestinationPolicy") or None


def wait_until_deleted(
    delivery_destination_name: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until the named delivery destination no longer has a policy in
    the CloudWatch Logs API.

    Raises:
        pytest.fail upon timeout
    """
    timeout = datetime.datetime.now() + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if get(delivery_destination_name) is None:
            return
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for DeliveryDestinationPolicy to be "
                "deleted in CloudWatch Logs API"
            )
        time.sleep(interval_seconds)
