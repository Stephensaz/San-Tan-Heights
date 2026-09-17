from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from src.snapshot.governed_state.models import GovernedFinding

class FindingFreezeError(ValueError):
    pass

@dataclass(frozen=True)
class FrozenFinding:
    finding_id: str
    finding_type: str
    passport_id: str
    passport_version: str
    canonical_value: Any
    confidence_code: str
    qa_status: str
    production_status: str
    publication_scope: str
    agent_wording: str | None
    seller_wording: str | None
    public_wording: str | None
    agent_wording_version: str | None
    seller_wording_version: str | None
    public_wording_version: str | None
    semantic_fingerprint: str
    evidence_reference_set_hash: str

class FindingFreezer:
    ELIGIBLE={"PRODUCTION_READY"}
    EXCLUDED={"BLOCKED","DEPRECATED","SUPERSEDED","INTERNAL_ONLY"}

    def freeze(self, findings: tuple[GovernedFinding, ...]) -> tuple[FrozenFinding, ...]:
        out=[]; seen=set()
        for finding in findings:
            if finding.finding_id in seen:
                raise FindingFreezeError(f"duplicate finding_id: {finding.finding_id}")
            seen.add(finding.finding_id)
            if finding.production_status in self.EXCLUDED:
                continue
            if finding.production_status not in self.ELIGIBLE:
                raise FindingFreezeError(f"unsupported production_status: {finding.production_status}")
            if finding.qa_status != "PASS":
                raise FindingFreezeError(f"production-ready finding must have PASS QA: {finding.finding_id}")
            w=finding.approved_wording; v=finding.wording_versions
            out.append(FrozenFinding(
                finding.finding_id,finding.finding_type,finding.passport_id,finding.passport_version,
                finding.canonical_value,finding.confidence_code,finding.qa_status,finding.production_status,finding.publication_scope,
                w.get("agent"),w.get("seller"),w.get("public"),v.get("agent"),v.get("seller"),v.get("public"),
                finding.semantic_fingerprint,finding.evidence_reference_set_hash))
        return tuple(sorted(out,key=lambda x:(x.finding_type,x.finding_id)))
