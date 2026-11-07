"""Throwaway stack ``earshot-<stage>-servicecheck`` (owner: M6 · tracker M6-03).

Creates one tiny resource for each approved service (CONTEXT §3) that the base stack
doesn't already create, to prove the account (Free plan) allows them before anyone relies
on them. ``AWS_PROFILE=earshot-prod make service-check STAGE=prod`` deploys it, prints the
account limits, and destroys it right away: 15-30 minutes (CloudFront is the slow part)
and a few cents.

Covered here: S3, CloudFront, Cognito, API Gateway (HTTP API), Lambda, Step Functions,
SQS, Kinesis, Firehose, EC2 (t3.micro in the default VPC).
Covered by ``make deploy-base``: DynamoDB, S3, SNS, SSM, Glue, Athena, CloudWatch, IAM.

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
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kinesis as kinesis
from aws_cdk import aws_kinesisfirehose as firehose
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
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

        sqs.Queue(self, "Queue", queue_name=f"{prefix}-queue", removal_policy=RemovalPolicy.DESTROY)

        stream = kinesis.Stream(
            self,
            "Stream",
            stream_name=f"{prefix}-stream",
            stream_mode=kinesis.StreamMode.PROVISIONED,
            shard_count=1,
            retention_period=Duration.hours(24),
            encryption=kinesis.StreamEncryption.MANAGED,
        )
        # Set explicitly: a stream left behind bills every hour.
        stream.apply_removal_policy(RemovalPolicy.DESTROY)

        firehose_role = iam.Role(
            self, "FirehoseRole", assumed_by=iam.ServicePrincipal("firehose.amazonaws.com")
        )
        bucket.grant_write(firehose_role)
        delivery = firehose.CfnDeliveryStream(
            self,
            "Firehose",
            delivery_stream_name=f"{prefix}-firehose",
            delivery_stream_type="DirectPut",
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=bucket.bucket_arn,
                role_arn=firehose_role.role_arn,
            ),
        )
        # Firehose checks its permissions on create, so the role's policy must exist first.
        delivery.node.add_dependency(firehose_role)

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
