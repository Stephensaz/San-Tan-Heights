from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Mapping, Sequence

import yaml

from src.community_temporal_state.delta import (
    CommunityDelta,
    FieldChange,
    validate_delta_replay,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _fp(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 fingerprint")
    return value


def load_refresh_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-003":
        raise ValueError("M13-003 refresh registry must be FROZEN")
    if data.get("refresh_registry_id") != "STH-M13-003-SELECTIVE-REFRESH-v1.0":
        raise ValueError("unexpected M13-003 refresh registry id")
    return data


@dataclass(frozen=True)
class CertifiedIntelligenceArtifact:
    artifact_id: str
    property_id: str
    intelligence_type: str
    dependency_domains: tuple[str, ...]
    value_fingerprint: str
    certification_state: str
    lineage_fingerprints: tuple[str, ...]
    engine_version: str
    ruleset_version: str
    artifact_version: int
    suppressed: bool
    artifact_fingerprint: str


@dataclass(frozen=True)
class RefreshDecision:
    artifact_id: str
    property_id: str
    disposition: str
    matched_domains: tuple[str, ...]
    triggering_change_fingerprints: tuple[str, ...]
    reason_codes: tuple[str, ...]
    prior_artifact_fingerprint: str
    decision_fingerprint: str


@dataclass(frozen=True)
class RefreshPlan:
    plan_id: str
    delta_fingerprint: str
    delta_before_snapshot_hash: str
    delta_after_snapshot_hash: str
    refresh_policy_version: str
    decisions: tuple[RefreshDecision, ...]
    targeted_artifact_ids: tuple[str, ...]
    no_impact_artifact_ids: tuple[str, ...]
    blocked_artifact_ids: tuple[str, ...]
    certification_state: str
    reproducible: bool
    plan_fingerprint: str


@dataclass(frozen=True)
class StagedIntelligenceArtifact:
    artifact_id: str
    prior_artifact_fingerprint: str
    property_id: str
    intelligence_type: str
    dependency_domains: tuple[str, ...]
    value_fingerprint: str
    lineage_fingerprints: tuple[str, ...]
    engine_version: str
    ruleset_version: str
    artifact_version: int
    suppressed: bool
    source_delta_fingerprint: str
    frozen_input_fingerprint: str
    stage_fingerprint: str


@dataclass(frozen=True)
class RefreshProof:
    artifact_id: str
    disposition: str
    action_taken: str
    reason_codes: tuple[str, ...]
    triggering_change_fingerprints: tuple[str, ...]
    before_artifact_fingerprint: str
    staged_artifact_fingerprint: str | None
    proof_fingerprint: str


@dataclass(frozen=True)
class RefreshExecution:
    execution_id: str
    plan_fingerprint: str
    delta_fingerprint: str
    status: str
    prior_artifacts: tuple[CertifiedIntelligenceArtifact, ...]
    staged_artifacts: tuple[StagedIntelligenceArtifact, ...]
    active_artifacts: tuple[CertifiedIntelligenceArtifact, ...]
    proofs: tuple[RefreshProof, ...]
    blocking_reasons: tuple[str, ...]
    execution_fingerprint: str


RefreshFunction = Callable[
    [CertifiedIntelligenceArtifact, tuple[FieldChange, ...], str, str, str],
    str,
]


def make_certified_intelligence_artifact(
    *,
    artifact_id: str,
    property_id: str,
    intelligence_type: str,
    dependency_domains: Sequence[str],
    value_fingerprint: str,
    lineage_fingerprints: Sequence[str],
    engine_version: str,
    ruleset_version: str,
    artifact_version: int = 1,
    suppressed: bool = False,
) -> CertifiedIntelligenceArtifact:
    if not artifact_id.strip() or not property_id.strip() or not intelligence_type.strip():
        raise ValueError("artifact identity fields required")
    _fp(value_fingerprint, "value_fingerprint")
    lineage = tuple(sorted(set(_fp(x, "lineage fingerprint") for x in lineage_fingerprints)))
    domains = tuple(sorted(set(str(x).strip() for x in dependency_domains if str(x).strip())))
    if not domains:
        raise ValueError("at least one dependency domain required")
    if not engine_version.strip() or not ruleset_version.strip():
        raise ValueError("engine and ruleset versions required")
    if artifact_version < 1:
        raise ValueError("artifact_version must be positive")
    payload = {
        "artifact_id": artifact_id.strip(),
        "property_id": property_id.strip(),
        "intelligence_type": intelligence_type.strip(),
        "dependency_domains": domains,
        "value_fingerprint": value_fingerprint,
        "certification_state": "CERTIFIED",
        "lineage_fingerprints": lineage,
        "engine_version": engine_version.strip(),
        "ruleset_version": ruleset_version.strip(),
        "artifact_version": artifact_version,
        "suppressed": bool(suppressed),
    }
    return CertifiedIntelligenceArtifact(**payload, artifact_fingerprint=_hash(payload))


def _disposition(change: FieldChange, registry: Mapping[str, object]) -> str:
    rules = registry["dependency_rules"].get(change.domain)
    if not rules:
        return "UNKNOWN_IMPACT"
    by_class = rules.get("classification_dispositions") or {}
    disposition = by_class.get(change.classification, rules.get("default_disposition"))
    return str(disposition or "UNKNOWN_IMPACT")


def _precedence(disposition: str) -> int:
    return {
        "NO_IMPACT": 0,
        "REVALIDATE_ONLY": 1,
        "UNSUPPRESS": 2,
        "SUPPRESS": 3,
        "REFRESH_REQUIRED": 4,
        "UNKNOWN_IMPACT": 5,
        "BLOCKED": 6,
    }[disposition]


def _change_applies(change: FieldChange, artifact: CertifiedIntelligenceArtifact) -> bool:
    if change.classification == "UNCHANGED":
        return False
    if change.domain not in set(artifact.dependency_domains):
        return False
    if change.scope == "PROPERTY":
        return change.object_id == artifact.property_id
    return True


def _decision(
    artifact: CertifiedIntelligenceArtifact,
    changes: Sequence[FieldChange],
    registry: Mapping[str, object],
) -> RefreshDecision:
    matched = tuple(x for x in changes if _change_applies(x, artifact))
    if not matched:
        disposition = "NO_IMPACT"
        domains: tuple[str, ...] = ()
        triggers: tuple[str, ...] = ()
        reasons = ("NO_MATCHING_DEPENDENCY_CHANGE",)
    else:
        pairs = tuple((_disposition(x, registry), x) for x in matched)
        disposition = max((x[0] for x in pairs), key=_precedence)
        domains = tuple(sorted(set(x.domain for x in matched)))
        triggers = tuple(sorted(x.change_fingerprint for x in matched))
        reasons = tuple(sorted({
            f"{x.domain}:{x.classification}:{_disposition(x, registry)}"
            for x in matched
        }))
    payload = {
        "artifact_id": artifact.artifact_id,
        "property_id": artifact.property_id,
        "disposition": disposition,
        "matched_domains": domains,
        "triggering_change_fingerprints": triggers,
        "reason_codes": reasons,
        "prior_artifact_fingerprint": artifact.artifact_fingerprint,
    }
    return RefreshDecision(**payload, decision_fingerprint=_hash(payload))


def build_refresh_plan(
    *,
    plan_id: str,
    delta: CommunityDelta,
    current_artifacts: Sequence[CertifiedIntelligenceArtifact],
    registry: Mapping[str, object],
) -> RefreshPlan:
    if not plan_id.strip():
        raise ValueError("plan_id required")
    if delta.certification_state != registry["policy"]["required_delta_certification_state"]:
        raise ValueError("certified M13-002 delta required")
    if not validate_delta_replay(delta):
        raise ValueError("delta replay validation failed")
    artifacts = tuple(sorted(current_artifacts, key=lambda x: x.artifact_id))
    if len({x.artifact_id for x in artifacts}) != len(artifacts):
        raise ValueError("artifact_id must be unique")
    required_state = registry["policy"]["required_artifact_certification_state"]
    if any(x.certification_state != required_state for x in artifacts):
        raise ValueError("current certified intelligence required")

    decisions = tuple(_decision(x, delta.changes, registry) for x in artifacts)
    targeted = tuple(sorted(
        x.artifact_id for x in decisions
        if x.disposition in {"REFRESH_REQUIRED", "SUPPRESS", "UNSUPPRESS"}
    ))
    no_impact = tuple(sorted(x.artifact_id for x in decisions if x.disposition == "NO_IMPACT"))
    blocked = tuple(sorted(
        x.artifact_id for x in decisions
        if x.disposition in {"BLOCKED", "UNKNOWN_IMPACT"}
    ))
    payload = {
        "plan_id": plan_id.strip(),
        "delta_fingerprint": delta.delta_fingerprint,
        "delta_before_snapshot_hash": delta.before_snapshot_semantic_hash,
        "delta_after_snapshot_hash": delta.after_snapshot_semantic_hash,
        "refresh_policy_version": registry["policy"]["version"],
        "decisions": tuple(asdict(x) for x in decisions),
        "targeted_artifact_ids": targeted,
        "no_impact_artifact_ids": no_impact,
        "blocked_artifact_ids": blocked,
        "certification_state": "DRAFT",
        "reproducible": True,
    }
    return RefreshPlan(**payload, plan_fingerprint=_hash(payload))


def validate_refresh_plan_replay(plan: RefreshPlan) -> bool:
    payload = {
        "plan_id": plan.plan_id,
        "delta_fingerprint": plan.delta_fingerprint,
        "delta_before_snapshot_hash": plan.delta_before_snapshot_hash,
        "delta_after_snapshot_hash": plan.delta_after_snapshot_hash,
        "refresh_policy_version": plan.refresh_policy_version,
        "decisions": tuple(asdict(x) for x in plan.decisions),
        "targeted_artifact_ids": plan.targeted_artifact_ids,
        "no_impact_artifact_ids": plan.no_impact_artifact_ids,
        "blocked_artifact_ids": plan.blocked_artifact_ids,
        "certification_state": "DRAFT",
        "reproducible": True,
    }
    return _hash(payload) == plan.plan_fingerprint


def certify_refresh_plan(plan: RefreshPlan) -> RefreshPlan:
    if plan.certification_state != "DRAFT":
        raise ValueError("only DRAFT refresh plan may be certified")
    if not validate_refresh_plan_replay(plan):
        raise ValueError("refresh plan is nonreproducible")
    return replace(plan, certification_state="CERTIFIED")


def _stage_artifact(
    *,
    artifact: CertifiedIntelligenceArtifact,
    decision: RefreshDecision,
    delta: CommunityDelta,
    triggering_changes: tuple[FieldChange, ...],
    refreshers: Mapping[str, RefreshFunction],
    engine_versions: Mapping[str, str],
    ruleset_versions: Mapping[str, str],
    frozen_input_fingerprints: Mapping[str, str],
) -> StagedIntelligenceArtifact:
    frozen_input = frozen_input_fingerprints.get(artifact.artifact_id)
    if frozen_input is None:
        raise ValueError(f"missing frozen input fingerprint for {artifact.artifact_id}")
    _fp(frozen_input, "frozen input fingerprint")

    if decision.disposition == "REFRESH_REQUIRED":
        refresher = refreshers.get(artifact.intelligence_type)
        if refresher is None:
            raise ValueError(f"missing refresher for {artifact.intelligence_type}")
        engine = str(engine_versions.get(artifact.intelligence_type) or "")
        ruleset = str(ruleset_versions.get(artifact.intelligence_type) or "")
        if not engine or not ruleset:
            raise ValueError("exact engine and ruleset versions required")
        first = refresher(artifact, triggering_changes, frozen_input, engine, ruleset)
        second = refresher(artifact, triggering_changes, frozen_input, engine, ruleset)
        _fp(first, "refreshed value fingerprint")
        _fp(second, "refreshed value fingerprint")
        if first != second:
            raise ValueError("refresh callback is nondeterministic")
        value_fp = first
        suppressed = artifact.suppressed
        engine_version = engine
        ruleset_version = ruleset
    elif decision.disposition == "SUPPRESS":
        value_fp = artifact.value_fingerprint
        suppressed = True
        engine_version = artifact.engine_version
        ruleset_version = artifact.ruleset_version
    elif decision.disposition == "UNSUPPRESS":
        value_fp = artifact.value_fingerprint
        suppressed = False
        engine_version = artifact.engine_version
        ruleset_version = artifact.ruleset_version
    else:
        raise ValueError("decision is not stageable")

    lineage = tuple(sorted(set(
        artifact.lineage_fingerprints
        + (artifact.artifact_fingerprint, delta.delta_fingerprint, frozen_input)
        + tuple(x.change_fingerprint for x in triggering_changes)
    )))
    payload = {
        "artifact_id": artifact.artifact_id,
        "prior_artifact_fingerprint": artifact.artifact_fingerprint,
        "property_id": artifact.property_id,
        "intelligence_type": artifact.intelligence_type,
        "dependency_domains": artifact.dependency_domains,
        "value_fingerprint": value_fp,
        "lineage_fingerprints": lineage,
        "engine_version": engine_version,
        "ruleset_version": ruleset_version,
        "artifact_version": artifact.artifact_version + 1,
        "suppressed": suppressed,
        "source_delta_fingerprint": delta.delta_fingerprint,
        "frozen_input_fingerprint": frozen_input,
    }
    return StagedIntelligenceArtifact(**payload, stage_fingerprint=_hash(payload))


def _proof(
    *,
    decision: RefreshDecision,
    action_taken: str,
    staged: StagedIntelligenceArtifact | None,
) -> RefreshProof:
    payload = {
        "artifact_id": decision.artifact_id,
        "disposition": decision.disposition,
        "action_taken": action_taken,
        "reason_codes": decision.reason_codes,
        "triggering_change_fingerprints": decision.triggering_change_fingerprints,
        "before_artifact_fingerprint": decision.prior_artifact_fingerprint,
        "staged_artifact_fingerprint": staged.stage_fingerprint if staged else None,
    }
    return RefreshProof(**payload, proof_fingerprint=_hash(payload))


def stage_selective_refresh(
    *,
    execution_id: str,
    plan: RefreshPlan,
    delta: CommunityDelta,
    current_artifacts: Sequence[CertifiedIntelligenceArtifact],
    refreshers: Mapping[str, RefreshFunction],
    engine_versions: Mapping[str, str],
    ruleset_versions: Mapping[str, str],
    frozen_input_fingerprints: Mapping[str, str],
) -> RefreshExecution:
    if plan.certification_state != "CERTIFIED":
        raise ValueError("certified refresh plan required")
    if not validate_refresh_plan_replay(plan):
        raise ValueError("refresh plan replay validation failed")
    if delta.certification_state != "CERTIFIED" or not validate_delta_replay(delta):
        raise ValueError("certified reproducible delta required")
    if plan.delta_fingerprint != delta.delta_fingerprint:
        raise ValueError("plan/delta lineage mismatch")
    artifacts = tuple(sorted(current_artifacts, key=lambda x: x.artifact_id))
    by_id = {x.artifact_id: x for x in artifacts}
    if tuple(sorted(by_id)) != tuple(sorted(x.artifact_id for x in plan.decisions)):
        raise ValueError("current artifact set does not match certified plan")

    decisions = {x.artifact_id: x for x in plan.decisions}
    if plan.blocked_artifact_ids:
        proofs = tuple(
            _proof(decision=d, action_taken="BLOCKED_NO_MUTATION", staged=None)
            for d in plan.decisions
        )
        return _execution(
            execution_id=execution_id, plan=plan, delta=delta, prior=artifacts,
            staged=(), active=artifacts, proofs=proofs,
            status="BLOCKED", blocking=tuple(f"BLOCKED:{x}" for x in plan.blocked_artifact_ids),
        )

    staged: list[StagedIntelligenceArtifact] = []
    proofs: list[RefreshProof] = []
    try:
        for artifact in artifacts:
            decision = decisions[artifact.artifact_id]
            triggers = tuple(
                x for x in delta.changes
                if x.change_fingerprint in set(decision.triggering_change_fingerprints)
            )
            if decision.disposition in {"REFRESH_REQUIRED", "SUPPRESS", "UNSUPPRESS"}:
                result = _stage_artifact(
                    artifact=artifact, decision=decision, delta=delta,
                    triggering_changes=triggers, refreshers=refreshers,
                    engine_versions=engine_versions, ruleset_versions=ruleset_versions,
                    frozen_input_fingerprints=frozen_input_fingerprints,
                )
                staged.append(result)
                proofs.append(_proof(decision=decision, action_taken="STAGED", staged=result))
            elif decision.disposition == "REVALIDATE_ONLY":
                proofs.append(_proof(decision=decision, action_taken="REVALIDATE_ONLY_NO_MUTATION", staged=None))
            elif decision.disposition == "NO_IMPACT":
                proofs.append(_proof(decision=decision, action_taken="NO_REFRESH_PRESERVED", staged=None))
            else:
                raise ValueError(f"unsupported executable disposition {decision.disposition}")
    except Exception as exc:
        failure_proofs = tuple(proofs) + tuple(
            _proof(
                decision=d,
                action_taken="FAILED_STAGE_PRIOR_STATE_PRESERVED",
                staged=None,
            )
            for d in plan.decisions
            if d.artifact_id not in {p.artifact_id for p in proofs}
        )
        return _execution(
            execution_id=execution_id, plan=plan, delta=delta, prior=artifacts,
            staged=(), active=artifacts, proofs=failure_proofs,
            status="FAILED", blocking=(f"STAGING_FAILED:{type(exc).__name__}:{exc}",),
        )

    return _execution(
        execution_id=execution_id, plan=plan, delta=delta, prior=artifacts,
        staged=tuple(sorted(staged, key=lambda x: x.artifact_id)),
        active=artifacts, proofs=tuple(sorted(proofs, key=lambda x: x.artifact_id)),
        status="STAGED", blocking=(),
    )


def _execution(
    *,
    execution_id: str,
    plan: RefreshPlan,
    delta: CommunityDelta,
    prior: tuple[CertifiedIntelligenceArtifact, ...],
    staged: tuple[StagedIntelligenceArtifact, ...],
    active: tuple[CertifiedIntelligenceArtifact, ...],
    proofs: tuple[RefreshProof, ...],
    status: str,
    blocking: tuple[str, ...],
) -> RefreshExecution:
    payload = {
        "execution_id": execution_id,
        "plan_fingerprint": plan.plan_fingerprint,
        "delta_fingerprint": delta.delta_fingerprint,
        "status": status,
        "prior_artifact_fingerprints": tuple(x.artifact_fingerprint for x in prior),
        "staged_artifact_fingerprints": tuple(x.stage_fingerprint for x in staged),
        "active_artifact_fingerprints": tuple(x.artifact_fingerprint for x in active),
        "proof_fingerprints": tuple(x.proof_fingerprint for x in proofs),
        "blocking_reasons": blocking,
    }
    return RefreshExecution(
        execution_id=execution_id,
        plan_fingerprint=plan.plan_fingerprint,
        delta_fingerprint=delta.delta_fingerprint,
        status=status,
        prior_artifacts=prior,
        staged_artifacts=staged,
        active_artifacts=active,
        proofs=proofs,
        blocking_reasons=blocking,
        execution_fingerprint=_hash(payload),
    )


def promote_staged_refresh(execution: RefreshExecution) -> RefreshExecution:
    if execution.status != "STAGED":
        raise ValueError("only fully STAGED execution may be promoted")
    prior = {x.artifact_id: x for x in execution.prior_artifacts}
    staged = {x.artifact_id: x for x in execution.staged_artifacts}
    active: list[CertifiedIntelligenceArtifact] = []
    for artifact_id in sorted(prior):
        old = prior[artifact_id]
        replacement = staged.get(artifact_id)
        if replacement is None:
            active.append(old)
            continue
        active.append(make_certified_intelligence_artifact(
            artifact_id=replacement.artifact_id,
            property_id=replacement.property_id,
            intelligence_type=replacement.intelligence_type,
            dependency_domains=replacement.dependency_domains,
            value_fingerprint=replacement.value_fingerprint,
            lineage_fingerprints=replacement.lineage_fingerprints,
            engine_version=replacement.engine_version,
            ruleset_version=replacement.ruleset_version,
            artifact_version=replacement.artifact_version,
            suppressed=replacement.suppressed,
        ))
    promoted = tuple(active)
    payload = {
        "execution_id": execution.execution_id,
        "plan_fingerprint": execution.plan_fingerprint,
        "delta_fingerprint": execution.delta_fingerprint,
        "status": "PROMOTED",
        "prior_artifact_fingerprints": tuple(x.artifact_fingerprint for x in execution.prior_artifacts),
        "staged_artifact_fingerprints": tuple(x.stage_fingerprint for x in execution.staged_artifacts),
        "active_artifact_fingerprints": tuple(x.artifact_fingerprint for x in promoted),
        "proof_fingerprints": tuple(x.proof_fingerprint for x in execution.proofs),
        "blocking_reasons": (),
    }
    return replace(
        execution,
        status="PROMOTED",
        active_artifacts=promoted,
        blocking_reasons=(),
        execution_fingerprint=_hash(payload),
    )
