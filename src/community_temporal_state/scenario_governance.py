from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import yaml


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_scenario_governance_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006A":
        raise ValueError("M13-006A scenario governance registry must be FROZEN")
    if data.get("scenario_governance_registry_id") != "STH-M13-006A-SCENARIO-GOVERNANCE-v1.0":
        raise ValueError("unexpected M13-006A scenario governance registry id")
    return data


@dataclass(frozen=True)
class ScenarioFact:
    key: str
    value: object
    source_artifact_id: str
    source_fingerprint: str
    fact_fingerprint: str


@dataclass(frozen=True)
class ScenarioAssumption:
    key: str
    assumption_type: str
    value: object
    source: str
    limitation: str | None
    assumption_fingerprint: str


@dataclass(frozen=True)
class ScenarioContract:
    scenario_id: str
    contract_version: int
    community_id: str
    subject_id: str
    baseline_snapshot_id: str
    baseline_status: str
    baseline_fingerprint: str
    facts: tuple[ScenarioFact, ...]
    assumptions: tuple[ScenarioAssumption, ...]
    state: str
    supersedes_scenario_fingerprint: str | None
    policy_version: str
    contract_fingerprint: str


def make_scenario_fact(
    *,
    key: str,
    value: object,
    source_artifact_id: str,
    source_fingerprint: str,
) -> ScenarioFact:
    if not key.strip() or not source_artifact_id.strip():
        raise ValueError("fact key and source artifact id required")
    _validate_fp(source_fingerprint, "fact source fingerprint")
    payload = {
        "key": key,
        "value": value,
        "source_artifact_id": source_artifact_id,
        "source_fingerprint": source_fingerprint,
    }
    return ScenarioFact(**payload, fact_fingerprint=_hash(payload))


def _validate_assumption_value(assumption_type: str, value: object) -> None:
    if assumption_type == "MONEY":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("MONEY assumption must be non-negative numeric")
    elif assumption_type == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("INTEGER assumption must be integer")
    elif assumption_type == "NUMBER":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("NUMBER assumption must be numeric")
    elif assumption_type == "PERCENT":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 100:
            raise ValueError("PERCENT assumption must be between 0 and 100")
    elif assumption_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise ValueError("BOOLEAN assumption must be boolean")
    elif assumption_type in {"ENUM", "TEXT"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{assumption_type} assumption must be non-empty text")
    elif assumption_type == "DATE":
        if not isinstance(value, str):
            raise ValueError("DATE assumption must be ISO date text")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("DATE assumption must be ISO date text") from exc
    else:
        raise ValueError("unsupported assumption type")


def make_scenario_assumption(
    *,
    key: str,
    assumption_type: str,
    value: object,
    source: str,
    registry: Mapping[str, object],
    limitation: str | None = None,
) -> ScenarioAssumption:
    if not key.strip() or not source.strip():
        raise ValueError("assumption key and source required")
    allowed = set(registry["assumption_types"])
    if assumption_type not in allowed:
        raise ValueError("unsupported assumption type")
    _validate_assumption_value(assumption_type, value)
    payload = {
        "key": key,
        "assumption_type": assumption_type,
        "value": value,
        "source": source,
        "limitation": limitation,
    }
    return ScenarioAssumption(**payload, assumption_fingerprint=_hash(payload))


def build_scenario_contract(
    *,
    scenario_id: str,
    contract_version: int,
    community_id: str,
    subject_id: str,
    baseline_snapshot_id: str,
    baseline_status: str,
    baseline_fingerprint: str,
    facts: Sequence[ScenarioFact],
    assumptions: Sequence[ScenarioAssumption],
    policy_version: str,
    registry: Mapping[str, object],
    supersedes_scenario_fingerprint: str | None = None,
) -> ScenarioContract:
    if not all(x.strip() for x in (scenario_id, community_id, subject_id, baseline_snapshot_id, policy_version)):
        raise ValueError("scenario identity, subject, baseline and policy version required")
    if contract_version < 1:
        raise ValueError("contract version must be positive")
    if registry["policy"]["require_certified_baseline"] and baseline_status != "CERTIFIED":
        raise ValueError("certified baseline required")
    _validate_fp(baseline_fingerprint, "baseline fingerprint")
    if supersedes_scenario_fingerprint is not None:
        _validate_fp(supersedes_scenario_fingerprint, "superseded scenario fingerprint")

    fact_rows = tuple(sorted(facts, key=lambda x: x.key))
    assumption_rows = tuple(sorted(assumptions, key=lambda x: x.key))
    fact_keys = [x.key for x in fact_rows]
    assumption_keys = [x.key for x in assumption_rows]
    if len(set(fact_keys)) != len(fact_keys):
        raise ValueError("duplicate fact keys prohibited")
    if len(set(assumption_keys)) != len(assumption_keys):
        raise ValueError("duplicate assumption keys prohibited")
    if set(fact_keys).intersection(assumption_keys):
        raise ValueError("fact/assumption key collision prohibited")
    if registry["policy"]["require_at_least_one_assumption"] and not assumption_rows:
        raise ValueError("at least one explicit assumption required")

    payload = {
        "scenario_id": scenario_id,
        "contract_version": contract_version,
        "community_id": community_id,
        "subject_id": subject_id,
        "baseline_snapshot_id": baseline_snapshot_id,
        "baseline_status": baseline_status,
        "baseline_fingerprint": baseline_fingerprint,
        "facts": tuple(asdict(x) for x in fact_rows),
        "assumptions": tuple(asdict(x) for x in assumption_rows),
        "state": "DRAFT",
        "supersedes_scenario_fingerprint": supersedes_scenario_fingerprint,
        "policy_version": policy_version,
    }
    return ScenarioContract(
        scenario_id=scenario_id,
        contract_version=contract_version,
        community_id=community_id,
        subject_id=subject_id,
        baseline_snapshot_id=baseline_snapshot_id,
        baseline_status=baseline_status,
        baseline_fingerprint=baseline_fingerprint,
        facts=fact_rows,
        assumptions=assumption_rows,
        state="DRAFT",
        supersedes_scenario_fingerprint=supersedes_scenario_fingerprint,
        policy_version=policy_version,
        contract_fingerprint=_hash(payload),
    )


def ready_scenario_contract(contract: ScenarioContract) -> ScenarioContract:
    if contract.state != "DRAFT":
        raise ValueError("only DRAFT scenario contracts may transition to READY")
    payload = asdict(contract)
    payload.pop("contract_fingerprint")
    payload["state"] = "READY"
    return replace(contract, state="READY", contract_fingerprint=_hash(payload))


def validate_scenario_contract_replay(contract: ScenarioContract) -> bool:
    payload = asdict(contract)
    fingerprint = payload.pop("contract_fingerprint")
    return _hash(payload) == fingerprint


def assert_ready_contract_immutable(original: ScenarioContract, candidate: ScenarioContract) -> None:
    if original.state != "READY":
        raise ValueError("immutability check requires READY original")
    if original != candidate:
        raise ValueError("READY scenario contract is immutable; create a new version instead")
