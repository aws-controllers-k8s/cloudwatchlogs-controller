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
"""Bootstraps the resources required to run the CloudWatch Logs integration tests.
"""
import logging

from acktest.bootstrapping import Resources, BootstrapFailureException
from acktest.bootstrapping.cloudwatch import LogGroup
from acktest.bootstrapping.elbv2 import NetworkLoadBalancer
from acktest.bootstrapping.s3 import Bucket

from e2e import bootstrap_directory
from e2e.bootstrap_resources import BootstrapResources

# Bucket policy granting the CloudWatch Logs delivery service permission to
# write log objects into the S3 destination bucket. The Bucket helper
# substitutes $NAME (bucket name), $ACCOUNT_ID and $REGION before calling
# PutBucketPolicy, so these tokens MUST stay literal here.
DELIVERY_S3_BUCKET_POLICY = """{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSLogDeliveryWrite",
      "Effect": "Allow",
      "Principal": { "Service": "delivery.logs.amazonaws.com" },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::$NAME/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control",
          "aws:SourceAccount": "$ACCOUNT_ID"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:logs:$REGION:$ACCOUNT_ID:delivery-source:*"
        }
      }
    }
  ]
}"""

def service_bootstrap() -> Resources:
    logging.getLogger().setLevel(logging.INFO)

    resources = BootstrapResources(
        DeliverySourceNLB=NetworkLoadBalancer(
            name_prefix="ack-cwl-ds",
            scheme="internal",
            num_public_subnet=0,
            num_private_subnet=2,
        ),
        # Separate NLB for the Delivery test prerequisites (boto3-managed
        # delivery source). An NLB ResourceId can only back one delivery source
        # at a time, so the DeliverySource ACK-CR test and the Delivery test
        # must each have their own NLB to avoid ConflictException when running
        # in parallel.
        DeliveryNLB=NetworkLoadBalancer(
            name_prefix="ack-cwl-dlvr",
            scheme="internal",
            num_public_subnet=0,
            num_private_subnet=2,
        ),
        DeliveryDestinationLogGroup=LogGroup(
            name_prefix="ack-cwl-dd",
        ),
        DeliveryDestinationLogGroup2=LogGroup(
            name_prefix="ack-cwl-dd2",
        ),
        # Dedicated NLB for the S3-destination Delivery update-path test. A
        # separate NLB (not DeliveryNLB) is required because an NLB ResourceId
        # can only back one delivery source at a time; reusing DeliveryNLB would
        # collide with the CWL-destination test under parallel execution.
        DeliveryS3NLB=NetworkLoadBalancer(
            name_prefix="ack-cwl-s3dlvr",
            scheme="internal",
            num_public_subnet=0,
            num_private_subnet=2,
        ),
        # S3 bucket used as the delivery destination for the update-path test
        # (suffixPath is mutable only on an S3-destination delivery).
        DeliveryS3Bucket=Bucket(
            name_prefix="ack-cwl-dlvr-s3",
            policy=DELIVERY_S3_BUCKET_POLICY,
        ),
    )

    try:
        resources.bootstrap()
    except BootstrapFailureException as ex:
        exit(254)

    return resources

if __name__ == "__main__":
    config = service_bootstrap()
    # Write config to current directory by default
    config.serialize(bootstrap_directory)
