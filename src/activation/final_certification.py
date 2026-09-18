from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

import yaml


EVIDENCE_PATHS = {
    "M9-001": "certification-evidence/m9-001/corpus-freeze-v1.0.json",
    "M9-002": "certification-evidence/m9-002/roster-population-v1.0.json",
    "M9-003": "certification-evidence/m9-003/identity-phase-spatial-binding-v1.0.json",
    "M9-004": "certification-evidence/m9-004/historical-intelligence-population-v1.0.json",
    "M9-005": "certification-evidence/m9-005/current-market-builder-v1.0.json",
    "M9-006": "certification-evidence/m9-006/evidence-passport-materialization-v1.0.json",
    "M9-007": "certification-evidence/m9-007/report-materialization-v1.0.json",
    "M9-008": "certification-evidence/m9-008/exception-quarantine-v1.0.json",
    "M9-009": "certification-evidence/m9-009/full-corpus-qa-v1.0.json",
    "M9-010": "certification-evidence/m9-010/controlled-publication-v1.0.json",
    "M9-011": "certification-evidence/m9-011/refresh-replay-v1.0.json",
}

ACCEPTED_STATUSES = {"PASS", "ACCEPTED"}


@dataclass(frozen=True)
class Milestone9CertificationResult:
    status: str
    verdict: str
    candidate_fingerprint: str
    certification_root_hash: str
    evidence_hashes: Mapping[str, str]
    check_statuses: Mapping[str, str]
    reason_codes: tuple[str, ...]


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def load_final_policy(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("final_certification_policy_id") != "STH-M9-012-FINAL-CERTIFICATION-v1.0":
        raise ValueError("unexpected M9-012 final certification policy id")
    if str(data.get("version")) != "1.0.0" or data.get("status") != "FROZEN":
        raise ValueError("M9-012 final certification policy must be FROZEN v1.0.0")
    return data


def load_evidence_set(root: str | Path = ".") -> tuple[dict[str, dict], dict[str, str]]:
    root = Path(root)
    evidence: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for ticket, rel in EVIDENCE_PATHS.items():
        path = root / rel
        raw = path.read_bytes()
        evidence[ticket] = json.loads(raw)
        hashes[ticket] = _hash_bytes(raw)
    return evidence, hashes


def evaluate_final_certification(
    *,
    evidence: Mapping[str, dict],
    evidence_hashes: Mapping[str, str],
    contract: Mapping[str, object],
    policy: Mapping[str, object],
    contract_hash: str,
    policy_hash: str,
) -> Milestone9CertificationResult:
    checks: dict[str, str] = {}
    reasons: list[str] = []

    required_tickets = tuple(policy["required_tickets"])
    for ticket in required_tickets:
        row = evidence.get(ticket)
        ok = bool(row and row.get("status") in ACCEPTED_STATUSES and ticket in evidence_hashes)
        checks[f"EVIDENCE_{ticket}"] = "PASS" if ok else "FAIL"
        if not ok:
            reasons.append(f"{ticket}_EVIDENCE_NOT_ACCEPTED")

    acceptance = contract["acceptance_model"]
    contract_ok = (
        acceptance["require_manifest_accounting_for_every_corpus_member"] is True
        and acceptance["require_zero_unclassified_exceptions"] is True
        and acceptance["require_zero_tier_leakage"] is True
        and acceptance["require_zero_unapproved_publications"] is True
        and acceptance["require_zero_source_lineage_gaps_for_published_records"] is True
        and acceptance["require_deterministic_replay"] is True
        and acceptance["require_refresh_replay_pass"] is True
        and acceptance["require_controlled_rollback_pass"] is True
        and acceptance["require_full_corpus_certification"] is True
        and acceptance["allow_waivers"] is False
        and acceptance["allow_conditional_go"] is False
    )
    checks["LOCKED_ACCEPTANCE_MODEL"] = "PASS" if contract_ok else "FAIL"
    if not contract_ok:
        reasons.append("LOCKED_ACCEPTANCE_MODEL_WEAKENED")

    qa = evidence.get("M9-009", {})
    qa_defects = dict(qa.get("defects") or {})
    hard_zero_codes = tuple(policy["hard_zero_m9_009_defects"])
    for code in hard_zero_codes:
        ok = int(qa_defects.get(code, -1)) == 0
        checks[f"HARD_ZERO_{code}"] = "PASS" if ok else "FAIL"
        if not ok:
            reasons.append(f"HARD_ZERO_{code}_NONZERO")

    qa_corpus = dict(qa.get("corpus") or {})
    corpus_ok = (
        int(qa_corpus.get("members", -1)) == int(policy["expected_corpus_members"])
        and int(qa_corpus.get("report_variants", -1)) == int(policy["expected_report_variants"])
        and int(qa_corpus.get("production_findings", -1)) == int(policy["expected_production_findings"])
        and int(qa_corpus.get("publication_decisions", -1)) == int(policy["expected_publication_decisions"])
    )
    checks["FULL_CORPUS_ACCOUNTING"] = "PASS" if corpus_ok else "FAIL"
    if not corpus_ok:
        reasons.append("FULL_CORPUS_ACCOUNTING_MISMATCH")

    m9_010 = evidence.get("M9-010", {})
    rollout = dict(m9_010.get("rollout") or {})
    controls_010 = dict(m9_010.get("controls") or {})
    publication_ok = (
        rollout.get("stage_order") == ["COHORT_25", "COHORT_100", "COHORT_500", "REMAINING_FLEET"]
        and rollout.get("allowed_tiers") == ["AGENT", "SELLER", "PUBLIC"]
        and rollout.get("manual_default") is True
        and rollout.get("unrestricted_fleet_publication") is False
        and int(m9_010.get("waivers", -1)) == 0
        and all(controls_010.get(k) is True for k in (
            "exact_cohort_membership",
            "prior_cohort_exclusion",
            "missing_tier_fail_closed",
            "quarantined_content_blocked",
            "stale_current_content_blocked",
            "pointer_compare_and_swap",
            "rollback_baseline",
            "m9_009_prerequisite",
            "m7_rollout_policy_bound",
            "m7_manual_publication_policy_bound",
        ))
    )
    checks["CONTROLLED_PUBLICATION"] = "PASS" if publication_ok else "FAIL"
    if not publication_ok:
        reasons.append("CONTROLLED_PUBLICATION_NOT_CERTIFIABLE")

    m9_011 = evidence.get("M9-011", {})
    controls_011 = dict(m9_011.get("controls") or {})
    replay_ok = (
        int(m9_011.get("waivers", -1)) == 0
        and all(controls_011.get(k) is True for k in (
            "unimpacted_fingerprint_stability",
            "governed_impacted_change_only",
            "isolated_failures",
            "deterministic_replay",
            "exact_pointer_rollback",
            "m2_019_bound",
            "m3_026_bound",
            "m7_023_bound",
            "m9_010_bound",
        ))
        and dict(m9_011.get("github_actions") or {}).get("repaired_m9_activation_ci", {}).get("conclusion") == "success"
        and dict(m9_011.get("github_actions") or {}).get("repaired_m9_architecture_boundary_validation", {}).get("conclusion") == "success"
    )
    checks["REFRESH_REGEN_ROLLBACK_REPLAY"] = "PASS" if replay_ok else "FAIL"
    if not replay_ok:
        reasons.append("REFRESH_REGEN_ROLLBACK_REPLAY_NOT_CERTIFIABLE")

    waivers = 0
    for ticket in ("M9-008", "M9-009", "M9-010", "M9-011"):
        row = evidence.get(ticket, {})
        if ticket == "M9-009":
            waivers += int(dict(row.get("defects") or {}).get("waivers", 0))
        else:
            waivers += int(row.get("waivers", 0))
    checks["ZERO_WAIVERS"] = "PASS" if waivers == 0 else "FAIL"
    if waivers:
        reasons.append("WAIVERS_PRESENT")

    candidate_payload = {
        "contract_hash": contract_hash,
        "evidence_hashes": {k: evidence_hashes[k] for k in sorted(required_tickets)},
    }
    candidate_fingerprint = _canonical_hash(candidate_payload)

    failures = [k for k, v in checks.items() if v != "PASS"]
    if failures:
        status, verdict = "FAIL", "NO_GO"
    else:
        status, verdict = "PASS", "GO"

    root_payload = {
        "candidate_fingerprint": candidate_fingerprint,
        "contract_hash": contract_hash,
        "policy_hash": policy_hash,
        "policy_version": policy["version"],
        "status": status,
        "verdict": verdict,
        "check_statuses": dict(sorted(checks.items())),
        "reason_codes": sorted(set(reasons)),
        "evidence_hashes": {k: evidence_hashes[k] for k in sorted(required_tickets)},
    }
    root_hash = _canonical_hash(root_payload)

    return Milestone9CertificationResult(
        status=status,
        verdict=verdict,
        candidate_fingerprint=candidate_fingerprint,
        certification_root_hash=root_hash,
        evidence_hashes=dict(sorted(evidence_hashes.items())),
        check_statuses=dict(sorted(checks.items())),
        reason_codes=tuple(sorted(set(reasons))),
    )


def run_repository_final_certification(root: str | Path = ".") -> Milestone9CertificationResult:
    root = Path(root)
    policy_path = root / "registries/activation/m9-012-final-certification-v1.0.yaml"
    contract_path = root / "contracts/activation/STH-PRODUCTION-POPULATION-ACTIVATION-v1.0.yaml"
    policy = load_final_policy(policy_path)
    contract = yaml.safe_load(contract_path.read_text())
    evidence, evidence_hashes = load_evidence_set(root)
    return evaluate_final_certification(
        evidence=evidence,
        evidence_hashes=evidence_hashes,
        contract=contract,
        policy=policy,
        contract_hash=_hash_bytes(contract_path.read_bytes()),
        policy_hash=_hash_bytes(policy_path.read_bytes()),
    )
