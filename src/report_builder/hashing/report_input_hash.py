from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from src.report_builder.dependencies import ReportDependencyManifest
from src.report_builder.findings.selector import FindingSelection
from src.report_builder.wording.resolver import ResolvedWording
from src.shared.hash import sha256_canonical


class ReportInputHashError(ValueError):
    pass


@dataclass(frozen=True)
class ReportInputIdentity:
    report_input_hash: str
    semantic_projection: dict


class ReportInputHashEngine:
    """Hashes semantic report inputs only; operational/render metadata is intentionally excluded."""

    def calculate(
        self,
        *,
        property_id: str,
        report_variant: str,
        selections: Iterable[FindingSelection],
        resolved_wording: dict[str, ResolvedWording],
        dependency_manifest: ReportDependencyManifest,
        report_schema_version: str,
        content_contract_version: str,
        variant_policy_version: str,
        friendly_label_version: str,
        glossary_version: str,
    ) -> ReportInputIdentity:
        if report_variant not in {"AGENT", "SELLER", "PUBLIC"}:
            raise ReportInputHashError(f"unsupported report variant: {report_variant}")
        finding_inputs = []
        for selection in selections:
            finding = selection.finding
            if finding.finding_id not in resolved_wording:
                raise ReportInputHashError(f"missing wording for finding: {finding.finding_id}")
            wording = resolved_wording[finding.finding_id]
            finding_inputs.append({
                "finding_id": finding.finding_id,
                "finding_type": finding.finding_type,
                "section_id": selection.section_id,
                "semantic_fingerprint": finding.semantic_fingerprint,
                "wording_text": wording.text,
                "wording_version": wording.version,
            })
        finding_inputs.sort(key=lambda x: (x["section_id"], x["finding_type"], x["finding_id"]))
        projection = {
            "property_id": str(property_id),
            "report_variant": report_variant,
            "findings": finding_inputs,
            "dependency_manifest": dependency_manifest.semantic_projection(),
            "report_schema_version": report_schema_version,
            "content_contract_version": content_contract_version,
            "variant_policy_version": variant_policy_version,
            "friendly_label_version": friendly_label_version,
            "glossary_version": glossary_version,
        }
        return ReportInputIdentity(sha256_canonical(projection), projection)
