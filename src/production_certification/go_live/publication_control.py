from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping
from uuid import UUID, uuid4

import yaml

from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class ManualPublicationPolicy:
    policy_id: str
    policy_version: str
    default_mode: str
    requires_current_stop_condition_clearance: bool
    requires_operator_identity: bool
    requires_reason_code: bool
    requires_candidate_fingerprint_match: bool
    allowed_actions: tuple[str, ...]
    prohibited_in_manual_mode: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> "ManualPublicationPolicy":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED" or data.get("default_mode") != "MANUAL":
            raise ValueError("manual publication policy must be LOCKED/MANUAL")
        actions = tuple(str(x) for x in (data.get("allowed_actions") or ()))
        if not actions or len(set(actions)) != len(actions):
            raise ValueError("manual publication policy requires unique allowed actions")
        return cls(
            str(data["policy_id"]), str(data["policy_version"]), "MANUAL",
            bool(data.get("requires_current_stop_condition_clearance", True)),
            bool(data.get("requires_operator_identity", True)), bool(data.get("requires_reason_code", True)),
            bool(data.get("requires_candidate_fingerprint_match", True)), actions,
            tuple(str(x) for x in (data.get("prohibited_in_manual_mode") or ())),
        )


@dataclass(frozen=True)
class ManualPublicationAuthorization:
    production_certification_id: UUID
    policy_version: str
    action: str
    candidate_fingerprint: str
    stop_condition_fingerprint: str
    operator_id: str
    reason_code: str
    authorization_fingerprint: str
    authorized_at: datetime
    mode: str = "MANUAL"


class ManualPublicationAuthorizer:
    def authorize(
        self, *, policy: ManualPublicationPolicy, production_certification_id: UUID, action: str,
        expected_candidate_fingerprint: str, observed_candidate_fingerprint: str,
        current_stop_conditions: GoLiveStopResult, operator_id: str, reason_code: str,
        authorized_at: datetime | None = None,
    ) -> ManualPublicationAuthorization:
        if action not in policy.allowed_actions:
            raise ValueError("publication action is not allowed by manual policy")
        if policy.requires_operator_identity and not operator_id.strip():
            raise ValueError("operator_id is required")
        if policy.requires_reason_code and not reason_code.strip():
            raise ValueError("reason_code is required")
        if policy.requires_candidate_fingerprint_match and expected_candidate_fingerprint != observed_candidate_fingerprint:
            raise ValueError("candidate fingerprint mismatch")
        if current_stop_conditions.production_certification_id != production_certification_id:
            raise ValueError("stop-condition certification identity mismatch")
        if policy.requires_current_stop_condition_clearance and current_stop_conditions.status != "CLEAR":
            raise ValueError("go-live stop conditions are not clear")
        now = authorized_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("authorized_at must be timezone-aware")
        payload = {
            "production_certification_id": str(production_certification_id), "policy_version": policy.policy_version,
            "mode": "MANUAL", "action": action, "candidate_fingerprint": observed_candidate_fingerprint,
            "stop_condition_fingerprint": current_stop_conditions.evidence_fingerprint,
            "operator_id": operator_id, "reason_code": reason_code, "authorized_at": now.isoformat(),
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return ManualPublicationAuthorization(
            production_certification_id, policy.policy_version, action, observed_candidate_fingerprint,
            current_stop_conditions.evidence_fingerprint, operator_id, reason_code, fp, now,
        )


@dataclass(frozen=True)
class AutomationStage:
    stage_code: str
    prior_stage: str


@dataclass(frozen=True)
class ProgressiveAutomationPolicy:
    policy_id: str
    policy_version: str
    default_mode: str
    requires_explicit_handoff: bool
    requires_current_stop_condition_clearance: bool
    requires_rollback_baseline: bool
    requires_prior_stage_certification_pass: bool
    allowed_stages: Mapping[str, AutomationStage]
    prohibited_actions: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> "ProgressiveAutomationPolicy":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED" or data.get("default_mode") != "MANUAL":
            raise ValueError("progressive automation policy must be LOCKED with MANUAL default")
        stages = {
            str(code): AutomationStage(str(code), str(row["prior_stage"]))
            for code, row in (data.get("allowed_stages") or {}).items()
        }
        if not stages:
            raise ValueError("progressive automation policy requires stages")
        return cls(
            str(data["policy_id"]), str(data["policy_version"]), "MANUAL",
            bool(data.get("requires_explicit_handoff", True)),
            bool(data.get("requires_current_stop_condition_clearance", True)),
            bool(data.get("requires_rollback_baseline", True)),
            bool(data.get("requires_prior_stage_certification_pass", True)), stages,
            tuple(str(x) for x in (data.get("prohibited_actions") or ())),
        )

    def require_stage(self, stage_code: str) -> AutomationStage:
        try:
            return self.allowed_stages[stage_code]
        except KeyError as exc:
            raise ValueError(f"stage is not automation-authorized: {stage_code}") from exc


@dataclass(frozen=True)
class AutomationHandoff:
    automation_handoff_id: UUID
    production_certification_id: UUID
    policy_version: str
    stage_code: str
    prior_stage: str
    candidate_fingerprint: str
    prior_certification_id: UUID
    prior_certification_fingerprint: str
    stop_condition_fingerprint: str
    requested_by: str
    reason_code: str
    handoff_fingerprint: str
    created_at: datetime
    mode: str = "AUTOMATED"


class ProgressiveAutomationAuthorizer:
    def authorize(
        self, *, policy: ProgressiveAutomationPolicy, production_certification_id: UUID,
        stage_code: str, candidate_fingerprint: str, prior_stage: str,
        prior_certification_id: UUID, prior_certification_fingerprint: str, prior_certification_status: str,
        current_stop_conditions: GoLiveStopResult, requested_by: str, reason_code: str,
        created_at: datetime | None = None, automation_handoff_id: UUID | None = None,
    ) -> AutomationHandoff:
        stage = policy.require_stage(stage_code)
        if stage.prior_stage != prior_stage:
            raise ValueError("prior stage does not match automation policy")
        if policy.requires_prior_stage_certification_pass and prior_certification_status != "PASS":
            raise ValueError("prior stage certification has not passed")
        if current_stop_conditions.production_certification_id != production_certification_id:
            raise ValueError("stop-condition certification identity mismatch")
        if policy.requires_current_stop_condition_clearance and current_stop_conditions.status != "CLEAR":
            raise ValueError("go-live stop conditions are not clear")
        if not requested_by.strip() or not reason_code.strip():
            raise ValueError("requested_by and reason_code are required")
        if len(candidate_fingerprint) != 64 or len(prior_certification_fingerprint) != 64:
            raise ValueError("candidate/prior certification fingerprints must be sha256")
        now = created_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        hid = automation_handoff_id or uuid4()
        payload = {
            "automation_handoff_id": str(hid), "production_certification_id": str(production_certification_id),
            "policy_version": policy.policy_version, "stage_code": stage_code, "prior_stage": prior_stage,
            "candidate_fingerprint": candidate_fingerprint, "prior_certification_id": str(prior_certification_id),
            "prior_certification_fingerprint": prior_certification_fingerprint,
            "stop_condition_fingerprint": current_stop_conditions.evidence_fingerprint,
            "requested_by": requested_by, "reason_code": reason_code, "created_at": now.isoformat(),
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return AutomationHandoff(
            hid, production_certification_id, policy.policy_version, stage_code, prior_stage,
            candidate_fingerprint, prior_certification_id, prior_certification_fingerprint,
            current_stop_conditions.evidence_fingerprint, requested_by, reason_code, fp, now,
        )


@dataclass(frozen=True)
class PublicationPointerState:
    property_id: UUID
    variant: str
    channel: str
    semantic_report_id: UUID | None
    channel_render_id: UUID | None


@dataclass(frozen=True)
class RollbackBaselineEntry:
    property_id: UUID
    variant: str
    channel: str
    semantic_report_id: UUID | None
    channel_render_id: UUID | None
    entry_fingerprint: str


@dataclass(frozen=True)
class RollbackBaseline:
    rollback_baseline_id: UUID
    production_certification_id: UUID
    stage_code: str
    candidate_fingerprint: str
    automation_handoff_id: UUID
    automation_handoff_fingerprint: str
    entries: tuple[RollbackBaselineEntry, ...]
    baseline_fingerprint: str
    captured_by: str
    captured_at: datetime


class RollbackBaselineCapture:
    def capture(
        self, *, production_certification_id: UUID, stage_code: str, candidate_fingerprint: str,
        handoff: AutomationHandoff, target_property_ids: Iterable[UUID], pointer_states: Iterable[PublicationPointerState],
        captured_by: str, captured_at: datetime | None = None, rollback_baseline_id: UUID | None = None,
    ) -> RollbackBaseline:
        if handoff.production_certification_id != production_certification_id or handoff.stage_code != stage_code:
            raise ValueError("automation handoff does not match rollback target")
        if handoff.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("automation handoff candidate mismatch")
        if not captured_by.strip():
            raise ValueError("captured_by is required")
        targets = tuple(sorted(set(target_property_ids), key=str))
        if not targets:
            raise ValueError("rollback baseline requires target properties")
        states = tuple(pointer_states)
        seen: set[tuple[UUID, str, str]] = set()
        entries: list[RollbackBaselineEntry] = []
        target_set = set(targets)
        for state in sorted(states, key=lambda x: (str(x.property_id), x.variant, x.channel)):
            if state.property_id not in target_set:
                raise ValueError("pointer state contains property outside target membership")
            key = (state.property_id, state.variant, state.channel)
            if key in seen:
                raise ValueError("duplicate pointer state")
            seen.add(key)
            payload = {
                "property_id": str(state.property_id), "variant": state.variant, "channel": state.channel,
                "semantic_report_id": str(state.semantic_report_id) if state.semantic_report_id else None,
                "channel_render_id": str(state.channel_render_id) if state.channel_render_id else None,
            }
            efp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            entries.append(RollbackBaselineEntry(state.property_id, state.variant, state.channel,
                                                 state.semantic_report_id, state.channel_render_id, efp))
        covered = {x.property_id for x in entries}
        if covered != target_set:
            missing = sorted(str(x) for x in target_set - covered)
            raise ValueError(f"rollback baseline missing target properties: {missing}")
        now = captured_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        bid = rollback_baseline_id or uuid4()
        payload = {
            "rollback_baseline_id": str(bid), "production_certification_id": str(production_certification_id),
            "stage_code": stage_code, "candidate_fingerprint": candidate_fingerprint,
            "automation_handoff_id": str(handoff.automation_handoff_id),
            "automation_handoff_fingerprint": handoff.handoff_fingerprint,
            "entry_fingerprints": [x.entry_fingerprint for x in entries],
        }
        bfp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return RollbackBaseline(
            bid, production_certification_id, stage_code, candidate_fingerprint,
            handoff.automation_handoff_id, handoff.handoff_fingerprint, tuple(entries), bfp, captured_by, now,
        )
