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

"""Declares the structure of the bootstrapped resources and provides a loader
for them.
"""

from dataclasses import dataclass, field
from acktest.bootstrapping import Resources
from acktest.bootstrapping.cloudwatch import LogGroup
from acktest.bootstrapping.elbv2 import NetworkLoadBalancer
from acktest.bootstrapping.s3 import Bucket
from e2e import bootstrap_directory

@dataclass
class BootstrapResources(Resources):
    DeliverySourceNLB: NetworkLoadBalancer = field(default=None)
    # A second NLB exclusively for the Delivery test's boto3 prerequisites so
    # the DeliverySource ACK-CR test and the Delivery test never fight over the
    # same NLB ResourceId when running in parallel (pytest-xdist).
    DeliveryNLB: NetworkLoadBalancer = field(default=None)
    DeliveryDestinationLogGroup: LogGroup = field(default=None)
    DeliveryDestinationLogGroup2: LogGroup = field(default=None)
    # Dedicated NLB + S3 bucket for the S3-destination Delivery update-path
    # test (suffixPath is only mutable on an S3-destination delivery).
    DeliveryS3NLB: NetworkLoadBalancer = field(default=None)
    DeliveryS3Bucket: Bucket = field(default=None)

_bootstrap_resources = None

def get_bootstrap_resources(bootstrap_file_name: str = "bootstrap.pkl") -> BootstrapResources:
    global _bootstrap_resources
    if _bootstrap_resources is None:
        _bootstrap_resources = BootstrapResources.deserialize(bootstrap_directory, bootstrap_file_name=bootstrap_file_name)
    return _bootstrap_resources
