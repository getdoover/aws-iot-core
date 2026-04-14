import json
import logging
import os
import tempfile

import requests
from pydoover.processor import Application
from pydoover.models import IngestionEndpointEvent, MessageCreateEvent

from .app_config import AwsIotIntegrationConfig

log = logging.getLogger(__name__)

# Channel name the processor writes to when it wants to send a downlink.
# Messages on this channel (on the integration's own agent) trigger a
# publish to aws/things/{thing}/{channel} via the per-org publish cert.
DOWNLINK_REQUEST_CHANNEL = "aws_iot_downlink_request"


class AwsIotIntegration(Application):
    config: AwsIotIntegrationConfig
    config_cls = AwsIotIntegrationConfig

    _cert_paths: tuple[str, str] | None = None

    async def setup(self):
        log.info("AWS IoT Core integration initialized")

    # -- Uplink path ---------------------------------------------------------

    async def on_ingestion_endpoint(self, event: IngestionEndpointEvent):
        """
        Handle an AWS IoT topic rule HTTPS forward.

        The rule is:
            SELECT *, topic() as topic FROM '$aws/things/+/doover_channel/#'

        so `payload` is the message body plus a `topic` field we use to
        recover the Thing name (segment 3) and the channel name (segments
        after 'doover_channel').
        """
        payload = event.payload
        if payload is None:
            log.warning("Received empty AWS IoT payload")
            return

        topic = None
        if isinstance(payload, dict):
            topic = payload.get("topic")
        if not topic:
            log.warning("No topic in AWS IoT payload — rule must include topic() as topic")
            return

        segments = topic.split("/")
        # Expected: ['$aws', 'things', '<thing>', 'doover_channel', '<channel>', ...]
        if len(segments) < 5 or segments[1] != "things" or segments[3] != "doover_channel":
            log.warning("Unexpected topic shape: %s", topic)
            return

        thing_name = segments[2]
        channel_name = "/".join(segments[4:])

        log.info("AWS IoT uplink: thing=%s channel=%s", thing_name, channel_name)

        # Look up the Doover agent for this Thing via the serial_number_lookup
        # tag (populated by processor apps whose serial_number matches the
        # thing name).
        agent_id = self._lookup_agent(thing_name)

        # Record the raw event on the integration's own agent for audit.
        await self.api.create_message("aws_iot_events", payload)

        if agent_id is None:
            log.info("No agent mapped to thing %s — event stored only", thing_name)
            return

        # Forward the decoded payload body to the device agent on the matching
        # channel name. Strip the topic-echo field we added in the rule SQL.
        body = {k: v for k, v in payload.items() if k != "topic"} if isinstance(payload, dict) else payload
        await self.api.create_message(channel_name, body, agent_id=agent_id)

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

        data = event.message.data
        if not isinstance(data, dict):
            log.warning("Downlink request payload must be a dict, got %r", type(data))
            return

        thing_name = data.get("thing_name")
        channel = data.get("channel")
        body = data.get("payload")
        if not thing_name or not channel:
            log.warning("Downlink request missing thing_name/channel: %s", data)
            return

        self._publish_downlink(thing_name, channel, body)

    # -- Helpers -------------------------------------------------------------

    def _lookup_agent(self, thing_name: str) -> int | None:
        try:
            mapping = self.tag_manager.get_tag(
                "serial_number_lookup",
                app_key="aws_iot_processor_1",
                raise_key_error=True,
            )
        except KeyError:
            log.debug("serial_number_lookup tag missing; processor not yet installed?")
            return None
        return mapping.get(thing_name)

    def _ensure_cert_files(self) -> tuple[str, str] | None:
        """Write the publish cert + key to /tmp on first use; cache paths."""
        if self._cert_paths is not None:
            return self._cert_paths

        cert_pem = self.config.publish_certificate_pem.value
        priv_key = self.config.publish_private_key.value
        if not cert_pem or not priv_key:
            log.error(
                "No publish certificate configured — doover-control should "
                "populate publish_certificate_pem + publish_private_key on "
                "first device provisioning."
            )
            return None

        tmpdir = tempfile.gettempdir()
        cert_path = os.path.join(tmpdir, "aws_iot_publish.crt")
        key_path = os.path.join(tmpdir, "aws_iot_publish.key")
        with open(cert_path, "w") as f:
            f.write(cert_pem)
        with open(key_path, "w") as f:
            f.write(priv_key)
        os.chmod(key_path, 0o600)

        self._cert_paths = (cert_path, key_path)
        return self._cert_paths

    def _publish_downlink(self, thing_name: str, channel: str, body) -> None:
        endpoint = self.config.aws_iot_endpoint.value
        if not endpoint:
            log.error("No aws_iot_endpoint configured; cannot publish downlink")
            return

        certs = self._ensure_cert_files()
        if certs is None:
            return

        topic = f"aws/things/{thing_name}/{channel}"
        url = f"https://{endpoint}:8443/topics/{topic}?qos=1"

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
            resp = requests.post(
                url,
                data=payload_bytes,
                headers={"Content-Type": content_type},
                cert=certs,
                timeout=10,
            )
        except requests.RequestException as e:
            log.error("Downlink publish to %s failed: %s", topic, e)
            return

        if resp.status_code >= 300:
            log.error(
                "Downlink publish to %s failed %s: %s",
                topic, resp.status_code, resp.text,
            )
        else:
            log.info("Published downlink to %s", topic)
