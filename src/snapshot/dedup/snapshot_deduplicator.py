from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class SnapshotDeduplicationResult:
    status: str
    snapshot_id: UUID | None = None

class SnapshotDeduplicator:
    """Finds a valid semantically-equivalent snapshot before version allocation."""
    def __init__(self, repository):
        self.repository = repository

    def check(self, cursor, property_id: UUID, semantic_fingerprint: str) -> SnapshotDeduplicationResult:
        existing = self.repository.find_equivalent(cursor, property_id, semantic_fingerprint)
        if existing is None:
            return SnapshotDeduplicationResult("NEW_SNAPSHOT_REQUIRED")
        return SnapshotDeduplicationResult("EXISTING_EQUIVALENT", existing)
