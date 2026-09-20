import json
from pathlib import Path
import yaml

EVIDENCE = {
    "M13-007A": "certification-evidence/m13-007a/unified-intelligence-governance-acceptance-v1.0.json",
    "M13-007B": "certification-evidence/m13-007b/cross-system-binding-acceptance-v1.0.json",
    "M13-007C": "certification-evidence/m13-007c/seller-relevance-acceptance-v1.0.json",
    "M13-007D": "certification-evidence/m13-007d/current-unified-state-acceptance-v1.0.json",
    "M13-007E": "certification-evidence/m13-007e/state-delta-acceptance-v1.0.json",
    "M13-007F": "certification-evidence/m13-007f/usability-framework-acceptance-v1.0.json",
    "M13-007G": "certification-evidence/m13-007g/seller-decision-brief-acceptance-v1.0.json",
}
EXPECTED_PARENTS = {
    "M13-007B": "M13-007A",
    "M13-007C": "M13-007B",
    "M13-007D": "M13-007C",
    "M13-007E": "M13-007D",
    "M13-007F": "M13-007E",
    "M13-007G": "M13-007F",
}
REQUIREMENTS = (
    "deterministic_same_inputs_same_state",
    "complete_intelligence_lineage",
    "facts_assumptions_distinct",
    "historical_remains_historical",
    "scenario_assumptions_remain_assumptions",
    "promoted_patterns_not_predictions",
    "unknowns_explicit",
    "stale_not_silently_current",
    "conflicts_surfaced",
    "applicability_property_specific_reproducible",
    "no_unrelated_intelligence_leakage",
    "prior_state_comparison_exact",
    "material_changes_describe_evidence_change_only",
    "no_seller_motivation_inference",
    "no_list_price_selection",
    "no_scenario_ranking",
    "no_future_outcome_prediction",
    "no_hidden_seller_or_opportunity_score",
    "no_m12_execution_trigger",
    "human_review_does_not_mutate_analytics",
    "clean_replay_reproduces_hashes",
    "zero_waivers",
    "zero_unresolved_blocking_defects",
    "complete_executable_requirement_coverage",
)

def load(path): return json.loads(Path(path).read_text())

def registry():
    return yaml.safe_load(Path("registries/community_temporal_state/m13-007h-final-certification-v1.0.yaml").read_text())

def test_a_to_g_acceptance_evidence_is_present_and_clean():
    for ticket,path in EVIDENCE.items():
        p=Path(path)
        assert p.exists(), f"missing {ticket} evidence"
        e=load(path)
        assert e["ticket"]==ticket
        assert e["status"]=="ACCEPTED"
        assert e["waivers"]==0
        assert e["open_defects"]==0
        assert e["tests"]["failed"]==0

def test_a_to_g_parent_chain_is_exact():
    for ticket,parent in EXPECTED_PARENTS.items():
        assert load(EVIDENCE[ticket])["parent"]["ticket"]==parent

def test_final_registry_is_frozen_binary_and_complete():
    r=registry()
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-007H" and r["subsystem"]=="M13-007"
    assert r["decision_values"]==["PASS / GO","FAIL / NO-GO"]
    assert r["conditional_pass_allowed"] is False
    assert r["required_tickets"]==list(EVIDENCE)
    assert tuple(r["acceptance_requirements"])==REQUIREMENTS
    assert all(r["policy"].values())

def test_build_manifest_is_on_h_and_m13_remains_in_progress():
    b=yaml.safe_load(Path("BUILD-MANIFEST.yaml").read_text())
    assert b["current_ticket"]=="M13-007H"
    states={x["id"]:x["status"] for x in b["milestones"]}
    assert states["M12"]=="ACCEPTED"
    assert states["M13"]=="IN_PROGRESS"

def test_no_m13_007i_exists():
    assert not any("M13-007I" in str(p) for p in Path(".").rglob("*"))
    backlog=Path("IMPLEMENTATION-BACKLOG.yaml")
    if backlog.exists():
        data=yaml.safe_load(backlog.read_text())
        tickets=data.get("tickets",[]) if isinstance(data,dict) else []
        assert all(x.get("ticket_id")!="M13-007I" for x in tickets if isinstance(x,dict))

def test_all_frozen_requirements_have_executable_coverage():
    mapping={
      "deterministic_same_inputs_same_state":["M13-007A","M13-007D"],
      "complete_intelligence_lineage":["M13-007A","M13-007B","M13-007G"],
      "facts_assumptions_distinct":["M13-007A"],
      "historical_remains_historical":["M13-007A","M13-007B"],
      "scenario_assumptions_remain_assumptions":["M13-007A","M13-007B"],
      "promoted_patterns_not_predictions":["M13-007A","M13-007B"],
      "unknowns_explicit":["M13-007A","M13-007C","M13-007D","M13-007F","M13-007G"],
      "stale_not_silently_current":["M13-007B","M13-007D","M13-007F"],
      "conflicts_surfaced":["M13-007B","M13-007F"],
      "applicability_property_specific_reproducible":["M13-007C"],
      "no_unrelated_intelligence_leakage":["M13-007C","M13-007D"],
      "prior_state_comparison_exact":["M13-007E"],
      "material_changes_describe_evidence_change_only":["M13-007E"],
      "no_seller_motivation_inference":["M13-007A","M13-007C"],
      "no_list_price_selection":["M13-007A","M13-007G"],
      "no_scenario_ranking":["M13-007A","M13-007G"],
      "no_future_outcome_prediction":["M13-007A","M13-007G"],
      "no_hidden_seller_or_opportunity_score":["M13-007A","M13-007C","M13-007G"],
      "no_m12_execution_trigger":["M13-007A","M13-007C","M13-007F","M13-007G"],
      "human_review_does_not_mutate_analytics":["M13-007G"],
      "clean_replay_reproduces_hashes":["M13-007A","M13-007B","M13-007C","M13-007D","M13-007E","M13-007F","M13-007G"],
      "zero_waivers":list(EVIDENCE),
      "zero_unresolved_blocking_defects":list(EVIDENCE),
      "complete_executable_requirement_coverage":list(EVIDENCE),
    }
    assert set(mapping)==set(REQUIREMENTS)
    assert all(v and all(ticket in EVIDENCE for ticket in v) for v in mapping.values())

def test_g_is_human_review_assembly_not_decision_engine():
    doc=Path("docs/implementation/M13-007G.md").read_text()
    assert "Status: ACCEPTED" in doc
    for phrase in ("no new analytics","recommend a list price","pricing strategy","generate actions","predict outcomes","rank scenarios","score sellers"):
        assert phrase.lower() in doc.lower()

def test_final_evidence_if_present_is_clean_and_complete():
    path=Path("certification-evidence/m13-007h/final-certification-v1.0.json")
    if not path.exists():
        return
    e=load(path)
    assert e["ticket"]=="M13-007H" and e["subsystem"]=="M13-007"
    assert e["status"]=="ACCEPTED" and e["decision"]=="PASS / GO"
    assert e["tests"]["certification_tests_passed"]==8
    assert e["tests"]["governing_a_g_tests_passed"]==78
    assert e["tests"]["m13_temporal_state_total_passed"]==329
    assert e["tests"]["inherited_m12_passed"]==137
    assert e["tests"]["failed"]==0
    assert e["waivers"]==0 and e["open_defects"]==0 and e["unresolved_blocking_defects"]==0
    assert e["conditional_pass_allowed"] is False
    assert e["m13_007i_exists"] is False
    assert len(e["requirement_traceability_matrix"])==24
    assert all(x["covered"] is True for x in e["requirement_traceability_matrix"])
    assert len(e["certification_root_hash"])==64
    assert all(x["conclusion"]=="success" for x in e["github_workflow_runs"])
