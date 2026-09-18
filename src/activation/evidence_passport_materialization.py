from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
import json
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EvidenceMaterializationAudit:
    passports: int
    findings: int
    eligibility_rows: int
    internal_eligible: int
    agent_eligible: int
    seller_eligible: int
    public_eligible: int
    stale_current_noninternal_eligible: int
    partial_passports: tuple[str, ...]


def _rows(path: str | Path) -> list[dict[str, str]]:
    raw = Path(path).read_bytes()
    return list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))


def _sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def validate_materialization(
    registry_path: str | Path,
    passport_summary_path: str | Path,
    findings_path: str | Path,
    eligibility_path: str | Path,
    policy_path: str | Path,
) -> EvidenceMaterializationAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("evidence_materialization_registry_id") != "STH-M9-006-EVIDENCE-PASSPORT-FINDINGS-v1.0":
        raise ValueError("unexpected M9-006 registry id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-006 registry must be FROZEN v1.0.0")

    passports = _rows(passport_summary_path)
    findings = _rows(findings_path)
    eligibility = _rows(eligibility_path)
    policy = _rows(policy_path)

    if len({r["canonical_property_id"] for r in passports}) != len(passports):
        raise ValueError("duplicate passport property")
    if len(passports) != registry["passport_population"]["total"]:
        raise ValueError("passport population mismatch")

    policy_keys = {r["finding_key"] for r in policy}
    if len(policy_keys) != registry["adopted_governance"]["finding_policy_registry"]["finding_families"]:
        raise ValueError("finding policy family count mismatch")

    required_finding_fields = (
        "finding_key","direct_artifact_sha256","source_row_fingerprint",
        "lineage_artifact_ids","calculation_version","policy_version",
        "allowed_wording_template","required_qualifier","prohibited_interpretations",
        "allowed_tiers","finding_fingerprint",
    )
    for r in findings:
        for field in required_finding_fields:
            if not str(r.get(field, "")).strip():
                raise ValueError(f"finding missing governed field: {field}")
        if r["finding_key"] not in policy_keys:
            raise ValueError("unsupported finding family")
        if r["policy_version"] != registry["findings"]["policy_version"]:
            raise ValueError("finding policy version drift")

    if len(eligibility) != len(findings) * 4:
        raise ValueError("tier eligibility must contain four decisions per finding")

    eligible_counts = {}
    for tier in ("INTERNAL","AGENT","SELLER","PUBLIC"):
        eligible_counts[tier] = sum(
            1 for r in eligibility if r["output_tier"] == tier and r["eligible"] == "YES"
        )

    stale_current_noninternal = sum(
        1 for r in eligibility
        if r["finding_key"] == "competition.current"
        and r["output_tier"] in {"AGENT","SELLER","PUBLIC"}
        and r["eligible"] == "YES"
    )
    if stale_current_noninternal:
        raise ValueError("stale current competition leaked outside INTERNAL")

    partial = tuple(sorted(
        r["canonical_property_id"] for r in passports if r["health_status"] == "PARTIAL"
    ))

    audit = EvidenceMaterializationAudit(
        passports=len(passports),
        findings=len(findings),
        eligibility_rows=len(eligibility),
        internal_eligible=eligible_counts["INTERNAL"],
        agent_eligible=eligible_counts["AGENT"],
        seller_eligible=eligible_counts["SELLER"],
        public_eligible=eligible_counts["PUBLIC"],
        stale_current_noninternal_eligible=stale_current_noninternal,
        partial_passports=partial,
    )

    p = registry["passport_population"]
    f = registry["findings"]
    e = registry["publication_eligibility"]
    checks = (
        ("passports", p["total"], audit.passports),
        ("findings", f["total"], audit.findings),
        ("eligibility_rows", e["decision_rows"], audit.eligibility_rows),
        ("internal", e["internal_eligible"], audit.internal_eligible),
        ("agent", e["agent_eligible"], audit.agent_eligible),
        ("seller", e["seller_eligible"], audit.seller_eligible),
        ("public", e["public_eligible"], audit.public_eligible),
    )
    for name, expected, actual in checks:
        if expected != actual:
            raise ValueError(f"M9-006 mismatch for {name}: expected={expected}, actual={actual}")

    if tuple(p["partial_property_ids"]) != audit.partial_passports:
        raise ValueError("partial passport set mismatch")

    adopted = registry["adopted_governance"]
    hash_checks = (
        (passport_summary_path, adopted["passport_summary"]["raw_sha256"]),
        (findings_path, adopted["production_finding_candidates"]["raw_sha256"]),
        (eligibility_path, adopted["publication_eligibility"]["raw_sha256"]),
        (policy_path, adopted["finding_policy_registry"]["raw_sha256"]),
    )
    for path, expected in hash_checks:
        if _sha(path) != expected:
            raise ValueError(f"M9-006 adopted artifact SHA-256 mismatch: {Path(path).name}")

    builder = registry["non_promoted_governed_context"]["m9_005_builder_context"]
    if builder["property_finding_created"] is not False:
        raise ValueError("builder context promoted without finding policy")
    if builder["reason"] != "NO_FINDING_POLICY_2_PROPERTY_FINDING_FAMILY":
        raise ValueError("builder non-promotion reason drift")

    governance = registry["governance"]
    must_true = (
        "preserve_allowed_wording","preserve_required_qualifiers",
        "preserve_prohibited_interpretations","preserve_confidence_and_qa",
        "preserve_freshness","preserve_tier_eligibility",
        "preserve_limitations","preserve_lineage",
        "renderer_tier_inference_prohibited","report_rendering_prohibited",
        "publication_prohibited",
    )
    if any(governance.get(k) is not True for k in must_true):
        raise ValueError("M9-006 governance weakened")
    if governance.get("create_new_analytical_facts") is not False or governance.get("invent_missing_findings") is not False:
        raise ValueError("M9-006 analytical creation prohibition weakened")

    return audit
