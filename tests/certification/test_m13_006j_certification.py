import json
from dataclasses import fields
from pathlib import Path

from src.community_temporal_state.scenario_governance import ScenarioContract
from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import PricingTimingScenarioState
from src.community_temporal_state.scenario_buyer_substitution import BuyerSubstitutionCompetitiveState
from src.community_temporal_state.scenario_new_construction import NewConstructionScenarioState
from src.community_temporal_state.scenario_comparison import MultiScenarioComparison
from src.community_temporal_state.scenario_explainability import ScenarioExplanation, ComparisonExplanation
from src.community_temporal_state.scenario_review_workspace import ScenarioReviewPackage, HumanReviewReceipt

EVIDENCE = (
    ("M13-006A","certification-evidence/m13-006a/scenario-governance-acceptance-v1.0.json","M13-005"),
    ("M13-006B","certification-evidence/m13-006b/certified-baseline-acceptance-v1.0.json","M13-006A"),
    ("M13-006C","certification-evidence/m13-006c/scenario-evidence-acceptance-v1.0.json","M13-006B"),
    ("M13-006D","certification-evidence/m13-006d/pricing-timing-acceptance-v1.0.json","M13-006C"),
    ("M13-006E","certification-evidence/m13-006e/buyer-substitution-acceptance-v1.0.json","M13-006D"),
    ("M13-006F","certification-evidence/m13-006f/new-construction-acceptance-v1.0.json","M13-006E"),
    ("M13-006G","certification-evidence/m13-006g/scenario-comparison-acceptance-v1.0.json","M13-006F"),
    ("M13-006H","certification-evidence/m13-006h/explainability-acceptance-v1.0.json","M13-006G"),
    ("M13-006I","certification-evidence/m13-006i/review-workspace-acceptance-v1.0.json","M13-006H"),
)

def load(path):
    return json.loads(Path(path).read_text())

def test_full_a_to_i_acceptance_chain_is_closed():
    for ticket,path,parent in EVIDENCE:
        e=load(path)
        assert e["ticket"]==ticket
        assert e["status"]=="ACCEPTED"
        assert e["parent"]["ticket"]==parent
        assert e["waivers"]==0
        assert e["open_defects"]==0
        assert e["tests"]["failed"]==0
        assert e["checks"]["failed"]==0
        assert e["checks"]["successful"]==e["checks"]["total"]

def test_corrected_i_is_the_governing_i_boundary():
    e=load(EVIDENCE[-1][1])
    assert e["evidence_id"]=="STH-M13-006I-REVIEW-WORKSPACE-v1.0"
    assert e["corrective_replacement_of"]=="STH-SCENARIO-PRESENTATION-CONTRACTS"
    assert Path("contracts/community_temporal_state/STH-SCENARIO-REVIEW-WORKSPACE-v1.0.yaml").exists()

def test_old_presentation_acceptance_is_not_j_dependency():
    paths={p for _,p,_ in EVIDENCE}
    assert "certification-evidence/m13-006i/presentation-contracts-acceptance-v1.0.json" not in paths

def test_no_decision_or_execution_fields_across_a_to_i_contracts():
    forbidden={
        "rank","winner","recommended_action","recommended_price","recommendation",
        "utility_score","seller_score","prediction","predicted_price","sale_probability",
        "execute","execution_state","selected_scenario","best_scenario"
    }
    classes=(
        ScenarioContract,CertifiedScenarioBaseline,ScenarioEvidenceSet,PricingTimingScenarioState,
        BuyerSubstitutionCompetitiveState,NewConstructionScenarioState,MultiScenarioComparison,
        ScenarioExplanation,ComparisonExplanation,ScenarioReviewPackage,HumanReviewReceipt,
    )
    for cls in classes:
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)

def test_j_has_exactly_nine_governing_acceptance_dependencies():
    assert len(EVIDENCE)==9
    assert [t for t,_,_ in EVIDENCE]==[f"M13-006{x}" for x in "ABCDEFGHI"]

def test_every_governing_evidence_file_has_successful_github_checks():
    for _,path,_ in EVIDENCE:
        e=load(path)
        checks=e.get("github_checks") or e.get("github_actions")
        assert checks
        if isinstance(checks,list):
            assert all(x["conclusion"]=="success" for x in checks)
        else:
            assert all(x["conclusion"]=="success" for x in checks.values())

def test_no_m13_006k_artifact_exists():
    roots=(Path("docs"),Path("src"),Path("tests"),Path("contracts"),Path("registries"),Path("certification-evidence"),Path(".github/workflows"))
    hits=[]
    for root in roots:
        if not root.exists(): continue
        for p in root.rglob("*"):
            if "006k" in p.name.lower():
                hits.append(str(p))
    assert hits==[]
