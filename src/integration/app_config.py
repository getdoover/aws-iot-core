from pathlib import Path

from pydoover import config
from pydoover.processor import IngestionEndpointConfig, ExtendedPermissionsConfig, EgressChannelConfig


class AwsIotIntegrationConfig(config.Schema):
    permissions = ExtendedPermissionsConfig()

    aws_role_arn = config.String(
        "AWS Role ARN (cross-account)",
        description=(
            "If set, doover-control will assume this role via STS instead of "
            "using static access keys. Recommended for BYO accounts — no "
            "long-lived secrets leave your AWS account."
        ),
        default="",
    )
    aws_external_id = config.String(
        "AWS External ID",
        description=(
            "External ID expected by the trust policy on the role above. "
            "Protects against the confused-deputy problem."
        ),
        default="",
    )
    aws_region = config.String(
        "AWS Region",
        description="AWS region for the IoT Core account (e.g. ap-southeast-2).",
        default="ap-southeast-2",
    )
    aws_access_key_id = config.String(
        "AWS Access Key ID",
        description=(
            "Access key for a BYO AWS account. Leave blank to use the "
            "doover production AWS account."
        ),
        default="",
        hidden=True
    )
    aws_secret_access_key = config.String(
        "AWS Secret Access Key",
        description="Secret key paired with the access key above.",
        default="",
        hidden=True
    )
    legacy_mode = config.Boolean(
        "Legacy Mode",
        description=(
            "If enabled, this integration absorbs pre-existing AWS IoT Things "
            "whose names don't follow the `dv-{integration_id}-` convention. "
            "Topic rule matches any non-`dv-`-prefixed Thing; publish policy "
            "is broadened to `aws/things/*/*`. Set before creating the first "
            "device. An integration is either all-legacy or all-new."
        ),
        default=False,
    )

    aws_iot_endpoint = config.String(
        "AWS IoT Endpoint",
        description=(
            "ATS data endpoint hostname for the account "
            "(e.g. xxxxx-ats.iot.ap-southeast-2.amazonaws.com). "
            "Populated automatically by doover-control on first device."
        ),
        default="",
        hidden=True
    )

    publish_certificate_pem = config.String(
        "Publish Certificate (PEM)",
        description=(
            "Per-org doover publish certificate, populated by doover-control. "
            "Used as mTLS client cert when publishing downlinks."
        ),
        default="",
        hidden=True
    )
    publish_private_key = config.String(
        "Publish Private Key",
        description="Private key for the publish certificate. Populated by doover-control.",
        default="",
        hidden=True
    )

    integration = IngestionEndpointConfig()
    egress_channel = EgressChannelConfig(default="aws_iot_downlink_request")


def export():
    AwsIotIntegrationConfig.export(
        Path(__file__).parents[2] / "doover_config.json",
        "aws_iot_core_integration",
    )
