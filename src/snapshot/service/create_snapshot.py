from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4
from src.shared.hash import sha256_canonical
from src.snapshot.findings import FindingFreezer
from src.snapshot.passports import PassportLineageCapture
from src.snapshot.fingerprints import FindingFingerprintEngine, SnapshotFingerprintEngine
from src.snapshot.requirements import SnapshotRequirementEngine
from src.snapshot.dependencies import DependencyManifestBuilder
from src.snapshot.dedup import SnapshotDeduplicator
from src.snapshot.repository import (
    SnapshotRepository, SnapshotFindingRepository, SnapshotDependencyRepository,
    SnapshotRequirementRepository, SnapshotRecord, SnapshotFindingRecord,
    SnapshotDependencyRecord, SnapshotRequirementResultRecord,
)

class SnapshotCreationError(RuntimeError):
    pass

@dataclass(frozen=True)
class CreateSnapshotResult:
    status: str
    snapshot_id: UUID | None
    semantic_fingerprint: str | None = None
    completeness_status: str | None = None

class SnapshotCreationService:
    """Creates one immutable snapshot from one coherent governed-state read.

    The caller owns the database transaction. Any exception must cause caller rollback.
    """
    def __init__(self, *, governed_state_client, requirements, passport_resolver,
                 snapshot_repository=None, finding_repository=None, dependency_repository=None,
                 requirement_repository=None):
        self.client = governed_state_client
        self.requirement_engine = SnapshotRequirementEngine(requirements)
        self.freezer = FindingFreezer()
        self.passports = PassportLineageCapture(passport_resolver)
        self.finding_fp = FindingFingerprintEngine()
        self.dependency_builder = DependencyManifestBuilder()
        self.snapshot_fp = SnapshotFingerprintEngine()
        self.snapshots = snapshot_repository or SnapshotRepository()
        self.findings = finding_repository or SnapshotFindingRepository()
        self.dependencies = dependency_repository or SnapshotDependencyRepository()
        self.requirements = requirement_repository or SnapshotRequirementRepository()
        self.dedup = SnapshotDeduplicator(self.snapshots)

    def create(self, cursor, *, property_id: UUID, snapshot_reason: str, created_by: str) -> CreateSnapshotResult:
        state = self.client.get(property_id)
        evaluation = self.requirement_engine.evaluate(state)
        if evaluation.completeness_status == "INVALID":
            raise SnapshotCreationError("SNAPSHOT_STATE_INVALID")
        if evaluation.completeness_status == "BLOCKED":
            return CreateSnapshotResult("BLOCKED", None, completeness_status="BLOCKED")

        frozen = self.freezer.freeze(state.findings)
        passport_refs = self.passports.capture(frozen)
        passport_by_finding = {p.finding_id: p for p in passport_refs}
        for finding in frozen:
            self.finding_fp.verify_upstream(finding, passport_by_finding[finding.finding_id])

        deps = self.dependency_builder.build(state.dependencies)
        fps = self.snapshot_fp.calculate(
            property_id=property_id,
            intelligence_schema_version=state.intelligence_schema_version,
            governance_schema_version=state.governance_schema_version,
            findings=frozen,
            dependencies=deps,
        )

        # Re-read the governed state immediately before persistence to prevent a hybrid snapshot.
        latest = self.client.get(property_id)
        if latest.source_read_token != state.source_read_token:
            raise SnapshotCreationError("SOURCE_STATE_CHANGED_DURING_CAPTURE")

        duplicate = self.dedup.check(cursor, property_id, fps.semantic_fingerprint)
        if duplicate.status == "EXISTING_EQUIVALENT":
            return CreateSnapshotResult("EXISTING_EQUIVALENT", duplicate.snapshot_id, fps.semantic_fingerprint, evaluation.completeness_status)

        snapshot_id = uuid4()
        sequence = self.snapshots.allocate_sequence(cursor, property_id)
        supersedes = self.snapshots.current_accepted(cursor, property_id)
        snapshot_hash = self._snapshot_hash(state, frozen, passport_refs, deps, evaluation.results, fps)
        now = datetime.now(timezone.utc)
        self.snapshots.insert(cursor, SnapshotRecord(
            snapshot_id, property_id, sequence, snapshot_reason, state.governed_state_version,
            state.source_read_token, state.intelligence_schema_version, state.governance_schema_version,
            state.model_version, fps.semantic_fingerprint, fps.agent_semantic_fingerprint,
            fps.seller_semantic_fingerprint, fps.public_semantic_fingerprint, snapshot_hash,
            evaluation.completeness_status, "PASS", created_by, now, supersedes,
        ))
        for finding in frozen:
            p = passport_by_finding[finding.finding_id]
            self.findings.insert(cursor, SnapshotFindingRecord(
                uuid4(), snapshot_id, finding.finding_id, finding.finding_type,
                finding.passport_id, finding.passport_version, p.passport_semantic_fingerprint,
                finding.canonical_value, finding.confidence_code, finding.qa_status,
                finding.production_status, finding.publication_scope, finding.agent_wording,
                finding.seller_wording, finding.public_wording, finding.agent_wording_version,
                finding.seller_wording_version, finding.public_wording_version,
                finding.semantic_fingerprint, finding.evidence_reference_set_hash,
            ))
        for dep in deps:
            scope=set(dep.variant_scope)
            self.dependencies.insert(cursor, SnapshotDependencyRecord(
                uuid4(), snapshot_id, dep.dependency_type, dep.dependency_id,
                dep.record_fingerprint, dep.semantic_fingerprint, dep.dependency_version,
                dep.required, "AGENT" in scope, "SELLER" in scope, "PUBLIC" in scope,
            ))
        for req in evaluation.results:
            self.requirements.insert(cursor, SnapshotRequirementResultRecord(
                uuid4(), snapshot_id, req.requirement_id, req.requirement_scope,
                req.required_flag, req.status, req.finding_id, req.dependency_type,
                req.dependency_id, req.reason_code,
            ))
        return CreateSnapshotResult("CREATED", snapshot_id, fps.semantic_fingerprint, evaluation.completeness_status)

    @staticmethod
    def _snapshot_hash(state, findings, passports, dependencies, requirements, fps) -> str:
        return sha256_canonical({
            "property_id": str(state.property_id),
            "governed_state_version": state.governed_state_version,
            "source_read_token": state.source_read_token,
            "intelligence_schema_version": state.intelligence_schema_version,
            "governance_schema_version": state.governance_schema_version,
            "model_version": state.model_version,
            "findings": [asdict(x) for x in findings],
            "passports": [asdict(x) for x in passports],
            "dependencies": [asdict(x) for x in dependencies],
            "requirements": [asdict(x) for x in requirements],
            "semantic_fingerprint": fps.semantic_fingerprint,
            "agent_semantic_fingerprint": fps.agent_semantic_fingerprint,
            "seller_semantic_fingerprint": fps.seller_semantic_fingerprint,
            "public_semantic_fingerprint": fps.public_semantic_fingerprint,
        })
