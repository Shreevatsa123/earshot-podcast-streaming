"""Throwaway stack ``earshot-<stage>-servicecheck`` (owner: M6 · tracker M6-03).

Creates one tiny resource for each approved service (CONTEXT §3) that the base stack
doesn't already create, to prove the account (Free plan) allows them before anyone relies
on them. ``AWS_PROFILE=earshot-prod make service-check STAGE=prod`` deploys it, prints the
account limits, and destroys it right away: 15-30 minutes (CloudFront is the slow part)
and a few cents.

Covered here: S3, CloudFront, Cognito, API Gateway (HTTP API), Lambda, Step Functions,
EC2 (t3.micro in the default VPC), and the event path that replaces Kinesis: an SNS topic
delivering to an SQS queue (raw message delivery) that triggers a Lambda.
Covered by ``make deploy-base``: DynamoDB, S3, SNS, SSM, Glue, Athena, CloudWatch, IAM.

Not used at all: Kinesis Data Streams and Amazon Data Firehose. Free plan accounts can't
use them (every call returns SubscriptionRequiredException, "needs a subscription for the
service"). The first run of this check found it on Nov 7, 2026, and a read-only CLI check
on Nov 8 confirmed both.

If the deploy fails, the CloudFormation error names the resource that failed: that's the
blocked service. Two known cases on new accounts: CloudFront can require AWS Support to
verify the account first, and EC2 can be blocked by a low vCPU quota.

Everything here is deleted with the stack. The app only adds this stack with
``-c servicecheck=true``, so a normal synth or deploy never touches it.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import CfnTag, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

from earshot_infra.common import log_group, tag_owner, tag_stack
from earshot_infra.config import StageConfig

HELLO_HANDLER = """
def main(event, context):
    return {"statusCode": 200, "body": "earshot service check ok"}
"""


class ServiceCheckStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        tag_stack(self, cfg)
        tag_owner(self, "M6")
        prefix = f"{cfg.prefix}-check"

        bucket = s3.Bucket(
            self,
            "Bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        cloudfront.Distribution(
            self,
            "Cdn",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket)
            ),
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            comment=f"{prefix}: service check",
        )

        function_name = f"{prefix}-fn"
        function = lambda_.Function(
            self,
            "Function",
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="index.main",
            code=lambda_.Code.from_inline(HELLO_HANDLER),
            timeout=Duration.seconds(5),
            log_group=log_group(self, "FunctionLogs", name=f"/aws/lambda/{function_name}"),
        )

        apigwv2.HttpApi(
            self,
            "Api",
            api_name=f"{prefix}-api",
            default_integration=integrations.HttpLambdaIntegration("Hello", function),
        )

        cognito.UserPool(
            self, "UserPool", user_pool_name=f"{prefix}-users", removal_policy=RemovalPolicy.DESTROY
        )

        sfn.StateMachine(
            self,
            "StateMachine",
            state_machine_name=f"{prefix}-sfn",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition_body=sfn.DefinitionBody.from_chainable(sfn.Pass(self, "Noop")),
        )

        # The event path that replaces Kinesis: SNS topic -> SQS queue -> Lambda trigger.
        # SQS-managed encryption, because SNS can't deliver to a queue encrypted with the
        # AWS-managed KMS key.
        topic = sns.Topic(self, "Topic", topic_name=f"{prefix}-topic")
        queue = sqs.Queue(
            self,
            "Queue",
            queue_name=f"{prefix}-queue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
        )
        topic.add_subscription(subscriptions.SqsSubscription(queue, raw_message_delivery=True))
        # Nothing is published, so the function is never invoked. Lambda polls the empty
        # queue only while this stack exists (a few hundred free requests).
        function.add_event_source(event_sources.SqsEventSource(queue, batch_size=10))

        # Without a VPC id or subnet, both land in the default VPC (no lookup needed at synth).
        security_group = ec2.CfnSecurityGroup(
            self, "InstanceSecurityGroup", group_description=f"{prefix}: no inbound rules"
        )
        ec2.CfnInstance(
            self,
            "Instance",
            instance_type="t3.micro",
            image_id=ec2.MachineImage.latest_amazon_linux2023().get_image(self).image_id,
            security_group_ids=[security_group.attr_group_id],
            tags=[CfnTag(key="Name", value=f"{prefix}-instance")],
        )
