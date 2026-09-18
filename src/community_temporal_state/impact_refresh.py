from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.community_temporal_state.delta import CommunityDelta, FieldChange, validate_delta_replay


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_impact_refresh_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-003":
        raise ValueError("M13-003 impact refresh registry must be FROZEN")
    if data.get("impact_refresh_registry_id") != "STH-M13-003-IMPACT-REFRESH-v1.0":
        raise ValueError("unexpected M13-003 impact refresh registry id")
    return data


@dataclass(frozen=True)
class DerivedIntelligenceRecord:
    artifact_id: str
    artifact_type: str
    scope: str
    scope_id: str
    source_snapshot_semantic_hash: str
    payload_fingerprint: str
    certification_state: str
    lineage_fingerprints: tuple[str, ...]
    record_fingerprint: str


@dataclass(frozen=True)
class RefreshDecision:
    artifact_id: str
    artifact_type: str
    scope: str
    scope_id: str
    decision: str
    reason_codes: tuple[str, ...]
    source_change_fingerprints: tuple[str, ...]
    current_record_fingerprint: str
    decision_fingerprint: str


@dataclass(frozen=True)
class SelectiveRefreshPlan:
    plan_id: str
    community_id: str
    delta_id: str
    delta_fingerprint: str
    after_snapshot_semantic_hash: str
    dependency_policy_fingerprint: str
    decisions: tuple[RefreshDecision, ...]
    refresh_artifact_ids: tuple[str, ...]
    preserved_artifact_ids: tuple[str, ...]
    plan_fingerprint: str


@dataclass(frozen=True)
class SelectiveRefreshResult:
    result_id: str
    plan_id: str
    plan_fingerprint: str
    records: tuple[DerivedIntelligenceRecord, ...]
    refreshed_artifact_ids: tuple[str, ...]
    preserved_artifact_ids: tuple[str, ...]
    replacement_fingerprints: tuple[str, ...]
    result_fingerprint: str


def make_derived_record(
    *,
    artifact_id: str,
    artifact_type: str,
    scope: str,
    scope_id: str,
    source_snapshot_semantic_hash: str,
    payload_fingerprint: str,
    certification_state: str = "CERTIFIED",
    lineage_fingerprints: Sequence[str] = (),
) -> DerivedIntelligenceRecord:
    if not artifact_id.strip() or not artifact_type.strip() or not scope.strip() or not scope_id.strip():
        raise ValueError("artifact identity and scope are required")
    if scope not in {"PROPERTY", "COMMUNITY"}:
        raise ValueError("unsupported derived record scope")
    _validate_fp(source_snapshot_semantic_hash, "source snapshot semantic hash")
    _validate_fp(payload_fingerprint, "payload fingerprint")
    lineage = tuple(sorted(set(lineage_fingerprints)))
    for fp in lineage:
        _validate_fp(fp, "lineage fingerprint")
    payload = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "scope": scope,
        "scope_id": scope_id,
        "source_snapshot_semantic_hash": source_snapshot_semantic_hash,
        "payload_fingerprint": payload_fingerprint,
        "certification_state": certification_state,
        "lineage_fingerprints": lineage,
    }
    return DerivedIntelligenceRecord(**payload, record_fingerprint=_hash(payload))


def policy_fingerprint(registry: Mapping[str, object]) -> str:
    return _hash({
        "policy": registry["policy"],
        "dependency_rules": registry["dependency_rules"],
        "scope_rules": registry["scope_rules"],
        "governance": registry["governance"],
    })


def _changed(change: FieldChange, registry: Mapping[str, object]) -> bool:
    return change.classification in set(registry["policy"]["refresh_required_classifications"])


def _change_targets_artifact(
    change: FieldChange,
    record: DerivedIntelligenceRecord,
    *,
    registry: Mapping[str, object],
) -> bool:
    allowed_types = set(registry["dependency_rules"].get(change.domain, ()))
    if record.artifact_type not in allowed_types:
        return False
    if change.scope == "PROPERTY":
        return record.scope == "PROPERTY" and record.scope_id == change.object_id
    if change.scope in {"COMMUNITY", "MANIFEST"}:
        return True
    return False


def build_selective_refresh_plan(
    *,
    plan_id: str,
    delta: CommunityDelta,
    current_records: Sequence[DerivedIntelligenceRecord],
    registry: Mapping[str, object],
) -> SelectiveRefreshPlan:
    if not plan_id.strip():
        raise ValueError("plan_id required")
    if delta.certification_state != registry["policy"]["accepted_delta_state"]:
        raise ValueError("M13-003 requires CERTIFIED M13-002 delta")
    if not validate_delta_replay(delta):
        raise ValueError("M13-003 requires reproducible M13-002 delta")
    if len({r.artifact_id for r in current_records}) != len(current_records):
        raise ValueError("duplicate artifact ids prohibited")

    allowed_current = set(registry["policy"]["allowed_current_certification_states"])
    decisions: list[RefreshDecision] = []
    changed = tuple(c for c in delta.changes if _changed(c, registry))

    for record in sorted(current_records, key=lambda r: r.artifact_id):
        if record.certification_state not in allowed_current:
            raise ValueError("current derived state must be certified")
        _validate_fp(record.record_fingerprint, "current record fingerprint")
        matching = tuple(c for c in changed if _change_targets_artifact(c, record, registry=registry))
        if matching:
            decision = "REFRESH_REQUIRED"
            reasons = tuple(sorted({f"{c.domain}:{c.classification}" for c in matching}))
            source_changes = tuple(sorted({c.change_fingerprint for c in matching}))
        else:
            decision = "NO_IMPACT"
            reasons = ("NO_GOVERNED_DEPENDENCY_MATCH",)
            source_changes = ()
        payload = {
            "artifact_id": record.artifact_id,
            "artifact_type": record.artifact_type,
            "scope": record.scope,
            "scope_id": record.scope_id,
            "decision": decision,
            "reason_codes": reasons,
            "source_change_fingerprints": source_changes,
            "current_record_fingerprint": record.record_fingerprint,
        }
        decisions.append(RefreshDecision(**payload, decision_fingerprint=_hash(payload)))

    decisions_tuple = tuple(decisions)
    refresh_ids = tuple(d.artifact_id for d in decisions_tuple if d.decision == "REFRESH_REQUIRED")
    preserved_ids = tuple(d.artifact_id for d in decisions_tuple if d.decision == "NO_IMPACT")
    dependency_fp = policy_fingerprint(registry)
    hash_payload = {
        "plan_id": plan_id,
        "community_id": delta.community_id,
        "delta_id": delta.delta_id,
        "delta_fingerprint": delta.delta_fingerprint,
        "after_snapshot_semantic_hash": delta.after_snapshot_semantic_hash,
        "dependency_policy_fingerprint": dependency_fp,
        "decisions": tuple(asdict(d) for d in decisions_tuple),
        "refresh_artifact_ids": refresh_ids,
        "preserved_artifact_ids": preserved_ids,
    }
    return SelectiveRefreshPlan(
        plan_id=plan_id,
        community_id=delta.community_id,
        delta_id=delta.delta_id,
        delta_fingerprint=delta.delta_fingerprint,
        after_snapshot_semantic_hash=delta.after_snapshot_semantic_hash,
        dependency_policy_fingerprint=dependency_fp,
        decisions=decisions_tuple,
        refresh_artifact_ids=refresh_ids,
        preserved_artifact_ids=preserved_ids,
        plan_fingerprint=_hash(hash_payload),
    )


def validate_refresh_plan_replay(plan: SelectiveRefreshPlan) -> bool:
    payload = {
        "plan_id": plan.plan_id,
        "community_id": plan.community_id,
        "delta_id": plan.delta_id,
        "delta_fingerprint": plan.delta_fingerprint,
        "after_snapshot_semantic_hash": plan.after_snapshot_semantic_hash,
        "dependency_policy_fingerprint": plan.dependency_policy_fingerprint,
        "decisions": tuple(asdict(d) for d in plan.decisions),
        "refresh_artifact_ids": plan.refresh_artifact_ids,
        "preserved_artifact_ids": plan.preserved_artifact_ids,
    }
    return _hash(payload) == plan.plan_fingerprint


def apply_selective_refresh(
    *,
    result_id: str,
    plan: SelectiveRefreshPlan,
    current_records: Sequence[DerivedIntelligenceRecord],
    authoritative_replacements: Sequence[DerivedIntelligenceRecord],
    registry: Mapping[str, object],
) -> SelectiveRefreshResult:
    if not result_id.strip():
        raise ValueError("result_id required")
    if not validate_refresh_plan_replay(plan):
        raise ValueError("refresh plan is nonreproducible")

    current = {x.artifact_id: x for x in current_records}
    replacements = {x.artifact_id: x for x in authoritative_replacements}
    if len(current) != len(current_records) or len(replacements) != len(authoritative_replacements):
        raise ValueError("duplicate artifact ids prohibited")

    required = set(plan.refresh_artifact_ids)
    preserved = set(plan.preserved_artifact_ids)
    if set(replacements) != required:
        missing = sorted(required - set(replacements))
        extra = sorted(set(replacements) - required)
        raise ValueError(
            f"authoritative replacements must exactly match refresh set; missing={missing}, extra={extra}"
        )

    allowed_replacement = set(registry["policy"]["allowed_replacement_certification_states"])
    output: list[DerivedIntelligenceRecord] = []
    replacement_fps: list[str] = []

    for decision in plan.decisions:
        old = current.get(decision.artifact_id)
        if old is None or old.record_fingerprint != decision.current_record_fingerprint:
            raise ValueError("current derived state drifted after refresh planning")
        if decision.decision == "NO_IMPACT":
            output.append(old)
            continue
        replacement = replacements[decision.artifact_id]
        if replacement.certification_state not in allowed_replacement:
            raise ValueError("authoritative replacement must be CERTIFIED")
        if (
            replacement.artifact_type != old.artifact_type
            or replacement.scope != old.scope
            or replacement.scope_id != old.scope_id
        ):
            raise ValueError("replacement artifact identity/scope mismatch")
        if replacement.source_snapshot_semantic_hash != plan.after_snapshot_semantic_hash:
            raise ValueError("replacement not bound to delta after-snapshot")
        required_lineage = {plan.delta_fingerprint, decision.decision_fingerprint}
        if not required_lineage.issubset(set(replacement.lineage_fingerprints)):
            raise ValueError("replacement missing M13-003 refresh lineage")
        output.append(replacement)
        replacement_fps.append(replacement.record_fingerprint)

    out_tuple = tuple(sorted(output, key=lambda r: r.artifact_id))
    if {r.artifact_id for r in out_tuple} != set(current):
        raise ValueError("selective refresh cannot add or drop current artifact identities")
    refreshed_ids = tuple(sorted(required))
    preserved_ids = tuple(sorted(preserved))
    replacement_ids = tuple(sorted(replacement_fps))
    hash_payload = {
        "result_id": result_id,
        "plan_id": plan.plan_id,
        "plan_fingerprint": plan.plan_fingerprint,
        "records": tuple(asdict(r) for r in out_tuple),
        "refreshed_artifact_ids": refreshed_ids,
        "preserved_artifact_ids": preserved_ids,
        "replacement_fingerprints": replacement_ids,
    }
    return SelectiveRefreshResult(
        result_id=result_id,
        plan_id=plan.plan_id,
        plan_fingerprint=plan.plan_fingerprint,
        records=out_tuple,
        refreshed_artifact_ids=refreshed_ids,
        preserved_artifact_ids=preserved_ids,
        replacement_fingerprints=replacement_ids,
        result_fingerprint=_hash(hash_payload),
    )


def validate_refresh_result_replay(result: SelectiveRefreshResult) -> bool:
    payload = {
        "result_id": result.result_id,
        "plan_id": result.plan_id,
        "plan_fingerprint": result.plan_fingerprint,
        "records": tuple(asdict(r) for r in result.records),
        "refreshed_artifact_ids": result.refreshed_artifact_ids,
        "preserved_artifact_ids": result.preserved_artifact_ids,
        "replacement_fingerprints": result.replacement_fingerprints,
    }
    return _hash(payload) == result.result_fingerprint
