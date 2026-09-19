from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.community_temporal_state.patterns import GovernedPatternCandidate, validate_candidate_replay
from src.community_temporal_state.scenario_governance import (
    ScenarioContract,
    validate_scenario_contract_replay,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_certified_baseline_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006B":
        raise ValueError("M13-006B certified baseline registry must be FROZEN")
    if data.get("certified_baseline_registry_id") != "STH-M13-006B-CERTIFIED-BASELINE-v1.0":
        raise ValueError("unexpected M13-006B certified baseline registry id")
    return data


@dataclass(frozen=True)
class PatternApplicabilityRule:
    rule_id: str
    pattern_domain: str
    required_fact_keys: tuple[str, ...]
    required_assumption_keys: tuple[str, ...]
    fact_equals: tuple[tuple[str, object], ...]
    assumption_equals: tuple[tuple[str, object], ...]
    rule_fingerprint: str


@dataclass(frozen=True)
class PatternApplicability:
    pattern_id: str
    pattern_fingerprint: str
    pattern_domain: str
    pattern_statement: str
    state: str
    reason_codes: tuple[str, ...]
    matched_fact_keys: tuple[str, ...]
    matched_assumption_keys: tuple[str, ...]
    source_ledger_fingerprint: str
    limitations: tuple[str, ...]
    applicability_fingerprint: str


@dataclass(frozen=True)
class CertifiedScenarioBaseline:
    scenario_id: str
    scenario_contract_fingerprint: str
    community_id: str
    subject_id: str
    baseline_snapshot_id: str
    baseline_fingerprint: str
    facts: tuple[tuple[str, object], ...]
    fact_source_fingerprints: tuple[str, ...]
    assumptions: tuple[tuple[str, object], ...]
    pattern_applicability: tuple[PatternApplicability, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    context_fingerprint: str


def make_pattern_applicability_rule(
    *,
    rule_id: str,
    pattern_domain: str,
    required_fact_keys: Sequence[str] = (),
    required_assumption_keys: Sequence[str] = (),
    fact_equals: Mapping[str, object] | None = None,
    assumption_equals: Mapping[str, object] | None = None,
) -> PatternApplicabilityRule:
    if not rule_id.strip() or not pattern_domain.strip():
        raise ValueError("rule id and pattern domain required")
    rf = tuple(sorted(set(x.strip() for x in required_fact_keys if x.strip())))
    ra = tuple(sorted(set(x.strip() for x in required_assumption_keys if x.strip())))
    fe = tuple(sorted((str(k), v) for k, v in (fact_equals or {}).items()))
    ae = tuple(sorted((str(k), v) for k, v in (assumption_equals or {}).items()))
    payload = {
        "rule_id": rule_id,
        "pattern_domain": pattern_domain,
        "required_fact_keys": rf,
        "required_assumption_keys": ra,
        "fact_equals": fe,
        "assumption_equals": ae,
    }
    return PatternApplicabilityRule(**payload, rule_fingerprint=_hash(payload))


def _reconcile_contract(
    contract: ScenarioContract,
    *,
    baseline_snapshot_id: str,
    baseline_status: str,
    baseline_fingerprint: str,
    baseline_facts: Mapping[str, object],
    baseline_fact_source_fingerprints: Mapping[str, str],
) -> None:
    if contract.state != "READY":
        raise ValueError("M13-006B requires READY scenario contract")
    if not validate_scenario_contract_replay(contract):
        raise ValueError("scenario contract replay failed")
    if baseline_status != "CERTIFIED":
        raise ValueError("certified baseline required")
    if contract.baseline_snapshot_id != baseline_snapshot_id:
        raise ValueError("baseline snapshot identity mismatch")
    _validate_fp(baseline_fingerprint, "baseline fingerprint")
    if contract.baseline_fingerprint != baseline_fingerprint:
        raise ValueError("baseline fingerprint mismatch")
    for fact in contract.facts:
        if fact.key not in baseline_facts:
            raise ValueError(f"scenario fact missing from certified baseline: {fact.key}")
        if baseline_facts[fact.key] != fact.value:
            raise ValueError(f"scenario fact value mismatch: {fact.key}")
        source_fp = baseline_fact_source_fingerprints.get(fact.key)
        if source_fp is None:
            raise ValueError(f"scenario fact source lineage missing: {fact.key}")
        _validate_fp(source_fp, "baseline fact source fingerprint")
        if source_fp != fact.source_fingerprint:
            raise ValueError(f"scenario fact source lineage mismatch: {fact.key}")


def assess_pattern_applicability(
    *,
    pattern: GovernedPatternCandidate,
    rule: PatternApplicabilityRule | None,
    facts: Mapping[str, object],
    assumptions: Mapping[str, object],
    registry: Mapping[str, object],
) -> PatternApplicability:
    if pattern.state != "PROMOTED" or pattern.promotion_state != "PROMOTED":
        raise ValueError("M13-006B may use promoted patterns only")
    if not validate_candidate_replay(pattern):
        raise ValueError("pattern replay failed")
    _validate_fp(pattern.source_ledger_fingerprint, "pattern source ledger fingerprint")
    states = set(registry["applicability_states"])
    reasons: list[str] = []
    matched_facts: list[str] = []
    matched_assumptions: list[str] = []

    if rule is None:
        state = "UNKNOWN"
        reasons.append("NO_GOVERNED_APPLICABILITY_RULE")
    elif rule.pattern_domain != pattern.domain:
        state = "NOT_APPLICABLE"
        reasons.append("PATTERN_DOMAIN_RULE_MISMATCH")
    else:
        missing_facts = [k for k in rule.required_fact_keys if k not in facts]
        missing_assumptions = [k for k in rule.required_assumption_keys if k not in assumptions]
        if missing_facts or missing_assumptions:
            state = "UNKNOWN"
            reasons.extend(f"MISSING_FACT:{k}" for k in missing_facts)
            reasons.extend(f"MISSING_ASSUMPTION:{k}" for k in missing_assumptions)
        else:
            mismatches = []
            for key, expected in rule.fact_equals:
                if key not in facts:
                    reasons.append(f"MISSING_FACT:{key}")
                    state = "UNKNOWN"
                    break
                if facts[key] != expected:
                    mismatches.append(f"FACT_VALUE_MISMATCH:{key}")
                else:
                    matched_facts.append(key)
            else:
                for key, expected in rule.assumption_equals:
                    if key not in assumptions:
                        reasons.append(f"MISSING_ASSUMPTION:{key}")
                        state = "UNKNOWN"
                        break
                    if assumptions[key] != expected:
                        mismatches.append(f"ASSUMPTION_VALUE_MISMATCH:{key}")
                    else:
                        matched_assumptions.append(key)
                else:
                    if mismatches:
                        state = "NOT_APPLICABLE"
                        reasons.extend(mismatches)
                    else:
                        state = "APPLICABLE"
                        matched_facts.extend(rule.required_fact_keys)
                        matched_assumptions.extend(rule.required_assumption_keys)
                        reasons.append("GOVERNED_RULE_SATISFIED")

    if state not in states:
        raise ValueError("invalid applicability state")
    payload = {
        "pattern_id": pattern.pattern_id,
        "pattern_fingerprint": pattern.candidate_fingerprint,
        "pattern_domain": pattern.domain,
        "pattern_statement": pattern.statement,
        "state": state,
        "reason_codes": tuple(sorted(set(reasons))),
        "matched_fact_keys": tuple(sorted(set(matched_facts))),
        "matched_assumption_keys": tuple(sorted(set(matched_assumptions))),
        "source_ledger_fingerprint": pattern.source_ledger_fingerprint,
        "limitations": tuple(pattern.limitations),
    }
    return PatternApplicability(**payload, applicability_fingerprint=_hash(payload))


def assemble_certified_scenario_baseline(
    *,
    scenario_contract: ScenarioContract,
    baseline_snapshot_id: str,
    baseline_status: str,
    baseline_fingerprint: str,
    baseline_community_id: str,
    baseline_subject_id: str,
    baseline_facts: Mapping[str, object],
    baseline_fact_source_fingerprints: Mapping[str, str],
    promoted_patterns: Sequence[GovernedPatternCandidate],
    applicability_rules: Sequence[PatternApplicabilityRule],
    registry: Mapping[str, object],
    unknowns: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> CertifiedScenarioBaseline:
    _reconcile_contract(
        scenario_contract,
        baseline_snapshot_id=baseline_snapshot_id,
        baseline_status=baseline_status,
        baseline_fingerprint=baseline_fingerprint,
        baseline_facts=baseline_facts,
        baseline_fact_source_fingerprints=baseline_fact_source_fingerprints,
    )
    if baseline_community_id != scenario_contract.community_id:
        raise ValueError("community identity mismatch")
    if baseline_subject_id != scenario_contract.subject_id:
        raise ValueError("subject identity mismatch")

    rules_by_domain: dict[str, PatternApplicabilityRule] = {}
    for rule in applicability_rules:
        if rule.pattern_domain in rules_by_domain:
            raise ValueError("multiple applicability rules for same pattern domain prohibited")
        rules_by_domain[rule.pattern_domain] = rule

    facts = dict(baseline_facts)
    assumptions = {x.key: x.value for x in scenario_contract.assumptions}
    applicability = tuple(sorted(
        (
            assess_pattern_applicability(
                pattern=pattern,
                rule=rules_by_domain.get(pattern.domain),
                facts=facts,
                assumptions=assumptions,
                registry=registry,
            )
            for pattern in promoted_patterns
        ),
        key=lambda x: x.pattern_id,
    ))
    if len({x.pattern_id for x in applicability}) != len(applicability):
        raise ValueError("duplicate promoted pattern ids prohibited")

    fact_sources = tuple(sorted(set(baseline_fact_source_fingerprints.values())))
    for fp in fact_sources:
        _validate_fp(fp, "baseline fact source fingerprint")

    pattern_limitations = {item for x in applicability for item in x.limitations if item}
    unknown_items = set(x.strip() for x in unknowns if x.strip())
    unknown_items.update(
        f"{x.pattern_id}:{reason}"
        for x in applicability
        if x.state == "UNKNOWN"
        for reason in x.reason_codes
    )
    limitation_items = set(x.strip() for x in limitations if x.strip()) | pattern_limitations

    payload = {
        "scenario_id": scenario_contract.scenario_id,
        "scenario_contract_fingerprint": scenario_contract.contract_fingerprint,
        "community_id": scenario_contract.community_id,
        "subject_id": scenario_contract.subject_id,
        "baseline_snapshot_id": baseline_snapshot_id,
        "baseline_fingerprint": baseline_fingerprint,
        "facts": tuple(sorted((str(k), v) for k, v in baseline_facts.items())),
        "fact_source_fingerprints": fact_sources,
        "assumptions": tuple(sorted((x.key, x.value) for x in scenario_contract.assumptions)),
        "pattern_applicability": tuple(asdict(x) for x in applicability),
        "unknowns": tuple(sorted(unknown_items)),
        "limitations": tuple(sorted(limitation_items)),
    }
    return CertifiedScenarioBaseline(
        scenario_id=payload["scenario_id"],
        scenario_contract_fingerprint=payload["scenario_contract_fingerprint"],
        community_id=payload["community_id"],
        subject_id=payload["subject_id"],
        baseline_snapshot_id=payload["baseline_snapshot_id"],
        baseline_fingerprint=payload["baseline_fingerprint"],
        facts=payload["facts"],
        fact_source_fingerprints=fact_sources,
        assumptions=payload["assumptions"],
        pattern_applicability=applicability,
        unknowns=payload["unknowns"],
        limitations=payload["limitations"],
        context_fingerprint=_hash(payload),
    )


def validate_certified_scenario_baseline_replay(
    context: CertifiedScenarioBaseline,
    *,
    scenario_contract: ScenarioContract,
    baseline_status: str,
    baseline_community_id: str,
    baseline_subject_id: str,
    baseline_facts: Mapping[str, object],
    baseline_fact_source_fingerprints: Mapping[str, str],
    promoted_patterns: Sequence[GovernedPatternCandidate],
    applicability_rules: Sequence[PatternApplicabilityRule],
    registry: Mapping[str, object],
) -> bool:
    replay = assemble_certified_scenario_baseline(
        scenario_contract=scenario_contract,
        baseline_snapshot_id=context.baseline_snapshot_id,
        baseline_status=baseline_status,
        baseline_fingerprint=context.baseline_fingerprint,
        baseline_community_id=baseline_community_id,
        baseline_subject_id=baseline_subject_id,
        baseline_facts=baseline_facts,
        baseline_fact_source_fingerprints=baseline_fact_source_fingerprints,
        promoted_patterns=promoted_patterns,
        applicability_rules=applicability_rules,
        registry=registry,
        unknowns=tuple(
            x for x in context.unknowns
            if not any(x.startswith(f"{p.pattern_id}:") for p in context.pattern_applicability)
        ),
        limitations=tuple(
            x for x in context.limitations
            if not any(x in p.limitations for p in context.pattern_applicability)
        ),
    )
    return replay == context
