class PublicationChannelPointerModel:
    """Reads explicit current render pointer for one delivery channel."""
    def __init__(self, repository): self.repository=repository
    def resolve(self, cursor, *, property_id, report_variant, channel):
        return self.repository.get_channel_pointer(cursor, property_id, report_variant, channel)
