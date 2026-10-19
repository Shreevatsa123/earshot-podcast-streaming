"""Shared base resources that several members' constructs use.

Owner: M6 · Stack: base · Tracker: M6-01 · Spec: CONTEXT §5, §8, §9.

Exposes (other constructs receive this object as ``core``):
- ``table``: the single DynamoDB table ``earshot-<stage>-main`` (§8)
- ``lake_bucket``: ``earshot-<stage>-lake-<account>`` (§9 lake layout)
- ``qoe_topic`` / ``ops_topic``: SNS topics for QoE alerts and ops alarms
- ``flags_param``: SSM ``/earshot/<stage>/flags``

Everything here costs about $0 while idle. In prod, the table and lake bucket are
RETAINed if the stack is deleted (§5).
"""

from __future__ import annotations

import json

from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from earshot_infra.common import data_removal_policy
from earshot_infra.config import StageConfig, names


class Core(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        removal = data_removal_policy(cfg)

        # Single-table design (CONTEXT §8): PK/SK strings, one GSI, TTL on "ttl".
        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=cfg.table_name,
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=removal,
        )
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(name="GSI1PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="GSI1SK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Event lake. M5 adds the athena-results/ lifecycle rule in lake.py.
        self.lake_bucket = s3.Bucket(
            self,
            "LakeBucket",
            bucket_name=cfg.lake_bucket,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=removal,
            auto_delete_objects=not cfg.retain_data,
        )

        self.qoe_topic = sns.Topic(
            self, "QoeTopic", topic_name=cfg.qoe_topic, display_name="Earshot QoE alerts"
        )
        self.ops_topic = sns.Topic(
            self, "OpsTopic", topic_name=cfg.ops_topic, display_name="Earshot ops alerts"
        )
        if cfg.alert_email:
            # AWS emails a confirmation link; alerts only arrive after you click it.
            for topic in (self.qoe_topic, self.ops_topic):
                topic.add_subscription(subscriptions.EmailSubscription(cfg.alert_email))

        # Initial flag values. scripts/set_flag.py changes them later; a normal deploy
        # doesn't reset them unless this resource's definition changes.
        self.flags_param = ssm.StringParameter(
            self,
            "FlagsParam",
            parameter_name=cfg.ssm_flags,
            string_value=json.dumps(names.DEFAULT_FLAGS, separators=(",", ":")),
            tier=ssm.ParameterTier.STANDARD,
            description="Earshot feature flags (CONTEXT §9)",
        )
