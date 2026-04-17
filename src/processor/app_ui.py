from pathlib import Path

from pydoover import ui

from .app_tags import AwsIotTags


class AwsIotUI(ui.UI, hidden="$config.app().hide_default_ui"):
    last_uplink_at = ui.Timestamp(
        "Last Uplink",
        value=AwsIotTags.last_uplink_at,
    )
    last_uplink_channel = ui.TextVariable(
        "Last Channel",
        value=AwsIotTags.last_uplink_channel,
    )
    uplink_count = ui.NumericVariable(
        "Uplinks Received",
        value=AwsIotTags.uplink_count,
        precision=0,
    )


def export():
    AwsIotUI(None, None, None).export(
        Path(__file__).parents[2] / "doover_config.json",
        "aws_iot_core_processor",
    )
