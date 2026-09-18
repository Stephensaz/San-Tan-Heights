from copy import deepcopy
import json
from pathlib import Path
import shutil

from src.listing_execution.operational_certification import (
    certify_operational_audit,
    load_operational_certification_registry,
)

R="registries/listing_execution/m12-008-operational-certification-v1.0.yaml"

def reg():
    return load_operational_certification_registry(R)

def certify(root="."):
    return certify_operational_audit(repository_root=root,registry=reg())

def copy_audit_repo(tmp_path):
    r=reg()
    for rel in list(r["accepted_evidence"].values()):
        src=Path(rel); dst=tmp_path/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    for manifest in r["artifact_manifest"].values():
        for rel in manifest.values():
            src=Path(rel); dst=tmp_path/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    return tmp_path

def test_operational_certification_is_ready_for_m12_009_not_final_decision():
    x=certify()
    assert x.status=="READY_FOR_M12_009"
    assert x.blocking_gaps==()
    assert x.final_milestone_decision_issued is False
    assert x.public_eligible is False
    assert x.external_action_capability=="NONE"
    assert x.evidence_chain_root=="82bb94798f887e5b7115abbac55c6b6e9e0cae3130f2310d1efab1ba0dbfe92c"
    assert x.artifact_manifest_root=="6e411dfccac19bfc0fdad22011307e507bc120a2d3a568e09ffd74364956a315"
    assert x.operational_certification_root=="700b426fdf8b576c0522fce216f3af2e1853fd7d851c0dc4ebb80089824f7b84"
    assert x.evidence_chain_root=="82bb94798f887e5b7115abbac55c6b6e9e0cae3130f2310d1efab1ba0dbfe92c"
    assert x.artifact_manifest_root=="6e411dfccac19bfc0fdad22011307e507bc120a2d3a568e09ffd74364956a315"
    assert x.operational_certification_root=="700b426fdf8b576c0522fce216f3af2e1853fd7d851c0dc4ebb80089824f7b84"

def test_exact_seven_ticket_evidence_chain_and_twenty_one_artifacts():
    x=certify()
    assert [r.ticket for r in x.evidence_receipts]==[f"M12-{i:03d}" for i in range(1,8)]
    assert len(x.artifact_receipts)==21

def test_certification_roots_are_deterministic():
    a=certify(); b=certify()
    assert a.evidence_chain_root==b.evidence_chain_root
    assert a.artifact_manifest_root==b.artifact_manifest_root
    assert a.operational_certification_root==b.operational_certification_root

def test_zero_waivers_and_zero_defects_required(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-004"]
    data=json.loads(p.read_text()); data["waivers"]=1; data["open_defects"]=2; p.write_text(json.dumps(data))
    x=certify(root)
    assert "M12-004:WAIVERS_PRESENT" in x.blocking_gaps
    assert "M12-004:OPEN_DEFECTS_PRESENT" in x.blocking_gaps
    assert x.status=="BLOCKED"

def test_false_declared_capability_is_blocking_gap(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-002"]
    data=json.loads(p.read_text()); key=next(iter(data["capabilities"])); data["capabilities"][key]=False; p.write_text(json.dumps(data))
    x=certify(root)
    assert any(g.startswith("M12-002:CAPABILITY_NOT_TRUE:") for g in x.blocking_gaps)

def test_control_contradiction_is_blocking_gap(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-006"]
    data=json.loads(p.read_text()); data["controls"]["execution_capability_prohibited"]=False; p.write_text(json.dumps(data))
    x=certify(root)
    assert "M12-006:CONTROL_NOT_TRUE:execution_capability_prohibited" in x.blocking_gaps

def test_public_eligible_must_remain_false(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-004"]
    data=json.loads(p.read_text()); data["controls"]["public_eligible"]=True; p.write_text(json.dumps(data))
    x=certify(root)
    assert "M12-004:CONTROL_EXPECTED_FALSE:public_eligible" in x.blocking_gaps

def test_external_action_capability_must_remain_none(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-004"]
    data=json.loads(p.read_text()); data["controls"]["external_action_capability"]="EXECUTE"; p.write_text(json.dumps(data))
    x=certify(root)
    assert "M12-004:CONTROL_VALUE_MISMATCH:external_action_capability" in x.blocking_gaps

def test_parent_chain_break_is_blocking_gap(tmp_path):
    root=copy_audit_repo(tmp_path)
    p=root/reg()["accepted_evidence"]["M12-007"]
    data=json.loads(p.read_text()); data["parent"]["ticket"]="M12-005"; p.write_text(json.dumps(data))
    x=certify(root)
    assert "M12-007:PARENT_TICKET_MISMATCH" in x.blocking_gaps

def test_missing_evidence_is_blocking_gap(tmp_path):
    root=copy_audit_repo(tmp_path)
    (root/reg()["accepted_evidence"]["M12-003"]).unlink()
    x=certify(root)
    assert "M12-003:EVIDENCE_MISSING" in x.blocking_gaps
    assert "M12_EVIDENCE_CHAIN_INCOMPLETE" in x.blocking_gaps

def test_missing_implementation_artifact_is_blocking_gap(tmp_path):
    root=copy_audit_repo(tmp_path)
    rel=reg()["artifact_manifest"]["M12-005"]["implementation"]
    (root/rel).unlink()
    x=certify(root)
    assert "M12-005:IMPLEMENTATION_MISSING" in x.blocking_gaps
    assert "M12_ARTIFACT_MANIFEST_INCOMPLETE" in x.blocking_gaps

def test_tampered_artifact_changes_manifest_and_package_roots(tmp_path):
    baseline=certify()
    root=copy_audit_repo(tmp_path)
    rel=reg()["artifact_manifest"]["M12-006"]["implementation"]
    p=root/rel; p.write_text(p.read_text()+"\n# tamper\n")
    x=certify(root)
    assert x.artifact_manifest_root!=baseline.artifact_manifest_root
    assert x.operational_certification_root!=baseline.operational_certification_root

def test_package_never_issues_final_milestone_decision():
    r=deepcopy(reg())
    assert r["package"]["final_milestone_decision_issued"] is False
    x=certify()
    assert x.final_milestone_decision_issued is False
    assert x.status!="PASS"
    assert x.status!="GO"


def test_wrong_frozen_root_fails_closed():
    r=deepcopy(reg())
    r["package"]["expected_evidence_chain_root"]="0"*64
    x=certify_operational_audit(repository_root=".",registry=r)
    assert x.status=="BLOCKED"
    assert "M12_EVIDENCE_CHAIN_ROOT_MISMATCH" in x.blocking_gaps


def test_wrong_frozen_evidence_root_blocks_package():
    r=deepcopy(reg()); r["expected_roots"]["evidence_chain_root"]="0"*64
    x=certify_operational_audit(repository_root=".",registry=r)
    assert x.status=="BLOCKED"
    assert "M12_EVIDENCE_CHAIN_ROOT_MISMATCH" in x.blocking_gaps

def test_wrong_frozen_artifact_root_blocks_package():
    r=deepcopy(reg()); r["expected_roots"]["artifact_manifest_root"]="0"*64
    x=certify_operational_audit(repository_root=".",registry=r)
    assert x.status=="BLOCKED"
    assert "M12_ARTIFACT_MANIFEST_ROOT_MISMATCH" in x.blocking_gaps
