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

"""Utilities for working with DeliverySource resources"""

import datetime
import time

import boto3
import pytest

DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 10
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 10


def get(name: str):
    """Returns the CloudWatch Logs delivery source with the given name, or None."""
    cwl = boto3.client("logs")
    try:
        resp = cwl.get_delivery_source(name=name)
        return resp.get("deliverySource")
    except cwl.exceptions.ResourceNotFoundException:
        return None
    except Exception:
        return None


def wait_until_deleted(
    name: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until a DeliverySource with the given name is no longer returned
    from the CloudWatch Logs API.

    Raises:
        pytest.fail upon timeout
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for DeliverySource to be "
                "deleted in CloudWatch Logs API"
            )
        time.sleep(interval_seconds)

        latest = get(name)
        if latest is None:
            break
