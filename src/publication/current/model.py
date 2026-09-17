class CurrentSemanticReportModel:
    """Reads only the explicit semantic-current pointer; never infers current via MAX(version)."""
    def __init__(self, repository): self.repository=repository
    def resolve(self, cursor, *, property_id, report_variant):
        return self.repository.get_current_report(cursor, property_id, report_variant)
