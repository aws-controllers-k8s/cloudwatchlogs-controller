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

"""Utilities for working with ResourcePolicy resources"""

import datetime
import time
import logging

import boto3
import pytest

DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS = 60 * 10
DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS = 10


def put_account_scoped(policy_name: str, policy_document: str):
    """Creates an account-scoped resource policy directly via the CloudWatch
    Logs API, bypassing the controller. Used to seed a pre-existing policy for
    adoption tests.
    """
    cwl = boto3.client("logs")
    cwl.put_resource_policy(
        policyName=policy_name,
        policyDocument=policy_document,
    )


def put_resource_scoped(resource_arn: str, policy_document: str):
    """Creates a resource-scoped resource policy directly via the CloudWatch
    Logs API, bypassing the controller. Resource-scoped policies are keyed by
    their resource ARN; the API infers the RESOURCE scope from its presence.
    """
    cwl = boto3.client("logs")
    cwl.put_resource_policy(
        policyDocument=policy_document,
        resourceArn=resource_arn,
    )


def delete_account_scoped(policy_name: str):
    """Best-effort deletion of an account-scoped resource policy via the
    CloudWatch Logs API. Safe to call during teardown even if the policy is
    already gone.
    """
    cwl = boto3.client("logs")
    try:
        cwl.delete_resource_policy(policyName=policy_name)
    except Exception:
        pass


def delete_resource_scoped(resource_arn: str):
    """Best-effort deletion of a resource-scoped resource policy via the
    CloudWatch Logs API. Safe to call during teardown even if the policy is
    already gone.

    Resource-scoped policies carry a revision ID and DeleteResourcePolicy
    requires a matching expectedRevisionId, so look the current one up first.
    """
    policy = get_resource_scoped(resource_arn)
    if policy is None:
        return
    cwl = boto3.client("logs")
    try:
        cwl.delete_resource_policy(
            resourceArn=resource_arn,
            expectedRevisionId=policy["revisionId"],
        )
    except Exception:
        pass


def get(policy_name: str):
    """Returns the CloudWatch Logs resource policy with the given name, or None."""
    cwl = boto3.client("logs")
    try:
        paginator = cwl.get_paginator("describe_resource_policies")
        for page in paginator.paginate():
            for policy in page.get("resourcePolicies", []):
                if policy.get("policyName") == policy_name:
                    return policy
    except Exception:
        return None
    return None


def get_resource_scoped(resource_arn: str):
    """Returns the resource-scoped CloudWatch Logs resource policy attached to
    the supplied resource ARN, or None.

    Resource-scoped policies are keyed by their resource ARN (one per resource)
    rather than a policy name. DescribeResourcePolicies defaults to ACCOUNT
    scope, so they are only returned when the RESOURCE scope and the resource
    ARN are supplied explicitly.
    """
    cwl = boto3.client("logs")
    try:
        resp = cwl.describe_resource_policies(
            resourceArn=resource_arn,
            policyScope="RESOURCE",
        )
        for policy in resp.get("resourcePolicies", []):
            if policy.get("resourceArn") == resource_arn:
                return policy
    except Exception:
        return None
    return None


def wait_until_deleted(
    policy_name: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until a ResourcePolicy with the given name is no longer returned
    from the CloudWatch Logs API.

    Raises:
        pytest.fail upon timeout
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for ResourcePolicy to be "
                "deleted in CloudWatch Logs API"
            )
        time.sleep(interval_seconds)

        latest = get(policy_name)
        if latest is None:
            break


def wait_until_deleted_resource_scoped(
    resource_arn: str,
    timeout_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_TIMEOUT_SECONDS,
    interval_seconds: int = DEFAULT_WAIT_UNTIL_DELETED_INTERVAL_SECONDS,
) -> None:
    """Waits until the resource-scoped ResourcePolicy attached to the supplied
    resource ARN is no longer returned from the CloudWatch Logs API.

    Raises:
        pytest.fail upon timeout
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while True:
        if datetime.datetime.now() >= timeout:
            pytest.fail(
                "Timed out waiting for resource-scoped ResourcePolicy to be "
                "deleted in CloudWatch Logs API"
            )
        time.sleep(interval_seconds)

        latest = get_resource_scoped(resource_arn)
        if latest is None:
            break
