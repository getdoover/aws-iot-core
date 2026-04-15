from pydoover.tags import Tag, Tags


class AwsIotTags(Tags):
    last_uplink_at = Tag("integer", default=None)
    last_uplink_channel = Tag("string", default=None)
    uplink_count = Tag("integer", default=0)
