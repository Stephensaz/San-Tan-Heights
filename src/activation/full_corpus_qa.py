from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FullCorpusQAAudit:
    corpus_members: int
    roster_members: int
    binding_members: int
    historical_members: int
    current_context_members: int
    passport_members: int
    report_properties: int
    report_variants: int
    production_findings: int
    publication_decisions: int
    partial_property_ids: tuple[str, ...]
    unclassified_exceptions: int
    tier_leakage_violations: int
    unauthorized_publications: int
    lineage_gaps: int
    coverage_gaps: int
    waivers: int
    qa_fingerprint: str


REGISTRY_PATHS = {
    "corpus": "registries/activation/production-corpus-freeze-v1.0.yaml",
    "roster": "registries/activation/m9-002-canonical-roster-v1.0.yaml",
    "binding": "registries/activation/m9-003-identity-phase-spatial-v1.0.yaml",
    "history": "registries/activation/m9-004-historical-intelligence-v1.0.yaml",
    "current": "registries/activation/m9-005-current-market-builder-v1.0.yaml",
    "evidence": "registries/activation/m9-006-evidence-passport-materialization-v1.0.yaml",
    "reports": "registries/activation/m9-007-report-materialization-v1.0.yaml",
    "exception_policy": "registries/activation/m9-008-exception-quarantine-v1.0.yaml",
}

EXCEPTION_EVIDENCE_PATH = "certification-evidence/m9-008/exception-quarantine-v1.0.json"


def _canonical_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def load_full_corpus_inputs(root: str | Path = ".") -> tuple[dict[str, dict], dict]:
    root = Path(root)
    registries: dict[str, dict] = {}
    for name, rel in REGISTRY_PATHS.items():
        registries[name] = yaml.safe_load((root / rel).read_text())
    exception_evidence = json.loads((root / EXCEPTION_EVIDENCE_PATH).read_text())
    return registries, exception_evidence


def audit_full_corpus_qa(registries: dict[str, dict], exception_evidence: dict) -> FullCorpusQAAudit:
    required = set(REGISTRY_PATHS)
    missing = sorted(required - set(registries))
    if missing:
        raise ValueError(f"missing M9 registries: {', '.join(missing)}")

    corpus = registries["corpus"]
    roster = registries["roster"]
    binding = registries["binding"]
    history = registries["history"]
    current = registries["current"]
    evidence = registries["evidence"]
    reports = registries["reports"]
    exception_policy = registries["exception_policy"]

    frozen_states = {
        "corpus": corpus.get("status"),
        "roster": roster.get("status"),
        "binding": binding.get("status"),
        "history": history.get("status"),
        "current": current.get("status"),
        "evidence": evidence.get("status"),
        "reports": reports.get("status"),
        "exception_policy": exception_policy.get("status"),
    }
    not_frozen = sorted(name for name, status in frozen_states.items() if status != "FROZEN")
    if not_frozen:
        raise ValueError(f"M9 registry not frozen: {', '.join(not_frozen)}")

    corpus_members = int(corpus["membership"]["declared_total"])
    if corpus_members <= 0:
        raise ValueError("invalid frozen corpus member count")

    if corpus["admission"]["admitted"] != corpus_members:
        raise ValueError("M9-001 admitted count does not equal frozen corpus")
    if corpus["admission"]["quarantined"] != 0 or corpus["admission"]["excluded_with_governed_reason"] != 0:
        raise ValueError("M9-001 corpus membership contains unresolved admission accounting")

    identity_hashes = (
        corpus["membership"]["canonical_property_ids_sha256"],
        roster["population"]["canonical_property_ids_sha256"],
    )
    parcel_hashes = (
        corpus["membership"]["county_parcelids_sha256"],
        roster["population"]["county_parcelids_sha256"],
    )
    pair_hashes = (
        corpus["membership"]["canonical_property_id_to_parcelid_pairs_sha256"],
        roster["population"]["canonical_property_id_to_parcelid_pairs_sha256"],
    )
    if len(set(identity_hashes)) != 1 or len(set(parcel_hashes)) != 1 or len(set(pair_hashes)) != 1:
        raise ValueError("M9-001/M9-002 membership fingerprint drift")

    roster_members = int(roster["population"]["row_count"])
    binding_members = int(binding["population"]["row_count"])
    historical_members = int(history["population"]["corpus_members"])
    current_context_members = int(current["property_population"]["current_context_available"]) + int(
        current["property_population"]["current_context_unavailable"]
    )
    passport_members = int(evidence["passport_population"]["total"])
    report_properties = int(reports["population"]["properties"])

    layer_counts = {
        "roster": roster_members,
        "binding": binding_members,
        "history": historical_members,
        "current": current_context_members,
        "passport": passport_members,
        "reports": report_properties,
    }
    bad_counts = {name: value for name, value in layer_counts.items() if value != corpus_members}
    if bad_counts:
        raise ValueError(f"full-corpus coverage drift: {bad_counts}")

    if roster["population"]["additions_vs_m9_001"] or roster["population"]["omissions_vs_m9_001"]:
        raise ValueError("M9-002 roster membership drift")
    if binding["population"]["additions_vs_m9_002"] or binding["population"]["omissions_vs_m9_002"]:
        raise ValueError("M9-003 binding membership drift")
    if binding["population"]["parcelid_mismatches_vs_m9_002"]:
        raise ValueError("M9-003 ParcelID mismatch")

    history_population = history["population"]
    if history_population["history_available_properties"] + history_population["no_governed_history_properties"] != corpus_members:
        raise ValueError("M9-004 property history coverage does not reconcile")
    source_rows = history["inputs"]["armls_listing_episode_foundation"]["rows"]
    if history_population["canonical_listing_records_attached"] + history_population["unresolved_listing_records_non_promoted"] != source_rows:
        raise ValueError("M9-004 listing-record accounting does not reconcile")
    legacy = history["legacy_episode_identity"]
    if legacy["bound_to_canonical_property"] + legacy["unresolved_non_promoted"] != legacy["total_episode_ids"]:
        raise ValueError("M9-004 legacy episode accounting does not reconcile")
    if history["governance"]["unresolved_history_non_promoted"] is not True:
        raise ValueError("M9-004 unresolved history promotion guard weakened")

    binding_partial = tuple(sorted(binding["spatial_binding"]["unresolved_property_ids"]))
    current_unavailable = tuple(sorted(current["property_population"]["unavailable_property_ids"]))
    passport_partial = tuple(sorted(evidence["passport_population"]["partial_property_ids"]))
    report_partial = (reports["partial_property"]["canonical_property_id"],)
    if not (binding_partial == current_unavailable == passport_partial == report_partial):
        raise ValueError("partial/unavailable property lineage mismatch across M9-003/M9-005/M9-006/M9-007")

    if binding["spatial_binding"]["bound"] + binding["spatial_binding"]["partial_unresolved"] != corpus_members:
        raise ValueError("M9-003 spatial coverage does not reconcile")
    if evidence["passport_population"]["ready_with_limitations"] + evidence["passport_population"]["partial"] != corpus_members:
        raise ValueError("M9-006 Passport health coverage does not reconcile")

    production_findings = int(evidence["findings"]["total"])
    family_total = sum(int(v) for v in evidence["findings"]["families"].values())
    if family_total != production_findings:
        raise ValueError("M9-006 finding-family totals do not reconcile")
    publication_decisions = int(evidence["publication_eligibility"]["decision_rows"])
    if publication_decisions != production_findings * 4:
        raise ValueError("M9-006 publication decision coverage does not reconcile")

    report_variants = int(reports["population"]["total_variants"])
    if report_variants != corpus_members * int(reports["population"]["variants_per_property"]):
        raise ValueError("M9-007 report variant coverage does not reconcile")
    if reports["population"]["unique_report_state_keys"] != report_variants:
        raise ValueError("M9-007 report state key coverage gap")
    for tier in ("agent", "seller", "public"):
        if reports["population"][f"{tier}_variants"] != corpus_members:
            raise ValueError(f"M9-007 {tier} report coverage gap")

    expected_display = {
        "agent_total": evidence["publication_eligibility"]["agent_eligible"],
        "seller_total": evidence["publication_eligibility"]["seller_eligible"],
        "public_total": evidence["publication_eligibility"]["public_eligible"],
    }
    for key, expected in expected_display.items():
        if reports["displayed_findings"][key] != expected:
            raise ValueError(f"M9-006/M9-007 tier eligibility mismatch for {key}")

    tier_leakage_violations = int(reports["tier_isolation"]["monotonicity_violations"])
    tier_leakage_violations += int(reports["displayed_findings"]["eligibility_mismatches"])
    if tier_leakage_violations:
        raise ValueError("audience-tier leakage detected")

    if reports["displayed_findings"]["stale_current_competition_displayed"] != 0:
        raise ValueError("stale current competition displayed")
    if evidence["integrity"]["stale_current_noninternal_eligible"] != 0:
        raise ValueError("stale current competition eligible outside INTERNAL")
    if reports["displayed_findings"]["new_analytical_intelligence_created"] != 0:
        raise ValueError("M9-007 created new analytical intelligence")

    unauthorized_publications = int(bool(reports["publication_state"]["physical_delivery_activated"])) + int(
        bool(reports["publication_state"]["public_delivery_activated"])
    )
    if unauthorized_publications:
        raise ValueError("publication activated before M9-010")

    lineage_flags = [
        roster["lineage"]["every_row_has_m9_001_freeze_fingerprint"],
        evidence["findings"]["all_have_direct_artifact_sha256"],
        evidence["findings"]["all_have_source_row_fingerprint"],
        evidence["findings"]["all_have_lineage"],
        evidence["findings"]["all_have_model_or_calculation_version"],
        evidence["findings"]["all_have_policy_version"],
        reports["governance"]["passport_fingerprint_preserved"],
        reports["governance"]["report_state_key_preserved"],
    ]
    lineage_gaps = sum(1 for flag in lineage_flags if flag is not True)
    if lineage_gaps:
        raise ValueError("required lineage coverage gap")

    if exception_evidence.get("status") != "ACCEPTED":
        raise ValueError("M9-008 exception workflow not accepted")
    waivers = int(exception_evidence.get("waivers", 0))
    if waivers:
        raise ValueError("M9 activation waivers are prohibited")

    known_exception = exception_evidence["known_governed_exception"]
    policy_known = exception_policy["known_governed_exception"]
    if known_exception["canonical_property_id"] != report_partial[0]:
        raise ValueError("M9-008 known exception does not match partial property")
    if policy_known["canonical_property_id"] != report_partial[0] or policy_known["scope_key"] != known_exception["scope_key"]:
        raise ValueError("M9-008 policy/evidence known-exception mismatch")

    unclassified_exceptions = 0
    coverage_gaps = 0

    fingerprint_payload = {
        "corpus_members": corpus_members,
        "membership_identity_hash": identity_hashes[0],
        "membership_parcel_hash": parcel_hashes[0],
        "membership_pair_hash": pair_hashes[0],
        "binding_sha256": binding["artifact"]["raw_sha256"],
        "historical_population_sha256": history["artifacts"]["property_population"]["raw_sha256"],
        "current_context_sha256": current["artifacts"]["property_context"]["raw_sha256"],
        "evidence_materialization_fingerprint": evidence["materialization_fingerprint"],
        "report_materialization_fingerprint": reports["artifact"]["aggregate_report_materialization_fingerprint"],
        "production_findings": production_findings,
        "publication_decisions": publication_decisions,
        "report_variants": report_variants,
        "partial_property_ids": report_partial,
        "tier_leakage_violations": tier_leakage_violations,
        "unauthorized_publications": unauthorized_publications,
        "lineage_gaps": lineage_gaps,
        "unclassified_exceptions": unclassified_exceptions,
        "coverage_gaps": coverage_gaps,
        "waivers": waivers,
    }

    return FullCorpusQAAudit(
        corpus_members=corpus_members,
        roster_members=roster_members,
        binding_members=binding_members,
        historical_members=historical_members,
        current_context_members=current_context_members,
        passport_members=passport_members,
        report_properties=report_properties,
        report_variants=report_variants,
        production_findings=production_findings,
        publication_decisions=publication_decisions,
        partial_property_ids=report_partial,
        unclassified_exceptions=unclassified_exceptions,
        tier_leakage_violations=tier_leakage_violations,
        unauthorized_publications=unauthorized_publications,
        lineage_gaps=lineage_gaps,
        coverage_gaps=coverage_gaps,
        waivers=waivers,
        qa_fingerprint=_canonical_hash(fingerprint_payload),
    )


def run_repository_full_corpus_qa(root: str | Path = ".") -> FullCorpusQAAudit:
    registries, exception_evidence = load_full_corpus_inputs(root)
    return audit_full_corpus_qa(registries, exception_evidence)
