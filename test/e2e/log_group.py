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

"""Utilities for working with Log Group resources"""

import datetime
import time
import logging

import boto3
import pytest

DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60*20
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 15


def wait_until_deleted(
        log_group_name: str,
        timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
        interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
    ) -> None:
    """Waits until a Log Group with a supplied ID is no longer returned from
    the CloudWatch Logs API.

    Usage:
        from e2e.log_group import wait_until_deleted

        wait_until_deleted(instance_id)

    Raises:
        pytest.fail upon timeout or if the Log Group goes to any other status
        other than 'deleting'
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for Log Group to be "
                "deleted in CloudWatch Logs API"
            )
        time.sleep(interval_seconds)

        latest = get(log_group_name)
        if latest is None:
            break


def exists_with_retention_period(log_group_name: str, retention: int):
    """Returns True if the supplied Log Group record exists and its retention
    period matches the 'retention' argument, False otherwise.
    """
    log_group = get(log_group_name)
    if log_group is not None:
        if log_group['retentionInDays'] == retention:
            return True
    return False


def get(log_group_name: str):
    """Returns a dict containing the Log Group record from the CloudWatch Logs
    API.

    If no such Log Group exists, returns None.
    """
    c = boto3.client('logs')
    resp = c.describe_log_groups(logGroupNamePrefix=log_group_name)
    if len(resp['logGroups']) == 1:
        return resp['logGroups'][0]
    return None

def get_subscription_filters(log_group_name: str):
    """Returns a dict containing Subscription groups attached to a LogGroup

    If no such Log Group exists, returns None.
    """
    c = boto3.client('logs')
    try:
        resp = c.describe_subscription_filters(logGroupName=log_group_name)
        logging.info(resp)
        return resp['subscriptionFilters']
    except Exception as e:
        logging.info(e)
        return None

def get_tags(log_group_arn):
    """Returns a dict containing the Log Group's tag records from the
    CloudWatch Logs API.

    If no such Log Group exists, returns None.
    """
    c = boto3.client('logs')
    try:
        resp = c.list_tags_for_resource(
            ResourceName=log_group_arn,
        )
        return resp['TagList']
    except c.exceptions.LogGroupNotFoundFault:
        return None
