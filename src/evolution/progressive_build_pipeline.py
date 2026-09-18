from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml


def _hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class StageInput:
    stage_id: str
    checks: Mapping[str, bool]
    evidence: Mapping[str, str]


@dataclass(frozen=True)
class StageResult:
    stage_id: str
    order: int
    status: str
    evidence_fingerprint: str
    failed_checks: tuple[str, ...]


@dataclass(frozen=True)
class ProgressiveBuildResult:
    community_id: str
    stages: tuple[StageResult, ...]
    status: str
    candidate_fingerprint: str | None
    stopped_at: str | None


def load_pipeline_registry(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    if raw.get("pipeline_registry_id") != "STH-M10-004-PROGRESSIVE-BUILD-PIPELINE-v1.0":
        raise ValueError("unexpected M10-004 pipeline registry id")
    if str(raw.get("version")) != "1.0.0" or raw.get("status") != "FROZEN":
        raise ValueError("M10-004 pipeline registry must be frozen v1.0")
    stages = raw.get("stages")
    if not isinstance(stages, list) or len(stages) != 8:
        raise ValueError("M10-004 pipeline must define exactly eight stages")
    orders = [int(s["order"]) for s in stages]
    if orders != list(range(1, 9)):
        raise ValueError("M10-004 stage order must be contiguous 1..8")
    return raw


def _stage_map(registry: Mapping[str, object]) -> dict[str, dict]:
    return {str(x["id"]): dict(x) for x in registry["stages"]}


def _validate_stage_input(stage: StageInput) -> None:
    if not stage.checks:
        raise ValueError(f"{stage.stage_id}: checks required")
    if not stage.evidence:
        raise ValueError(f"{stage.stage_id}: evidence required")
    if any(not str(k).strip() for k in stage.checks):
        raise ValueError(f"{stage.stage_id}: blank check id")
    if any(not str(k).strip() or not str(v).strip() for k, v in stage.evidence.items()):
        raise ValueError(f"{stage.stage_id}: evidence keys/values must be nonblank")


def execute_progressive_pipeline(
    *,
    community_id: str,
    onboarding_bootstrap_fingerprint: str,
    stage_inputs: Mapping[str, StageInput],
    registry: Mapping[str, object],
    protected_tokens: tuple[str, ...] = ("SAN_TAN_HEIGHTS", "San Tan Heights", "Pinal", "ARMLS"),
) -> ProgressiveBuildResult:
    if not community_id.strip():
        raise ValueError("community_id required")
    if community_id == "SAN_TAN_HEIGHTS":
        raise ValueError("protected San Tan Heights identity cannot be used as a new-community pipeline target")
    if len(onboarding_bootstrap_fingerprint) != 64:
        raise ValueError("onboarding bootstrap fingerprint must be sha256")

    ordered = sorted(registry["stages"], key=lambda x: int(x["order"]))
    known = {str(x["id"]) for x in ordered}
    if set(stage_inputs) != known:
        missing = sorted(known - set(stage_inputs))
        extra = sorted(set(stage_inputs) - known)
        raise ValueError(f"stage input coverage mismatch: missing={missing}, extra={extra}")

    prior: dict[str, StageResult] = {}
    results: list[StageResult] = []

    for spec in ordered:
        stage_id = str(spec["id"])
        order = int(spec["order"])
        required = tuple(str(x) for x in spec.get("requires") or ())

        for dep in required:
            dep_result = prior.get(dep)
            if dep_result is None or dep_result.status != "PASS":
                return ProgressiveBuildResult(
                    community_id=community_id,
                    stages=tuple(results),
                    status="FAIL",
                    candidate_fingerprint=None,
                    stopped_at=stage_id,
                )

        supplied = stage_inputs[stage_id]
        if supplied.stage_id != stage_id:
            raise ValueError(f"stage identity mismatch for {stage_id}")
        _validate_stage_input(supplied)

        serialized = json.dumps(
            {"checks": dict(supplied.checks), "evidence": dict(supplied.evidence)},
            sort_keys=True,
        )
        leaked = tuple(token for token in protected_tokens if token and token in serialized)
        if leaked:
            raise ValueError(f"{stage_id}: protected default leakage detected: {leaked}")

        failed = tuple(sorted(k for k, passed in supplied.checks.items() if passed is not True))
        payload = {
            "community_id": community_id,
            "stage_id": stage_id,
            "order": order,
            "onboarding_bootstrap_fingerprint": onboarding_bootstrap_fingerprint,
            "required_predecessors": list(required),
            "checks": dict(sorted(supplied.checks.items())),
            "evidence": dict(sorted(supplied.evidence.items())),
            "failed_checks": list(failed),
        }
        result = StageResult(
            stage_id=stage_id,
            order=order,
            status="FAIL" if failed else "PASS",
            evidence_fingerprint=_hash(payload),
            failed_checks=failed,
        )
        results.append(result)
        prior[stage_id] = result

        if failed:
            return ProgressiveBuildResult(
                community_id=community_id,
                stages=tuple(results),
                status="FAIL",
                candidate_fingerprint=None,
                stopped_at=stage_id,
            )

    final_payload = {
        "community_id": community_id,
        "onboarding_bootstrap_fingerprint": onboarding_bootstrap_fingerprint,
        "stage_evidence": [
            {
                "stage_id": x.stage_id,
                "order": x.order,
                "status": x.status,
                "evidence_fingerprint": x.evidence_fingerprint,
            }
            for x in results
        ],
    }
    return ProgressiveBuildResult(
        community_id=community_id,
        stages=tuple(results),
        status="PASS",
        candidate_fingerprint=_hash(final_payload),
        stopped_at=None,
    )
