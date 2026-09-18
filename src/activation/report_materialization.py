from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ReportMaterializationAudit:
    records: int
    properties: int
    agent_variants: int
    seller_variants: int
    public_variants: int
    unique_report_state_keys: int
    agent_displayed_findings: int
    seller_displayed_findings: int
    public_displayed_findings: int
    stale_current_competition_displayed: int
    new_analytical_intelligence_created: int
    monotonicity_violations: int
    partial_property_ids: tuple[str, ...]
    raw_sha256: str
    aggregate_fingerprint: str


def _load_jsonl(path: str | Path) -> list[dict]:
    records: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def validate_report_materialization(
    registry_path: str | Path,
    materialization_path: str | Path,
) -> ReportMaterializationAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("report_materialization_registry_id") != "STH-M9-007-AGENT-SELLER-PUBLIC-REPORTS-v1.0":
        raise ValueError("unexpected M9-007 registry id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-007 registry must be FROZEN v1.0.0")

    records = _load_jsonl(materialization_path)
    by_property: dict[str, dict[str, dict]] = {}
    report_keys: set[str] = set()
    fingerprints: list[str] = []

    allowed_tiers = {"AGENT", "SELLER", "PUBLIC"}
    agent_displayed = seller_displayed = public_displayed = 0
    stale_displayed = new_intel = 0
    partial_ids: set[str] = set()

    for record in records:
        property_id = record["canonical_property_id"]
        tier = record["output_tier"]
        if tier not in allowed_tiers:
            raise ValueError(f"{property_id}: unsupported report tier {tier}")

        if record["publication_state"] != "MATERIALIZED_NOT_PUBLISHED":
            raise ValueError(f"{property_id}/{tier}: publication state drift")
        if record["stale_current_competition_displayed"] is not False:
            stale_displayed += 1
        if record["new_analytical_intelligence_created"] is not False:
            new_intel += 1

        displayed = tuple(record["displayed_finding_keys"])
        if len(displayed) != record["displayed_finding_count"]:
            raise ValueError(f"{property_id}/{tier}: displayed finding count mismatch")
        if len(set(displayed)) != len(displayed):
            raise ValueError(f"{property_id}/{tier}: duplicate displayed finding key")

        canonical = dict(record)
        fingerprint = canonical.pop("report_materialization_fingerprint")
        encoded = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        expected_fingerprint = sha256(encoded).hexdigest()
        if fingerprint != expected_fingerprint:
            raise ValueError(f"{property_id}/{tier}: report materialization fingerprint mismatch")

        if record["report_state_key"] in report_keys:
            raise ValueError("duplicate report state key")
        report_keys.add(record["report_state_key"])
        fingerprints.append(fingerprint)

        by_property.setdefault(property_id, {})
        if tier in by_property[property_id]:
            raise ValueError(f"{property_id}: duplicate {tier} report variant")
        by_property[property_id][tier] = record

        if record["health_status"] == "PARTIAL":
            partial_ids.add(property_id)

        if tier == "AGENT":
            agent_displayed += len(displayed)
        elif tier == "SELLER":
            seller_displayed += len(displayed)
        else:
            public_displayed += len(displayed)

    monotonicity_violations = 0
    for property_id, variants in by_property.items():
        if set(variants) != allowed_tiers:
            raise ValueError(f"{property_id}: missing Agent/Seller/Public variant")
        agent = set(variants["AGENT"]["displayed_finding_keys"])
        seller = set(variants["SELLER"]["displayed_finding_keys"])
        public = set(variants["PUBLIC"]["displayed_finding_keys"])
        if not public <= seller or not seller <= agent:
            monotonicity_violations += 1

        passport_fingerprints = {variants[t]["passport_fingerprint"] for t in allowed_tiers}
        if len(passport_fingerprints) != 1:
            raise ValueError(f"{property_id}: cross-tier passport fingerprint mismatch")

        health_states = {variants[t]["health_status"] for t in allowed_tiers}
        if len(health_states) != 1:
            raise ValueError(f"{property_id}: cross-tier health-status mismatch")

    if stale_displayed:
        raise ValueError("stale current competition displayed in M9-007")
    if new_intel:
        raise ValueError("presentation materialization created analytical intelligence")
    if monotonicity_violations:
        raise ValueError("cross-tier monotonicity violation")

    raw_sha = sha256(Path(materialization_path).read_bytes()).hexdigest()
    aggregate = sha256(("\n".join(fingerprints) + "\n").encode("utf-8")).hexdigest()

    audit = ReportMaterializationAudit(
        records=len(records),
        properties=len(by_property),
        agent_variants=sum(1 for r in records if r["output_tier"] == "AGENT"),
        seller_variants=sum(1 for r in records if r["output_tier"] == "SELLER"),
        public_variants=sum(1 for r in records if r["output_tier"] == "PUBLIC"),
        unique_report_state_keys=len(report_keys),
        agent_displayed_findings=agent_displayed,
        seller_displayed_findings=seller_displayed,
        public_displayed_findings=public_displayed,
        stale_current_competition_displayed=stale_displayed,
        new_analytical_intelligence_created=new_intel,
        monotonicity_violations=monotonicity_violations,
        partial_property_ids=tuple(sorted(partial_ids)),
        raw_sha256=raw_sha,
        aggregate_fingerprint=aggregate,
    )

    pop = registry["population"]
    displayed = registry["displayed_findings"]
    isolation = registry["tier_isolation"]
    artifact = registry["artifact"]

    checks = (
        ("records", pop["total_variants"], audit.records),
        ("properties", pop["properties"], audit.properties),
        ("agent_variants", pop["agent_variants"], audit.agent_variants),
        ("seller_variants", pop["seller_variants"], audit.seller_variants),
        ("public_variants", pop["public_variants"], audit.public_variants),
        ("unique_report_state_keys", pop["unique_report_state_keys"], audit.unique_report_state_keys),
        ("agent_displayed_findings", displayed["agent_total"], audit.agent_displayed_findings),
        ("seller_displayed_findings", displayed["seller_total"], audit.seller_displayed_findings),
        ("public_displayed_findings", displayed["public_total"], audit.public_displayed_findings),
        ("monotonicity_violations", isolation["monotonicity_violations"], audit.monotonicity_violations),
    )
    for name, expected, actual in checks:
        if expected != actual:
            raise ValueError(f"M9-007 mismatch for {name}: expected={expected}, actual={actual}")

    if artifact["raw_sha256"] != audit.raw_sha256:
        raise ValueError("M9-007 materialization SHA-256 mismatch")
    if artifact["aggregate_report_materialization_fingerprint"] != audit.aggregate_fingerprint:
        raise ValueError("M9-007 aggregate fingerprint mismatch")

    partial = registry["partial_property"]["canonical_property_id"]
    if audit.partial_property_ids != (partial,):
        raise ValueError("M9-007 partial property set mismatch")

    governance = registry["governance"]
    required_true = (
        "only_tier_eligible_findings_displayed",
        "stale_current_competition_suppressed",
        "agent_only_not_in_seller_or_public",
        "seller_only_not_in_public",
        "limitations_and_health_preserved",
        "passport_fingerprint_preserved",
        "report_state_key_preserved",
        "presentation_layer_recomputation_prohibited",
        "new_intelligence_prohibited",
        "raw_source_lookup_from_renderer_prohibited",
        "publication_prohibited_in_m9_007",
    )
    if any(governance.get(key) is not True for key in required_true):
        raise ValueError("M9-007 governance weakened")

    publication = registry["publication_state"]
    if publication["physical_delivery_activated"] is not False:
        raise ValueError("physical delivery activated during M9-007")
    if publication["public_delivery_activated"] is not False:
        raise ValueError("public delivery activated during M9-007")

    return audit
