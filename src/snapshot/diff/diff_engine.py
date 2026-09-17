from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID, uuid4
from src.shared.hash import sha256_canonical
from src.snapshot.repository import SnapshotDiffRecord

class SnapshotDiffError(ValueError):
    pass

@dataclass(frozen=True)
class SnapshotDiffResult:
    old_snapshot_id: UUID
    new_snapshot_id: UUID
    diff_payload: dict[str, Any]
    diff_hash: str

class SnapshotDiffEngine:
    def _index_findings(self, rows: Iterable[Any]) -> dict[str, Any]:
        out = {}
        for r in rows:
            if r.finding_id in out:
                raise SnapshotDiffError(f"duplicate finding_id: {r.finding_id}")
            out[r.finding_id] = r
        return out

    def _index_dependencies(self, rows: Iterable[Any]) -> dict[tuple[str, str], Any]:
        out = {}
        for r in rows:
            key = (r.dependency_type, r.dependency_id)
            if key in out:
                raise SnapshotDiffError(f"duplicate dependency: {key[0]}:{key[1]}")
            out[key] = r
        return out

    def compare(self, *, old_snapshot_id: UUID, new_snapshot_id: UUID,
                old_findings=(), new_findings=(), old_dependencies=(), new_dependencies=()) -> SnapshotDiffResult:
        if old_snapshot_id == new_snapshot_id:
            raise SnapshotDiffError("snapshots must differ")
        old_f = self._index_findings(old_findings)
        new_f = self._index_findings(new_findings)
        old_d = self._index_dependencies(old_dependencies)
        new_d = self._index_dependencies(new_dependencies)
        finding_changes = []
        for fid in sorted(set(old_f) | set(new_f)):
            a, b = old_f.get(fid), new_f.get(fid)
            if a is None:
                finding_changes.append({"finding_id": fid, "change_type": "ADDED"}); continue
            if b is None:
                finding_changes.append({"finding_id": fid, "change_type": "REMOVED"}); continue
            if a.semantic_fingerprint == b.semantic_fingerprint:
                continue
            if a.canonical_value != b.canonical_value:
                change_type = "VALUE_CHANGED"
            elif a.confidence_code != b.confidence_code:
                change_type = "CONFIDENCE_CHANGED"
            elif a.qa_status != b.qa_status:
                change_type = "QA_CHANGED"
            elif a.publication_scope != b.publication_scope:
                change_type = "PUBLICATION_SCOPE_CHANGED"
            elif (a.agent_wording, a.seller_wording, a.public_wording,
                  a.agent_wording_version, a.seller_wording_version, a.public_wording_version) != (
                  b.agent_wording, b.seller_wording, b.public_wording,
                  b.agent_wording_version, b.seller_wording_version, b.public_wording_version):
                change_type = "WORDING_CHANGED"
            else:
                change_type = "SEMANTIC_CHANGED"
            finding_changes.append({"finding_id": fid, "change_type": change_type,
                                    "old_fingerprint": a.semantic_fingerprint,
                                    "new_fingerprint": b.semantic_fingerprint})
        dependency_changes = []
        for key in sorted(set(old_d) | set(new_d)):
            a, b = old_d.get(key), new_d.get(key)
            dtype, did = key
            if a is None:
                dependency_changes.append({"dependency_type": dtype, "dependency_id": did, "change_type": "ADDED"}); continue
            if b is None:
                dependency_changes.append({"dependency_type": dtype, "dependency_id": did, "change_type": "REMOVED"}); continue
            if a.semantic_fingerprint != b.semantic_fingerprint:
                dependency_changes.append({"dependency_type": dtype, "dependency_id": did,
                                           "change_type": "SEMANTIC_CHANGED",
                                           "old_fingerprint": a.semantic_fingerprint,
                                           "new_fingerprint": b.semantic_fingerprint})
            elif a.dependency_version != b.dependency_version or a.record_fingerprint != b.record_fingerprint:
                dependency_changes.append({"dependency_type": dtype, "dependency_id": did,
                                           "change_type": "VERSION_CHANGED_NON_SEMANTIC"})
        payload = {"old_snapshot_id": str(old_snapshot_id), "new_snapshot_id": str(new_snapshot_id),
                   "finding_changes": finding_changes, "dependency_changes": dependency_changes}
        return SnapshotDiffResult(old_snapshot_id, new_snapshot_id, payload, sha256_canonical(payload))

    def persist(self, cursor, repository, result: SnapshotDiffResult):
        repository.insert(cursor, SnapshotDiffRecord(uuid4(), result.old_snapshot_id,
                         result.new_snapshot_id, result.diff_payload, result.diff_hash))
