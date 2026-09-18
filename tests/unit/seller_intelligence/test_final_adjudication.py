from copy import deepcopy
import json
from pathlib import Path
import pytest

from src.seller_intelligence.final_adjudication import (
    execute_final_adjudication,
    load_final_adjudication_registry,
)

R="registries/seller_intelligence/m11-010-final-adjudication-v1.0.yaml"


def reg():
    return load_final_adjudication_registry(R)


def adjudicate(r=None):
    return execute_final_adjudication(repository_root=".",registry=r or reg())


def test_exact_m11_001_through_009_evidence_chain_registered():
    assert list(reg()["accepted_evidence"])==[f"M11-{i:03d}" for i in range(1,10)]


def test_final_adjudication_reproduces_production_candidate_and_passes():
    result=adjudicate()
    assert result.status=="PASS"
    assert result.decision=="SELLER INTELLIGENCE RELEASED"
    assert result.blocking_reasons==()
    assert result.production_candidate_root=="2cca3529c4b09b0a3dc4305b9b7c1732b894fc47018dc971cfe18a98c8e269dd"
    assert result.end_to_end_fingerprint=="5ac8c31d25d700a5b54639b39a1c8b91d17600784ad9fa83301c0b232f01b91b"
    assert result.promotion_package_fingerprint=="32028acf0d636fbd82a511fdceea1d5d567968bbe5714991e8ab9613125fbca6"
    assert result.rollback_rule_fingerprint=="2f39d3fa387ce45c7fe22d8b79f7c92effb47642ecb4a8a111a069b03051aae2"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"
    assert result.certification_root_hash=="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"


def test_final_certification_root_is_deterministic():
    assert adjudicate().certification_root_hash==adjudicate().certification_root_hash


def test_all_prior_evidence_accepted_zero_waivers_zero_defects():
    result=adjudicate()
    assert len(result.evidence_receipts)==9
    assert all(x.status=="ACCEPTED" for x in result.evidence_receipts)
    assert all(x.waivers==0 for x in result.evidence_receipts)
    assert all(x.open_defects==0 for x in result.evidence_receipts)


def test_missing_evidence_forces_no_go():
    r=deepcopy(reg())
    r["accepted_evidence"]["M11-009"]="certification-evidence/m11-009/missing.json"
    result=adjudicate(r)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    assert "M11-009:EVIDENCE_MISSING" in result.blocking_reasons


def test_nonaccepted_evidence_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-008/calibration-promotion-acceptance-v1.0.json").read_text())
    data["status"]="IN_PROGRESS"
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-008"]=str(p)
    result=adjudicate(r)
    assert "M11-008:NOT_ACCEPTED" in result.blocking_reasons


def test_waiver_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-007/effectiveness-learning-acceptance-v1.0.json").read_text())
    data["waivers"]=1
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-007"]=str(p)
    assert "M11-007:WAIVERS_PRESENT" in adjudicate(r).blocking_reasons


def test_open_defect_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-006/seller-workspace-acceptance-v1.0.json").read_text())
    data["open_defects"]=1
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-006"]=str(p)
    assert "M11-006:OPEN_DEFECTS_PRESENT" in adjudicate(r).blocking_reasons


def test_wrong_m11_009_expected_root_forces_no_go():
    r=deepcopy(reg())
    r["expected_m11_009_production_candidate_root"]="0"*64
    result=adjudicate(r)
    assert result.status=="FAIL"
    assert "M11-009:PRODUCTION_CANDIDATE_ROOT_EVIDENCE_MISMATCH" in result.blocking_reasons
    assert "M11-009:PRODUCTION_CANDIDATE_ROOT_REPRODUCTION_FAILED" in result.blocking_reasons


def test_wrong_release_candidate_version_fails_closed():
    r=deepcopy(reg()); r["release_candidate_version"]="9.9.9"
    with pytest.raises(ValueError,match="release candidate version mismatch"):
        adjudicate(r)


def test_wrong_frozen_final_root_forces_no_go():
    r=deepcopy(reg())
    r["expected_certification_root_hash"]="0"*64
    result=adjudicate(r)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    assert "M11_FINAL_CERTIFICATION_ROOT_MISMATCH" in result.blocking_reasons
