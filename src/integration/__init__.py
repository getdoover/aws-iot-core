from typing import Any

from pydoover.processor import run_app

from .application import AwsIotIntegration


def handler(event: dict[str, Any], context):
    """Lambda handler entry point."""
    run_app(
        AwsIotIntegration(),
        event,
        context,
    )
