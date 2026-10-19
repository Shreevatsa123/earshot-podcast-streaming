"""EC2 instance that runs the listener simulator and the load tests.

Owner: M3 · Stack: **pipeline** (hourly-billed) · Tracker: M3-07 · Spec: CONTEXT §5, §11

STATUS: STUB. Creates nothing yet.

Must create:
- One t3.micro, Amazon Linux 2023, in a **default-VPC public subnet**, with a security
  group that has **no inbound rules**. Access it through SSM Session Manager (no SSH key,
  no Elastic IP).
- Instance role: ``AmazonSSMManagedInstanceCore``, plus ``ssm:GetParameter*`` on
  ``cfg.ssm_stage_parameters_arn`` and read access to the simulator code asset.
- User data that installs the Python dependencies and unpacks ``simulator/``
  (from an ``s3_assets.Asset``).

Gotcha: don't use ``ec2.Vpc.from_lookup``. Lookups need AWS credentials at synth time,
which breaks synth for teammates and CI. An instance and security group created without
a subnet/VPC id land in the default VPC (``ec2.CfnInstance`` / ``ec2.CfnSecurityGroup``),
and the AMI can come from the public SSM parameter for AL2023.

Exposes: nothing.
"""

from __future__ import annotations

from constructs import Construct

from earshot_infra.config import StageConfig


class Simulator(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        # TODO(M3-07): implement per the docstring.
