from pathlib import Path

from pydoover import config
from pydoover.processor import ManySubscriptionConfig, SerialNumberConfig


class AwsIotProcessorConfig(config.Schema):
    # Subscribed channels are typically written by the integration when it
    # forwards an uplink. Defaults cover the 1.0-style channel names used by
    # existing firmware (device_uplinks). Users can extend per-deployment.
    subscription = ManySubscriptionConfig(default=["device_uplinks"], hidden=True)
    position = config.ApplicationPosition()

    # Thing name — populated from the device's dv_serial_number (set by the
    # control-plane hook to the AWS IoT Thing name).
    serial_number = SerialNumberConfig(
        description="AWS IoT Thing name (e.g. org-123-456)",
        hidden=True,
        default="",
    )

    hide_ui = config.Boolean(
        "Hide Default UI",
        description="Hide the default UI. Useful if you have a custom UI application.",
        default=False,
    )


def export():
    AwsIotProcessorConfig.export(
        Path(__file__).parents[2] / "doover_config.json",
        "aws_iot_processor",
    )
