# AWS IoT Core connector for Doover

Mirrors the `tts` connector. Contains:

- **integration** — runs on ingestion endpoint posts from AWS IoT topic rules.
  Extracts the Thing name and channel from the MQTT topic, forwards the
  payload to the corresponding device agent. Also handles downlink publish
  requests by calling AWS IoT Core's HTTPS data API with mTLS using a
  per-org publish certificate stored in the integration's deployment config.
- **processor** — runs on device agents. Receives the forwarded uplink
  message and updates tags / UI.

## Topic scheme

Uplinks travel on `$aws/things/{thing}/doover_channel/{channel}`. The AWS
topic rule forwards everything matching `$aws/things/org-{orgId}-+/doover_channel/#`
(plus legacy patterns when applicable) to the integration's ingestion URL.

Downlinks are published to `aws/things/{thing}/{channel}` (non-reserved
prefix — mirrors doover 1.0).

## Provisioning

The AWS IoT resources (Thing, device cert, per-org publish cert, topic rule,
HTTPS destination) are created by the control-plane hook in doover-control
(`doover_control/devices/hooks/aws_iot.py`). This app only consumes what the
hook set up — it does not create any AWS resources itself.

The integration's deployment config is populated by doover-control on first
device creation, including the publish cert PEM + private key.
