from pydoover.tags import Tag, Tags


class AwsIotTags(Tags):
    last_uplink_at = Tag("string", default=None)
    last_uplink_channel = Tag("string", default=None)
    last_payload = Tag("object", default=None)
    uplink_count = Tag("integer", default=0)
