from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class CurrentSnapshot:
    property_id: UUID
    current_snapshot_id: UUID
    snapshot_sequence: int
    semantic_fingerprint: str
    agent_semantic_fingerprint: str
    seller_semantic_fingerprint: str
    public_semantic_fingerprint: str
    snapshot_completeness_status: str
    qa_status: str
    created_at: datetime

class CurrentSnapshotReader:
    SQL = '''SELECT property_id,current_snapshot_id,snapshot_sequence,semantic_fingerprint,
    agent_semantic_fingerprint,seller_semantic_fingerprint,public_semantic_fingerprint,
    snapshot_completeness_status,qa_status,created_at
    FROM snapshot.current_snapshot_view WHERE property_id=%s'''
    def get(self, cursor, property_id: UUID):
        cursor.execute(self.SQL, (property_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return CurrentSnapshot(UUID(str(row[0])), UUID(str(row[1])), int(row[2]), str(row[3]), str(row[4]),
                               str(row[5]), str(row[6]), str(row[7]), str(row[8]), row[9])
