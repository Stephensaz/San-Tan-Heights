from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_comparison import ScenarioComparisonMember, MultiScenarioComparison
from src.community_temporal_state.scenario_explainability import ScenarioExplanation, ComparisonExplanation


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_review_workspace_registry(path: str | Path) -> dict:
    data=yaml.safe_load(Path(path).read_text())
    if data.get("status")!="FROZEN" or data.get("ticket")!="M13-006I":
        raise ValueError("M13-006I review workspace registry must be FROZEN")
    if data.get("review_workspace_registry_id")!="STH-M13-006I-REVIEW-WORKSPACE-v1.0":
        raise ValueError("unexpected M13-006I registry id")
    return data


@dataclass(frozen=True)
class ScenarioReviewItem:
    scenario_id: str
    user_order: int
    scenario_context_fingerprint: str
    comparison_member_fingerprint: str
    scenario_explanation_fingerprint: str
    facts: tuple[tuple[str, object], ...]
    assumptions: tuple[tuple[str, object], ...]
    scenario_outputs: tuple[tuple[str, object], ...]
    changed_from_reference: tuple[str, ...]
    evidence_source_fingerprints: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    applicable_pattern_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    item_fingerprint: str


@dataclass(frozen=True)
class ScenarioReviewPackage:
    package_id: str
    community_id: str
    subject_id: str
    review_state: str
    scenario_ids: tuple[str, ...]
    review_items: tuple[ScenarioReviewItem, ...]
    comparison_fingerprint: str
    comparison_explanation_fingerprint: str
    certified_inputs: tuple[str, ...]
    evidence: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    human_decisions: tuple[str, ...]
    package_fingerprint: str


def build_review_item(
    *,
    context: CertifiedScenarioBaseline,
    comparison_member: ScenarioComparisonMember,
    explanation: ScenarioExplanation,
) -> ScenarioReviewItem:
    for label,fp in (
        ("context",context.context_fingerprint),
        ("member",comparison_member.member_fingerprint),
        ("explanation",explanation.explanation_fingerprint),
    ): _validate_fp(fp,f"{label} fingerprint")
    if context.scenario_id!=comparison_member.scenario_id or context.scenario_id!=explanation.scenario_id:
        raise ValueError("scenario identity mismatch")
    if comparison_member.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/member lineage mismatch")
    if explanation.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/explanation lineage mismatch")
    if explanation.comparison_member_fingerprint!=comparison_member.member_fingerprint:
        raise ValueError("member/explanation lineage mismatch")
    if tuple(context.facts)!=tuple(explanation.facts):
        raise ValueError("facts must match certified context")
    if tuple(context.assumptions)!=tuple(explanation.assumptions):
        raise ValueError("assumptions must match certified context")
    payload={
        "scenario_id":context.scenario_id,"user_order":comparison_member.user_order,
        "scenario_context_fingerprint":context.context_fingerprint,
        "comparison_member_fingerprint":comparison_member.member_fingerprint,
        "scenario_explanation_fingerprint":explanation.explanation_fingerprint,
        "facts":tuple(explanation.facts),"assumptions":tuple(explanation.assumptions),
        "scenario_outputs":tuple(comparison_member.dimensions),
        "changed_from_reference":tuple(explanation.changed_from_reference),
        "evidence_source_fingerprints":tuple(explanation.evidence_source_fingerprints),
        "evidence_fingerprints":tuple(explanation.evidence_fingerprints),
        "applicable_pattern_ids":tuple(explanation.applicable_pattern_ids),
        "unknowns":tuple(explanation.unknowns),"limitations":tuple(explanation.limitations),
    }
    return ScenarioReviewItem(**payload,item_fingerprint=_hash(payload))


def assemble_review_package(
    *,
    package_id: str,
    community_id: str,
    subject_id: str,
    contexts: Sequence[CertifiedScenarioBaseline],
    members: Sequence[ScenarioComparisonMember],
    scenario_explanations: Sequence[ScenarioExplanation],
    comparison: MultiScenarioComparison,
    comparison_explanation: ComparisonExplanation,
    registry: Mapping[str, object],
    human_decisions: Sequence[str] = (),
) -> ScenarioReviewPackage:
    if not package_id.strip() or not community_id.strip() or not subject_id.strip():
        raise ValueError("package, community, and subject identities required")
    _validate_fp(comparison.comparison_fingerprint,"comparison fingerprint")
    _validate_fp(comparison_explanation.explanation_fingerprint,"comparison explanation fingerprint")
    if comparison_explanation.comparison_fingerprint!=comparison.comparison_fingerprint:
        raise ValueError("comparison/explanation lineage mismatch")

    by_context={x.scenario_id:x for x in contexts}
    by_member={x.scenario_id:x for x in members}
    by_explanation={x.scenario_id:x for x in scenario_explanations}
    ids=tuple(comparison.scenario_ids)
    if set(by_context)!=set(ids) or set(by_member)!=set(ids) or set(by_explanation)!=set(ids):
        raise ValueError("review package requires exactly one A-H item for each compared scenario")
    if tuple(comparison_explanation.scenario_ids)!=ids:
        raise ValueError("comparison explanation scenario order mismatch")
    if any(x.community_id!=community_id or x.subject_id!=subject_id for x in contexts):
        raise ValueError("review package community/subject mismatch")

    ordered_members=tuple(sorted(members,key=lambda x:x.user_order))
    if tuple(x.scenario_id for x in ordered_members)!=ids:
        raise ValueError("human scenario order must match comparison order")

    items=tuple(build_review_item(context=by_context[s],comparison_member=by_member[s],explanation=by_explanation[s]) for s in ids)
    certified_inputs=tuple(sorted({
        comparison.comparison_fingerprint,comparison_explanation.explanation_fingerprint,
        *(x.scenario_context_fingerprint for x in items),
        *(x.comparison_member_fingerprint for x in items),
        *(x.scenario_explanation_fingerprint for x in items),
    }))
    evidence=tuple(sorted({fp for x in items for fp in (*x.evidence_source_fingerprints,*x.evidence_fingerprints)}))
    unknowns=tuple(sorted(set(comparison_explanation.unknowns)|{u for x in items for u in x.unknowns}))
    limitations=tuple(sorted(set(comparison_explanation.limitations)|{l for x in items for l in x.limitations}|{
        "This package supports human review only; it does not select, rank, recommend, approve, authorize, execute, or publish a scenario."
    }))
    decisions=tuple(x.strip() for x in human_decisions if x.strip())
    payload={
        "package_id":package_id,"community_id":community_id,"subject_id":subject_id,
        "review_state":"READY_FOR_HUMAN_REVIEW","scenario_ids":ids,
        "review_items":tuple(asdict(x) for x in items),
        "comparison_fingerprint":comparison.comparison_fingerprint,
        "comparison_explanation_fingerprint":comparison_explanation.explanation_fingerprint,
        "certified_inputs":certified_inputs,"evidence":evidence,
        "unknowns":unknowns,"limitations":limitations,"human_decisions":decisions,
    }
    return ScenarioReviewPackage(
        package_id=package_id,community_id=community_id,subject_id=subject_id,
        review_state=payload["review_state"],scenario_ids=ids,review_items=items,
        comparison_fingerprint=payload["comparison_fingerprint"],
        comparison_explanation_fingerprint=payload["comparison_explanation_fingerprint"],
        certified_inputs=certified_inputs,evidence=evidence,unknowns=unknowns,
        limitations=limitations,human_decisions=decisions,package_fingerprint=_hash(payload)
    )


def validate_review_package_replay(package: ScenarioReviewPackage, **kwargs) -> bool:
    return assemble_review_package(**kwargs)==package
