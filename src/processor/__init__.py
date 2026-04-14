from typing import Any

from pydoover.processor import run_app

from .application import AwsIotProcessor


def handler(event: dict[str, Any], context):
    """Lambda handler entry point."""
    run_app(
        AwsIotProcessor(),
        event,
        context,
    )
