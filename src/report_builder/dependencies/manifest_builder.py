from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from src.report_builder.findings.selector import FindingSelection
from src.report_builder.wording.resolver import ResolvedWording
from src.shared.canonical_json import canonical_json
from src.shared.hash import sha256_canonical


class ReportDependencyManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ReportDependencyEntry:
    dependency_type: str
    dependency_id: str
    semantic_fingerprint: str
    dependency_version: str
    source_snapshot_id: UUID | None = None

    def semantic_projection(self) -> dict[str, str]:
        return {
            "dependency_type": self.dependency_type,
            "dependency_id": self.dependency_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "dependency_version": self.dependency_version,
        }


@dataclass(frozen=True)
class ReportDependencyManifest:
    entries: tuple[ReportDependencyEntry, ...]
    manifest_hash: str

    def semantic_projection(self) -> list[dict[str, str]]:
        return [entry.semantic_projection() for entry in self.entries]


class ReportDependencyManifestBuilder:
    """Builds the exact semantic dependency set consumed by one report variant."""

    def build(
        self,
        *,
        snapshot_id: UUID,
        selections: Iterable[FindingSelection],
        resolved_wording: dict[str, ResolvedWording],
        report_schema_version: str,
        content_contract_version: str,
        variant_policy_id: str,
        variant_policy_version: str,
        section_registry_id: str,
        section_registry_version: str,
        friendly_label_registry_id: str,
        friendly_label_version: str,
        glossary_registry_id: str,
        glossary_version: str,
    ) -> ReportDependencyManifest:
        entries: list[ReportDependencyEntry] = []
        seen_findings: set[str] = set()
        for selection in selections:
            finding = selection.finding
            if finding.finding_id in seen_findings:
                raise ReportDependencyManifestError(f"duplicate consumed finding: {finding.finding_id}")
            seen_findings.add(finding.finding_id)
            try:
                wording = resolved_wording[finding.finding_id]
            except KeyError as exc:
                raise ReportDependencyManifestError(
                    f"missing resolved wording dependency for finding {finding.finding_id}"
                ) from exc
            entries.extend([
                ReportDependencyEntry(
                    "PRODUCTION_FINDING", finding.finding_id, finding.semantic_fingerprint,
                    "semantic-v1", snapshot_id,
                ),
                ReportDependencyEntry(
                    "PASSPORT", finding.passport_id, finding.passport_semantic_fingerprint,
                    finding.passport_version, snapshot_id,
                ),
                ReportDependencyEntry(
                    "APPROVED_WORDING", f"{finding.finding_id}",
                    sha256_canonical({"text": wording.text, "version": wording.version}),
                    wording.version, snapshot_id,
                ),
            ])

        config_entries = (
            ("REPORT_SCHEMA", "canonical-report", report_schema_version),
            ("CONTENT_CONTRACT", "report-content", content_contract_version),
            ("VARIANT_POLICY", variant_policy_id, variant_policy_version),
            ("REPORT_SECTIONS", section_registry_id, section_registry_version),
            ("FRIENDLY_LABELS", friendly_label_registry_id, friendly_label_version),
            ("GLOSSARY", glossary_registry_id, glossary_version),
        )
        for dep_type, dep_id, version in config_entries:
            if not version or not str(version).strip():
                raise ReportDependencyManifestError(f"missing dependency version: {dep_type}")
            entries.append(ReportDependencyEntry(
                dep_type, dep_id, sha256_canonical({"id": dep_id, "version": version}), str(version), None
            ))

        unique: dict[tuple[str, str], ReportDependencyEntry] = {}
        for entry in entries:
            key = (entry.dependency_type, entry.dependency_id)
            prior = unique.get(key)
            if prior is not None and prior != entry:
                raise ReportDependencyManifestError(f"conflicting dependency entry: {key}")
            unique[key] = entry
        ordered = tuple(sorted(unique.values(), key=lambda x: (x.dependency_type, x.dependency_id)))
        semantic = [entry.semantic_projection() for entry in ordered]
        return ReportDependencyManifest(ordered, sha256_canonical(semantic))
