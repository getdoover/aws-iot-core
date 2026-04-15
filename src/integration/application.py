import json
import logging
import os
import ssl
from dataclasses import dataclass
from typing import Any

import httpx
from pydoover.processor import Application
from pydoover.models import IngestionEndpointEvent, MessageCreateEvent

from .app_config import AwsIotIntegrationConfig

log = logging.getLogger(__name__)

# Channel name the processor writes to when it wants to send a downlink.
# Messages on this channel (on the integration's own agent) trigger a
# publish to aws/things/{thing}/{channel} via the per-org publish cert.
DOWNLINK_REQUEST_CHANNEL = "aws_iot_downlink_request"
UPLINK_CHANNEL = "on_aws_iot_event"


@dataclass(frozen=True, slots=True)
class DownlinkRequest:
    thing_name: str
    channel: str
    payload: Any

    @classmethod
    def from_message(cls, data: dict) -> "DownlinkRequest":
        return cls(
            thing_name=data["thing_name"],
            channel=data["channel"],
            payload=data.get("payload"),
        )


class AwsIotIntegration(Application):
    config: AwsIotIntegrationConfig
    config_cls = AwsIotIntegrationConfig

    _ssl_context: ssl.SSLContext | None = None

    # -- Uplink path ---------------------------------------------------------

    async def on_ingestion_endpoint(self, event: IngestionEndpointEvent):
        """
        Handle an AWS IoT topic rule HTTPS forward.

        The rule's `SELECT *, topic() as topic` adds a `topic` field we use
        to recover the Thing name. Uplinks are forwarded to the
        `on_aws_iot_event` channel on the matching agent; the processor
        decides what to do with them.
        """
        payload = event.payload
        if payload is None:
            log.warning("Received empty AWS IoT payload")
            return

        topic = payload.get("topic") if isinstance(payload, dict) else None
        if not topic:
            log.warning("No topic in AWS IoT payload — rule must include topic() as topic")
            return

        segments = topic.split("/")
        if len(segments) < 4 or segments[1] != "things":
            log.warning("Unexpected topic shape: %s", topic)
            return

        thing_name = segments[2]
        log.info("AWS IoT uplink: thing=%s topic=%s", thing_name, topic)

        agent_id = self._lookup_agent(thing_name)

        # Record the raw event on the integration's own agent for audit.
        await self.api.create_message("aws_iot_events", payload)

        if agent_id is None:
            log.info("No agent mapped to thing %s — event stored only", thing_name)
            return

        await self.api.create_message(UPLINK_CHANNEL, payload, agent_id=agent_id)

    # -- Downlink path -------------------------------------------------------

    async def on_message_create(self, event: MessageCreateEvent):
        """
        Handle a downlink-publish request.

        Processors request a downlink by creating a message on the
        `aws_iot_downlink_request` channel of the integration's own agent,
        with payload { "thing_name": ..., "channel": ..., "payload": ... }.
        """
        if event.channel.name != DOWNLINK_REQUEST_CHANNEL:
            return

        await self._publish_downlink(DownlinkRequest.from_message(event.message.data))

    # -- Helpers -------------------------------------------------------------

    def _lookup_agent(self, thing_name: str) -> int | None:
        try:
            mapping = self.tag_manager.get_tag(
                "serial_number_lookup",
                app_key="aws_iot_core_processor_1",
                raise_key_error=True,
            )
        except KeyError:
            log.debug("serial_number_lookup tag missing; processor not yet installed?")
            return None
        return mapping.get(thing_name)

    def _ensure_ssl_context(self) -> ssl.SSLContext | None:
        """Build an SSL context with the publish cert loaded from memory.

        Uses memfd_create + /proc/self/fd/N so the PEM material never touches
        the filesystem. Linux-only, which is fine for the Lambda runtime.
        """
        if self._ssl_context is not None:
            return self._ssl_context

        cert_pem = self.config.publish_certificate_pem.value
        priv_key = self.config.publish_private_key.value
        if not cert_pem or not priv_key:
            log.error(
                "No publish certificate configured — doover-control should "
                "populate publish_certificate_pem + publish_private_key on "
                "first device provisioning."
            )
            return None

        cert_fd = os.memfd_create("aws_iot_cert")
        key_fd = os.memfd_create("aws_iot_key")
        try:
            os.write(cert_fd, cert_pem.encode())
            os.write(key_fd, priv_key.encode())
            ctx = ssl.create_default_context()
            ctx.load_cert_chain(
                certfile=f"/proc/self/fd/{cert_fd}",
                keyfile=f"/proc/self/fd/{key_fd}",
            )
        finally:
            os.close(cert_fd)
            os.close(key_fd)

        self._ssl_context = ctx
        return ctx

    async def _publish_downlink(self, request: DownlinkRequest) -> None:
        endpoint = self.config.aws_iot_endpoint.value
        if not endpoint:
            log.error("No aws_iot_endpoint configured; cannot publish downlink")
            return

        ctx = self._ensure_ssl_context()
        if ctx is None:
            return

        topic = f"aws/things/{request.thing_name}/{request.channel}"
        url = f"https://{endpoint}:8443/topics/{topic}?qos=1"

        body = request.payload
        if isinstance(body, (dict, list)):
            payload_bytes = json.dumps(body).encode()
            content_type = "application/json"
        elif isinstance(body, bytes):
            payload_bytes = body
            content_type = "application/octet-stream"
        else:
            payload_bytes = str(body).encode()
            content_type = "text/plain"

        try:
            async with httpx.AsyncClient(verify=ctx, timeout=10) as client:
                resp = await client.post(
                    url,
                    content=payload_bytes,
                    headers={"Content-Type": content_type},
                )
        except httpx.HTTPError as e:
            log.error("Downlink publish to %s failed: %s", topic, e)
            return

        if resp.status_code >= 300:
            log.error(
                "Downlink publish to %s failed %s: %s",
                topic, resp.status_code, resp.text,
            )
        else:
            log.info("Published downlink to %s", topic)
