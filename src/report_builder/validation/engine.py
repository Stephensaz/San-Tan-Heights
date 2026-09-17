from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from src.report_builder.dependencies import ReportDependencyManifest
from src.report_builder.hashing.canonical_payload_hash import CanonicalPayloadHashEngine, CanonicalPayloadHashError
from src.report_builder.repository import ReportVersion
from src.report_builder.schema import CanonicalReportSchema, CanonicalReportSchemaError


@dataclass(frozen=True)
class ReportValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ReportValidationResult:
    valid: bool
    issues: tuple[ReportValidationIssue, ...]


class ReportValidationEngine:
    """Fail-closed semantic validation gate before a report may advance toward READY/publication."""

    def __init__(self, *, schema: CanonicalReportSchema, payload_hasher: CanonicalPayloadHashEngine):
        self.schema = schema
        self.payload_hasher = payload_hasher

    def validate(self, *, report: ReportVersion, dependency_manifest: ReportDependencyManifest) -> ReportValidationResult:
        issues: list[ReportValidationIssue] = []
        payload = report.canonical_payload
        try:
            self.schema.validate(payload)
        except (CanonicalReportSchemaError, ValueError) as exc:
            issues.append(ReportValidationIssue('CANONICAL_SCHEMA_INVALID', str(exc)))
            return ReportValidationResult(False, tuple(issues))

        metadata = payload['metadata']
        lineage = payload['lineage']
        checks = (
            (metadata['property_id'] == str(report.property_id), 'REPORT_PROPERTY_MISMATCH', 'report property does not match payload'),
            (metadata['report_variant'] == report.report_variant, 'REPORT_VARIANT_MISMATCH', 'report variant does not match payload'),
            (metadata['snapshot_id'] == str(report.snapshot_id), 'REPORT_SNAPSHOT_MISMATCH', 'report snapshot does not match payload'),
            (metadata['report_schema_version'] == report.report_schema_version, 'REPORT_SCHEMA_VERSION_MISMATCH', 'report schema version does not match payload'),
            (metadata['content_contract_version'] == report.content_contract_version, 'CONTENT_CONTRACT_VERSION_MISMATCH', 'content contract version does not match payload'),
            (metadata['variant_policy_version'] == report.variant_policy_version, 'VARIANT_POLICY_VERSION_MISMATCH', 'variant policy version does not match payload'),
            (lineage['dependency_manifest_hash'] == report.dependency_manifest_hash, 'REPORT_DEPENDENCY_HASH_MISMATCH', 'payload lineage does not match report dependency hash'),
            (dependency_manifest.manifest_hash == report.dependency_manifest_hash, 'DEPENDENCY_MANIFEST_HASH_MISMATCH', 'provided dependency manifest does not match report'),
        )
        for ok, code, message in checks:
            if not ok:
                issues.append(ReportValidationIssue(code, message))

        try:
            self.payload_hasher.verify(payload, report.canonical_payload_hash)
        except CanonicalPayloadHashError as exc:
            issues.append(ReportValidationIssue('CANONICAL_PAYLOAD_HASH_MISMATCH', str(exc)))
        if report.stored_payload_hash is not None and report.stored_payload_hash != report.canonical_payload_hash:
            issues.append(ReportValidationIssue('STORED_PAYLOAD_HASH_MISMATCH', 'stored payload hash differs from canonical payload hash'))

        if report.publication_eligible and not (
            report.content_state == 'READY' and report.health_state == 'CLEAN' and report.qa_status == 'PASS'
        ):
            issues.append(ReportValidationIssue('PUBLICATION_ELIGIBILITY_STATE_INVALID', 'publication eligible report is not READY/CLEAN/PASS'))

        return ReportValidationResult(not issues, tuple(issues))
