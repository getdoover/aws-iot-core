import logging
from datetime import datetime, timezone, timedelta

from pydoover.processor import Application
from pydoover.models import MessageCreateEvent, ConnectionStatus

from .app_config import AwsIotProcessorConfig
from .app_tags import AwsIotTags
from .app_ui import AwsIotUI

log = logging.getLogger(__name__)

# Channel on the integration's agent that triggers a downlink publish.
# Mirrors the constant in integration.application.
DOWNLINK_REQUEST_CHANNEL = "aws_iot_downlink_request"


class AwsIotProcessor(Application):
    config_cls = AwsIotProcessorConfig
    ui_cls = AwsIotUI
    tags_cls = AwsIotTags

    config: AwsIotProcessorConfig
    tags: AwsIotTags
    ui: AwsIotUI

    async def on_message_create(self, event: MessageCreateEvent):
        """
        Handle an AWS IoT uplink forwarded by the integration on any
        subscribed channel. Updates observability tags and pings the
        device's connection status.
        """
        channel = event.channel.name
        data = event.message.data
        log.info("AWS IoT uplink on %s: %s", channel, data)

        now = datetime.now(timezone.utc)
        await self.tags.last_uplink_at.set(int(now.timestamp() * 1000))
        await self.tags.last_uplink_channel.set(channel)
        await self.tags.uplink_count.set(self.tags.uplink_count.value + 1)
        # await self.ping_connection(online_at=now)

    async def send_downlink(self, channel: str, payload) -> None:
        """
        Helper for subclasses / downstream apps: request a downlink publish
        via the integration. Fire-and-forget — the integration's
        on_message_create handler picks this up and publishes to MQTT.
        """
        thing_name = self.config.serial_number.value
        if not thing_name:
            log.error("No serial_number configured — cannot send downlink")
            return

        await self.api.create_message(
            DOWNLINK_REQUEST_CHANNEL,
            {
                "thing_name": thing_name,
                "channel": channel,
                "payload": payload,
            },
            # agent_id omitted — defaults to the integration agent when the
            # processor's permissions cover it. Callers can override if needed.
        )
