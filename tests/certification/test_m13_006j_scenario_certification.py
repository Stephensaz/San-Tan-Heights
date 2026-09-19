import json
from pathlib import Path
import yaml

EVIDENCE = {
    "M13-006A": "certification-evidence/m13-006a/scenario-governance-acceptance-v1.0.json",
    "M13-006B": "certification-evidence/m13-006b/certified-baseline-acceptance-v1.0.json",
    "M13-006C": "certification-evidence/m13-006c/scenario-evidence-acceptance-v1.0.json",
    "M13-006D": "certification-evidence/m13-006d/pricing-timing-acceptance-v1.0.json",
    "M13-006E": "certification-evidence/m13-006e/buyer-substitution-acceptance-v1.0.json",
    "M13-006F": "certification-evidence/m13-006f/new-construction-acceptance-v1.0.json",
    "M13-006G": "certification-evidence/m13-006g/scenario-comparison-acceptance-v1.0.json",
    "M13-006H": "certification-evidence/m13-006h/explainability-acceptance-v1.0.json",
    "M13-006I": "certification-evidence/m13-006i/review-workspace-acceptance-v1.0.json",
}

def load(path): return json.loads(Path(path).read_text())

def test_all_a_to_i_acceptance_evidence_is_present_and_clean():
    for ticket,path in EVIDENCE.items():
        p=Path(path)
        assert p.exists(), f"missing {ticket} evidence"
        e=load(path)
        assert e["ticket"]==ticket
        assert e["status"]=="ACCEPTED"
        assert e["waivers"]==0
        assert e["open_defects"]==0
        assert e["tests"]["failed"]==0

def test_corrected_i_is_the_governing_i_boundary():
    e=load(EVIDENCE["M13-006I"])
    assert e["evidence_id"]=="STH-M13-006I-REVIEW-WORKSPACE-v1.0"
    assert e["corrective_replacement_of"]=="STH-SCENARIO-PRESENTATION-CONTRACTS"
    doc=Path("docs/implementation/M13-006I.md").read_text()
    assert "Governed Scenario Review Workspace" in doc
    assert "Status: ACCEPTED" in doc

def test_a_to_i_parent_chain_is_ordered():
    expected={
      "M13-006B":"M13-006A","M13-006C":"M13-006B","M13-006D":"M13-006C",
      "M13-006E":"M13-006D","M13-006F":"M13-006E","M13-006G":"M13-006F",
      "M13-006H":"M13-006G","M13-006I":"M13-006H",
    }
    for ticket,parent in expected.items():
        assert load(EVIDENCE[ticket])["parent"]["ticket"]==parent

def test_build_manifest_is_on_j_and_m13_remains_in_progress():
    b=yaml.safe_load(Path("BUILD-MANIFEST.yaml").read_text())
    assert b["current_ticket"]=="M13-006J"
    states={x["id"]:x["status"] for x in b["milestones"]}
    assert states["M12"]=="ACCEPTED"
    assert states["M13"]=="IN_PROGRESS"

def test_no_m13_006k_exists():
    assert not any("M13-006K" in str(p) for p in Path(".").rglob("*"))
    backlog=Path("IMPLEMENTATION-BACKLOG.yaml")
    if backlog.exists():
        data=yaml.safe_load(backlog.read_text())
        tickets=data.get("tickets",[]) if isinstance(data,dict) else []
        assert all(x.get("ticket_id")!="M13-006K" for x in tickets if isinstance(x,dict))

def test_governing_i_contract_has_all_frozen_prohibitions():
    manifest=yaml.safe_load(Path("CONTRACT-MANIFEST.yaml").read_text())
    row=[x for x in manifest["contracts"] if x["id"]=="STH-SCENARIO-REVIEW-WORKSPACE"][0]
    c=yaml.safe_load(Path(row["path"]).read_text())
    required={
      "ranking_prohibited","recommendation_prohibited","winner_selection_prohibited",
      "hidden_utility_score_prohibited","list_price_selection_prohibited","prediction_prohibited",
      "execution_prohibited","publication_prohibited","analytical_artifact_mutation_prohibited",
      "silent_refresh_prohibited",
    }
    assert required.issubset(c["hard_boundaries"])
    assert all(c["hard_boundaries"][x] is True for x in required)

def test_final_certification_document_declares_binary_decision_only():
    doc=Path("docs/implementation/M13-006J.md").read_text()
    assert "PASS / GO" in doc and "FAIL / NO-GO" in doc
    assert "CONDITIONAL PASS" in doc
    assert "prohibited" in doc.lower()


def test_final_m13_006j_evidence_if_present_is_clean():
    path=Path("certification-evidence/m13-006j/final-certification-v1.0.json")
    if not path.exists():
        return
    e=json.loads(path.read_text())
    assert e["ticket"]=="M13-006J"
    assert e["subsystem"]=="M13-006"
    assert e["status"]=="ACCEPTED"
    assert e["decision"]=="PASS / GO"
    assert e["governing_i"]["evidence"]=="certification-evidence/m13-006i/review-workspace-acceptance-v1.0.json"
    assert e["tests"]["certification_tests_passed"]==7
    assert e["tests"]["governing_scenario_tests_passed"]==153
    assert e["tests"]["m13_temporal_state_total_passed"]==251
    assert e["tests"]["inherited_m12_passed"]==137
    assert e["tests"]["failed"]==0
    assert e["checks"]["total"]==31
    assert e["checks"]["successful"]==31
    assert e["checks"]["failed"]==0
    assert e["waivers"]==0
    assert e["open_defects"]==0
    assert e["unresolved_blocking_defects"]==0
    assert e["conditional_pass_allowed"] is False
    assert e["m13_006k_exists"] is False
    assert len(e["certification_root_hash"])==64
    assert all(x["conclusion"]=="success" for x in e["github_checks"])
