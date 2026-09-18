from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml

from src.seller_intelligence.opportunity import (
    GovernedAlternativeInput,
    build_seller_opportunity,
    load_seller_opportunity_registry,
)
from src.seller_intelligence.strategy import (
    GovernedStrategyFinding,
    build_property_seller_strategy,
    load_seller_strategy_registry,
)
from src.seller_intelligence.scenario import (
    ScenarioAssumption,
    evaluate_seller_scenario,
    load_seller_scenario_registry,
)
from src.seller_intelligence.timeline import (
    GovernedTimelineSnapshot,
    build_seller_decision_timeline,
    load_seller_timeline_registry,
)
from src.seller_intelligence.communication import (
    translate_seller_intelligence,
    load_communication_registry,
)
from src.seller_intelligence.workspace import (
    build_seller_intelligence_case,
    load_workspace_registry,
    make_human_decision,
)
from src.seller_intelligence.effectiveness import (
    CalibrationCandidate,
    make_observed_outcome,
    evaluate_effectiveness,
    load_effectiveness_registry,
)
from src.seller_intelligence.calibration import (
    build_accepted_baseline,
    build_fixture,
    build_candidate_version,
    evaluate_candidate,
    load_calibration_registry,
    make_promotion_approval,
)


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class EvidenceReceipt:
    ticket: str
    path: str
    evidence_id: str
    sha256: str
    status: str
    waivers: int
    open_defects: int


@dataclass(frozen=True)
class ProductionCertificationResult:
    status: str
    decision: str
    evidence_receipts: tuple[EvidenceReceipt,...]
    end_to_end_fingerprint: str
    promotion_package_fingerprint: str
    rollback_rule_fingerprint: str
    negative_controls: tuple[str,...]
    blocking_reasons: tuple[str,...]
    production_candidate_root: str
    public_eligible: bool
    external_action_capability: str


def load_production_certification_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_production_certification_id")!="STH-M11-009-PRODUCTION-CERTIFICATION-v1.0":
        raise ValueError("unexpected M11-009 production certification id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-009 registry must be FROZEN v1.0")
    expected=[f"M11-{i:03d}" for i in range(1,9)]
    if list(raw.get("accepted_evidence") or {})!=expected:
        raise ValueError("M11-009 evidence registry must contain exact M11-001 through M11-008 chain")
    return raw


def _verify_evidence(root: Path, registry: Mapping[str,object]):
    receipts=[]
    blocking=[]
    for ticket,rel in registry["accepted_evidence"].items():
        path=root/str(rel)
        if not path.is_file():
            blocking.append(f"{ticket}:EVIDENCE_MISSING")
            continue
        data=json.loads(path.read_text())
        if data.get("ticket")!=ticket:
            blocking.append(f"{ticket}:TICKET_ID_MISMATCH")
        if data.get("status")!="ACCEPTED":
            blocking.append(f"{ticket}:NOT_ACCEPTED")
        waivers=int(data.get("waivers",-1))
        defects=int(data.get("open_defects",-1))
        if waivers!=0:
            blocking.append(f"{ticket}:WAIVERS_PRESENT")
        if defects!=0:
            blocking.append(f"{ticket}:OPEN_DEFECTS_PRESENT")
        receipts.append(EvidenceReceipt(
            ticket=ticket,path=str(rel),evidence_id=str(data.get("evidence_id") or ""),
            sha256=_file_sha(path),status=str(data.get("status") or ""),
            waivers=waivers,open_defects=defects,
        ))
    if len(receipts)!=8:
        blocking.append("EVIDENCE_CHAIN_INCOMPLETE")
    return tuple(receipts),blocking


def _end_to_end(root: Path):
    O=root/"registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
    S=root/"registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
    SC=root/"registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
    T=root/"registries/seller_intelligence/m11-004-seller-decision-timeline-v1.0.yaml"
    C=root/"registries/seller_intelligence/m11-005-communication-translation-v1.0.yaml"
    W=root/"registries/seller_intelligence/m11-006-seller-workspace-v1.0.yaml"
    E=root/"registries/seller_intelligence/m11-007-effectiveness-learning-v1.0.yaml"
    CAL=root/"registries/seller_intelligence/m11-008-calibration-promotion-v1.0.yaml"

    fp1="a"*64; fp2="b"*64; fp3="c"*64; fp4="d"*64; fp5="e"*64; fp6="f"*64

    opp=build_seller_opportunity(
        subject_property_id="CERT-SUBJECT-1",
        alternatives=[
            GovernedAlternativeInput("A-1","CERT-SUBJECT-1","P-1","CLOSE_SUBSTITUTE",True,"PASS","SELLER","CURRENT","1"*64),
            GovernedAlternativeInput("A-2","CERT-SUBJECT-1","P-2","CLOSE_SUBSTITUTE",True,"PASS","SELLER","CURRENT","2"*64),
            GovernedAlternativeInput("A-3","CERT-SUBJECT-1","P-3","BUILDER_ALTERNATIVE",True,"PASS","SELLER","CURRENT","3"*64),
        ],
        registry=load_seller_opportunity_registry(O),
    )
    prior=build_property_seller_strategy(
        opportunity=build_seller_opportunity(subject_property_id="CERT-SUBJECT-1",alternatives=[],registry=load_seller_opportunity_registry(O)),
        m11_001_certified=True,m11_001_evidence_fingerprint=fp1,
        findings=[GovernedStrategyFinding("P-1","CERT-SUBJECT-1","BUYER_DEPTH","DEEP","Prior depth",True,"PASS","SELLER","CURRENT","4"*64)],
        registry=load_seller_strategy_registry(S),
    )
    strat=build_property_seller_strategy(
        opportunity=opp,m11_001_certified=True,m11_001_evidence_fingerprint=fp1,
        findings=[
            GovernedStrategyFinding("F-1","CERT-SUBJECT-1","BUYER_DEPTH","THIN","Current depth",True,"PASS","SELLER","CURRENT","5"*64),
            GovernedStrategyFinding("F-2","CERT-SUBJECT-1","VERIFIED_DIFFERENTIATION","LIMITED","Current differentiation",True,"PASS","SELLER","CURRENT","6"*64),
            GovernedStrategyFinding("F-3","CERT-SUBJECT-1","NEW_CONSTRUCTION_PRESSURE","HIGH","Current construction pressure",True,"PASS","SELLER","CURRENT","7"*64),
            GovernedStrategyFinding("F-4","CERT-SUBJECT-1","PRICING_RESPONSE_ENVIRONMENT","WEAK","Current response environment",True,"PASS","SELLER","CURRENT","8"*64),
            GovernedStrategyFinding("F-5","CERT-SUBJECT-1","WEEK_OVER_WEEK_DIRECTION","WORSENING","Current direction",True,"PASS","SELLER","CURRENT","9"*64),
        ],
        registry=load_seller_strategy_registry(S),
    )
    scen=evaluate_seller_scenario(
        scenario_id="CERT-SCENARIO",strategy=strat,m11_002_certified=True,m11_002_evidence_fingerprint=fp2,
        assumptions=[ScenarioAssumption("H-1","CERT-SUBJECT-1","BUYER_DEPTH","DEEP","Controlled what-if",True)],
        registry=load_seller_scenario_registry(SC),
    )
    timeline=build_seller_decision_timeline(
        snapshots=[
            GovernedTimelineSnapshot("S-1","2026-09-01T09:00:00-07:00",prior,True,"a1"*32),
            GovernedTimelineSnapshot("S-2","2026-09-08T09:00:00-07:00",strat,True,"a2"*32,scen,True,fp3),
        ],
        registry=load_seller_timeline_registry(T),
    )
    comm=translate_seller_intelligence(
        audience="SELLER",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,
        m11_001_evidence_fingerprint=fp1,m11_002_evidence_fingerprint=fp2,m11_003_evidence_fingerprint=fp3,
        m11_004_evidence_fingerprint=fp4,registry=load_communication_registry(C),
    )
    review_item="REVIEW-S-2-REVIEW"
    decision=make_human_decision(
        decision_id="D-1",review_item_id=review_item,decision_type="ACKNOWLEDGE_REVIEW",
        actor_id="CERT-HUMAN",decided_at="2026-09-08T10:00:00-07:00",rationale="Certification review",
        registry=load_workspace_registry(W),
    )
    case=build_seller_intelligence_case(
        case_id="CERT-CASE",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,communication=comm,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,m11_005_certified=True,
        m11_001_evidence_fingerprint=fp1,m11_002_evidence_fingerprint=fp2,m11_003_evidence_fingerprint=fp3,
        m11_004_evidence_fingerprint=fp4,m11_005_evidence_fingerprint=fp5,
        human_decisions=[decision],registry=load_workspace_registry(W),
    )
    outcome=make_observed_outcome(
        outcome_id="O-1",subject_property_id="CERT-SUBJECT-1",outcome_type="MARKET_RESPONSE",
        outcome_state="WORSENED",observed_at="2026-09-15T09:00:00-07:00",
        source_fingerprint="ab"*32,notes="Certified historical outcome",
        registry=load_effectiveness_registry(E),
    )
    learning=evaluate_effectiveness(
        case=case,timeline=timeline,m11_004_certified=True,m11_004_evidence_fingerprint=fp4,
        m11_006_certified=True,m11_006_evidence_fingerprint=fp6,
        outcomes=[outcome],registry=load_effectiveness_registry(E),
    )
    advisory=[x for x in learning.calibration_candidates if x.candidate_type=="REVIEW_CONDITION_CALIBRATION"][0]
    calreg=load_calibration_registry(CAL)
    baseline=build_accepted_baseline(calreg)
    candidate=build_candidate_version(
        candidate_id="CERT-CANDIDATE-v1",advisory_candidate=advisory,baseline=baseline,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=calreg,
    )
    fixtures=[
        build_fixture(
            fixture_id="HF-1",competitive_pressure="HIGH",buyer_depth="THIN",
            pricing_response_environment="WEAK",new_construction_pressure="HIGH",
            verified_differentiation="LIMITED",week_over_week_direction="WORSENING",protected_behavior=True,
        ),
        build_fixture(
            fixture_id="HF-2",competitive_pressure="LOW",buyer_depth="DEEP",
            pricing_response_environment="MIXED",new_construction_pressure="LOW",
            verified_differentiation="STRONG",week_over_week_direction="STABLE",protected_behavior=False,
        ),
    ]
    approval=make_promotion_approval(
        approval_id="CERT-APPROVAL",candidate_rule_fingerprint=candidate.rule_fingerprint,
        authority_id="CERT-HUMAN",status="APPROVED",
    )
    calibration=evaluate_candidate(
        baseline=baseline,candidate=candidate,fixtures=fixtures,registry=calreg,approval=approval
    )
    if calibration.promotion_package is None:
        raise ValueError("M11-008 promotion package missing")
    package=calibration.promotion_package

    for obj in (opp,strat,scen,timeline,comm,case,learning):
        if getattr(obj,"public_eligible",False) is not False:
            raise ValueError("public leakage boundary failed")
        if getattr(obj,"external_action_capability","NONE")!="NONE":
            raise ValueError("external action boundary failed")
    if comm.audience!="SELLER" or comm.output_tier!="SELLER":
        raise ValueError("seller communication tier boundary failed")
    if case.output_tier!="INTERNAL" or learning.output_tier!="INTERNAL":
        raise ValueError("internal-only workspace/learning boundary failed")
    if package.public_eligible is not False or package.external_action_capability!="NONE":
        raise ValueError("promotion package boundary failed")
    if package.rollback_rule_fingerprint!=baseline.rule_fingerprint:
        raise ValueError("rollback fingerprint mismatch")

    payload={
        "opportunity":opp.result_fingerprint,
        "strategy":strat.strategy_fingerprint,
        "scenario":scen.scenario_fingerprint,
        "timeline":timeline.timeline_fingerprint,
        "communication":comm.projection_fingerprint,
        "workspace":case.case_fingerprint,
        "learning":learning.learning_fingerprint,
        "calibration":calibration.evaluation_fingerprint,
        "promotion_package":package.package_fingerprint,
        "rollback_rule_fingerprint":package.rollback_rule_fingerprint,
    }
    return _hash(payload), package.package_fingerprint, package.rollback_rule_fingerprint


def _negative_controls(root: Path) -> tuple[str,...]:
    passed=[]
    O=load_seller_opportunity_registry(root/"registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml")
    try:
        build_seller_opportunity(
            subject_property_id="NEG",
            alternatives=[GovernedAlternativeInput("A","NEG","P","CLOSE_SUBSTITUTE",False,"PASS","SELLER","CURRENT","1"*64)],
            registry=O,
        )
    except ValueError:
        passed.append("UNCERTIFIED_INPUT_FAILS_CLOSED")
    C=load_communication_registry(root/"registries/seller_intelligence/m11-005-communication-translation-v1.0.yaml")
    if C["governance"]["public_audience_prohibited"] is True:
        passed.append("PUBLIC_STRATEGY_LEAKAGE_PROHIBITED")
    CAL=load_calibration_registry(root/"registries/seller_intelligence/m11-008-calibration-promotion-v1.0.yaml")
    base=build_accepted_baseline(CAL)
    fake=CalibrationCandidate(
        candidate_id="NEG-CAL",candidate_type="REVIEW_CONDITION_CALIBRATION",outcome_id="O",
        rationale="negative control",advisory_only=True,promotion_status="NOT_PROMOTED",
        source_fingerprints=("1"*64,),candidate_fingerprint="2"*64,
    )
    bad=build_candidate_version(
        candidate_id="NEG-CAND",advisory_candidate=fake,baseline=base,
        rule_changes={"DAY_14_ALWAYS_REVIEW_ENABLED":False},registry=CAL,
    )
    ev=evaluate_candidate(
        baseline=base,candidate=bad,
        fixtures=[build_fixture(
            fixture_id="NEG-F",competitive_pressure="LOW",buyer_depth="DEEP",
            pricing_response_environment="RESPONSIVE",new_construction_pressure="LOW",
            verified_differentiation="STRONG",week_over_week_direction="STABLE",protected_behavior=True,
        )],
        registry=CAL,
    )
    if ev.regression_count>0 and ev.promotion_package is None:
        passed.append("REGRESSION_BLOCKS_PROMOTION")
    return tuple(sorted(passed))


def execute_production_certification(
    *,
    repository_root: str|Path,
    registry: Mapping[str,object],
) -> ProductionCertificationResult:
    root=Path(repository_root)
    if (root/"VERSION").read_text().strip()!=str(registry["production_candidate_version"]):
        raise ValueError("M11-009 production candidate version mismatch")

    receipts,blocking=_verify_evidence(root,registry)
    try:
        end_fp,pkg_fp,rollback_fp=_end_to_end(root)
    except Exception as exc:
        end_fp=""
        pkg_fp=""
        rollback_fp=""
        blocking.append(f"END_TO_END_REPLAY_FAILED:{type(exc).__name__}")

    neg=_negative_controls(root)
    required={
        "UNCERTIFIED_INPUT_FAILS_CLOSED",
        "PUBLIC_STRATEGY_LEAKAGE_PROHIBITED",
        "REGRESSION_BLOCKS_PROMOTION",
    }
    if set(neg)!=required:
        blocking.append("NEGATIVE_CONTROL_COVERAGE_INCOMPLETE")

    blocking_tuple=tuple(sorted(set(blocking)))
    payload={
        "evidence":[{"ticket":x.ticket,"sha256":x.sha256} for x in receipts],
        "end_to_end_fingerprint":end_fp,
        "promotion_package_fingerprint":pkg_fp,
        "rollback_rule_fingerprint":rollback_fp,
        "negative_controls":neg,
        "blocking_reasons":blocking_tuple,
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    root_fp=_hash(payload)
    expected=str(registry.get("expected_production_candidate_root") or "")
    if expected and root_fp!=expected:
        blocking.append("PRODUCTION_CANDIDATE_ROOT_MISMATCH")
        blocking_tuple=tuple(sorted(set(blocking)))
    passed=not blocking_tuple
    return ProductionCertificationResult(
        status="PASS" if passed else "FAIL",
        decision=registry["decision_values"]["pass"] if passed else registry["decision_values"]["fail"],
        evidence_receipts=receipts,
        end_to_end_fingerprint=end_fp,
        promotion_package_fingerprint=pkg_fp,
        rollback_rule_fingerprint=rollback_fp,
        negative_controls=neg,
        blocking_reasons=blocking_tuple,
        production_candidate_root=root_fp,
        public_eligible=False,
        external_action_capability="NONE",
    )
