"""EC2 instance that runs the listener simulator and the load tests.

Owner: M3 · Stack: **pipeline** (hourly-billed) · Tracker: M3-07 · Spec: CONTEXT §5, §11

Creates:
- One t3.micro, Amazon Linux 2023, in a **default-VPC public subnet**, with a security
  group that has **no inbound rules**. Access it through SSM Session Manager (no SSH key,
  no Elastic IP).
- Instance role: ``AmazonSSMManagedInstanceCore``, plus ``ssm:GetParameter*`` on
  ``cfg.ssm_stage_parameters_arn``, read access to the simulator code assets, and
  ``sns:Publish`` on ``cfg.events_topic_arn`` (``replay --direct`` publishes there).
- User data that installs Python 3.11 + boto3 + locust and unpacks the code into
  ``/opt/earshot`` with the same layout as the repo (``simulator/``,
  ``services/shared/``, ``contracts/samples/catalog.json``), so the CLI runs the same way
  as locally::

      sudo -iu ec2-user
      cd /opt/earshot && python3.11 -m simulator run --stage <stage> --users 2000 --rate 500 --duration 600

Gotcha: don't use ``ec2.Vpc.from_lookup``. Lookups need AWS credentials at synth time,
which breaks synth for teammates and CI. An instance and security group created without
a subnet/VPC id land in the default VPC (``ec2.CfnInstance`` / ``ec2.CfnSecurityGroup``),
and the AMI comes from the public SSM parameter for AL2023 (same as M6's service check).

Exposes: nothing.
"""

from __future__ import annotations

from aws_cdk import CfnTag, Fn
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct

from earshot_infra.config import REPO_ROOT, SERVICES_DIR, StageConfig

INSTANCE_TYPE = "t3.micro"
APP_DIR = "/opt/earshot"
ASSET_EXCLUDES = ["**/__pycache__/**", "**/*.pyc", "runs/**", "*.jsonl"]


class Simulator(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)

        # Code assets, uploaded by CDK to the bootstrap bucket.
        simulator_code = s3_assets.Asset(
            self, "SimulatorCode", path=str(REPO_ROOT / "simulator"), exclude=ASSET_EXCLUDES
        )
        shared_code = s3_assets.Asset(
            self, "SharedCode", path=str(SERVICES_DIR / "shared"), exclude=ASSET_EXCLUDES
        )
        catalog = s3_assets.Asset(
            self, "Catalog", path=str(REPO_ROOT / "contracts" / "samples" / "catalog.json")
        )

        role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")],
            description=f"{cfg.prefix} simulator instance",
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
                resources=[cfg.ssm_stage_parameters_arn],
            )
        )
        role.add_to_policy(iam.PolicyStatement(actions=["sns:Publish"], resources=[cfg.events_topic_arn]))
        for asset in (simulator_code, shared_code, catalog):
            asset.grant_read(role)
        profile = iam.CfnInstanceProfile(self, "InstanceProfile", roles=[role.role_name])

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "set -euxo pipefail",
            "dnf install -y python3.11 python3.11-pip unzip",
            "python3.11 -m pip install --quiet boto3 locust",
            f"mkdir -p {APP_DIR}/simulator {APP_DIR}/services/shared {APP_DIR}/contracts/samples",
        )
        sim_zip = user_data.add_s3_download_command(
            bucket=simulator_code.bucket, bucket_key=simulator_code.s3_object_key
        )
        shared_zip = user_data.add_s3_download_command(
            bucket=shared_code.bucket, bucket_key=shared_code.s3_object_key
        )
        catalog_file = user_data.add_s3_download_command(bucket=catalog.bucket, bucket_key=catalog.s3_object_key)
        user_data.add_commands(
            f"unzip -o {sim_zip} -d {APP_DIR}/simulator",
            f"unzip -o {shared_zip} -d {APP_DIR}/services/shared",
            f"cp {catalog_file} {APP_DIR}/contracts/samples/catalog.json",
            f"chown -R ec2-user:ec2-user {APP_DIR}",
            f"echo 'export EARSHOT_STAGE={cfg.stage} AWS_DEFAULT_REGION={cfg.region}' >> /home/ec2-user/.bashrc",
            "echo 'earshot simulator ready'",
        )

        security_group = ec2.CfnSecurityGroup(
            self, "SecurityGroup", group_description=f"{cfg.prefix} simulator: no inbound rules"
        )
        instance = ec2.CfnInstance(
            self,
            "Instance",
            instance_type=INSTANCE_TYPE,
            image_id=ec2.MachineImage.latest_amazon_linux2023().get_image(self).image_id,
            iam_instance_profile=profile.ref,
            security_group_ids=[security_group.attr_group_id],
            user_data=Fn.base64(user_data.render()),
            tags=[CfnTag(key="Name", value=f"{cfg.prefix}-simulator")],
        )
        # User data runs on first boot only. The pipeline stack is recreated for every
        # session, so a fresh `make pipeline-up` always gets the current code.
        instance.add_dependency(profile)
