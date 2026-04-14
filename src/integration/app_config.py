from pathlib import Path

from pydoover import config
from pydoover.processor import IngestionEndpointConfig, ExtendedPermissionsConfig


class AwsIotIntegrationConfig(config.Schema):
    permissions = ExtendedPermissionsConfig()

    aws_region = config.String(
        "AWS Region",
        description="AWS region for the IoT Core account (e.g. ap-southeast-2).",
        default="ap-southeast-2",
    )
    aws_iot_endpoint = config.String(
        "AWS IoT Endpoint",
        description=(
            "ATS data endpoint hostname for the account "
            "(e.g. xxxxx-ats.iot.ap-southeast-2.amazonaws.com). "
            "Populated automatically by doover-control on first device."
        ),
        default="",
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


def export():
    AwsIotIntegrationConfig.export(
        Path(__file__).parents[2] / "doover_config.json",
        "aws_iot_integration",
    )
