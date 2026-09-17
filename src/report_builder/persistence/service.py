from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.report_builder.deduplication import ReportDeduplicationEngine
from src.report_builder.dependencies import ReportDependencyManifest
from src.report_builder.hashing.canonical_payload_hash import CanonicalPayloadHashEngine
from src.report_builder.repository import ReportDependency, ReportRepository, ReportVersion
from src.report_builder.versioning import ReportVersionAllocator


class ReportPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistReportCommand:
    property_id: UUID
    report_variant: str
    snapshot_id: UUID
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str
    builder_version: str
    report_input_hash: str
    canonical_payload: dict
    dependency_manifest: ReportDependencyManifest
    generation_reason: str
    created_by: str = 'REPORT_BUILDER'


@dataclass(frozen=True)
class PersistReportResult:
    report_id: UUID
    version_number: int | None
    reused_existing: bool
    canonical_payload_hash: str | None


class ReportPersistenceService:
    """Persists one immutable semantic report version in the caller's transaction."""

    def __init__(self, *, repository: ReportRepository, allocator: ReportVersionAllocator,
                 deduplication: ReportDeduplicationEngine, payload_hasher: CanonicalPayloadHashEngine):
        self.repository = repository
        self.allocator = allocator
        self.deduplication = deduplication
        self.payload_hasher = payload_hasher

    def persist(self, cursor, command: PersistReportCommand) -> PersistReportResult:
        self.repository.lock_target(cursor, command.property_id, command.report_variant)
        duplicate = self.deduplication.find(
            cursor,
            property_id=command.property_id,
            report_variant=command.report_variant,
            report_input_hash=command.report_input_hash,
        )
        if duplicate.reused:
            return PersistReportResult(duplicate.existing_report_id, None, True, None)

        payload_identity = self.payload_hasher.calculate(command.canonical_payload)
        if command.canonical_payload.get('metadata', {}).get('property_id') != str(command.property_id):
            raise ReportPersistenceError('PAYLOAD_PROPERTY_MISMATCH')
        if command.canonical_payload.get('metadata', {}).get('report_variant') != command.report_variant:
            raise ReportPersistenceError('PAYLOAD_VARIANT_MISMATCH')
        if command.canonical_payload.get('metadata', {}).get('snapshot_id') != str(command.snapshot_id):
            raise ReportPersistenceError('PAYLOAD_SNAPSHOT_MISMATCH')
        if command.canonical_payload.get('lineage', {}).get('dependency_manifest_hash') != command.dependency_manifest.manifest_hash:
            raise ReportPersistenceError('DEPENDENCY_MANIFEST_HASH_MISMATCH')

        version_number = self.allocator.allocate(cursor, command.property_id, command.report_variant)
        report_id = uuid4()
        report = ReportVersion(
            report_id=report_id,
            property_id=command.property_id,
            report_variant=command.report_variant,
            version_number=version_number,
            snapshot_id=command.snapshot_id,
            report_schema_version=command.report_schema_version,
            content_contract_version=command.content_contract_version,
            variant_policy_version=command.variant_policy_version,
            builder_version=command.builder_version,
            report_input_hash=command.report_input_hash,
            canonical_payload_hash=payload_identity.canonical_payload_hash,
            stored_payload_hash=payload_identity.canonical_payload_hash,
            canonical_payload=command.canonical_payload,
            dependency_manifest_hash=command.dependency_manifest.manifest_hash,
            generation_reason=command.generation_reason,
            created_by=command.created_by,
        )
        self.repository.insert_report(cursor, report)
        for entry in command.dependency_manifest.entries:
            self.repository.insert_dependency(cursor, ReportDependency(
                report_dependency_id=uuid4(),
                report_id=report_id,
                dependency_type=entry.dependency_type,
                dependency_id=entry.dependency_id,
                semantic_fingerprint=entry.semantic_fingerprint,
                dependency_version=entry.dependency_version,
                source_snapshot_id=entry.source_snapshot_id,
            ))
        return PersistReportResult(report_id, version_number, False, payload_identity.canonical_payload_hash)
